"""ShipLog API and page.

Each browser keeps a random workspace key and sends it as X-Workspace; a new key starts with its own
copy of the demo data. The owner's real workspace uses the key in SHIPLOG_OWNER_KEY and starts empty.
"""
import datetime as dt
import hashlib
import hmac
import os
import pathlib
import re
import secrets
import time
import urllib.parse
import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, RedirectResponse, Response
from pydantic import BaseModel, Field

import ask as asker
import dates
import drafts
import extract as ex
import flowwords
import github
import reports
import gitlab
import speech
import telegram as tg
from store import Workspaces

STATIC = pathlib.Path(__file__).resolve().parent / "static"
KEY_RE = re.compile(r"^w[a-z0-9]{10,40}$")
OWNER_KEY = os.environ.get("SHIPLOG_OWNER_KEY", "")
READS_PER_HOUR = 40
GH_ID = os.environ.get("GITHUB_CLIENT_ID", "")
GH_SECRET = os.environ.get("GITHUB_CLIENT_SECRET", "")
oauth_states = {}  # state -> (workspace key, started at); one instance, so memory is enough

app = FastAPI(title="ShipLog")
spaces = Workspaces()
recent_reads = {}


def workspace(request: Request | None, key=None):
    key = key or (request.headers.get("X-Workspace", "") if request else "")
    owner = bool(OWNER_KEY) and hmac.compare_digest(key, OWNER_KEY)  # checked first: the owner key need not look like a browser key
    if not owner and not KEY_RE.match(key):
        raise HTTPException(400, "missing or malformed X-Workspace")
    return key, ("empty" if owner else "demo"), owner


def stamp():
    return dates.now().isoformat(timespec="seconds")


class SaveItem(BaseModel):
    kind: str
    text: str = Field(max_length=300)
    quote: str = Field(default="", max_length=600)
    due: str | None = None
    date_words: str | None = None
    project: str = ""
    repo: str | None = None
    number: int | None = None
    who: str = ""
    host: str = ""
    urgent: str = Field(default="", max_length=40)
    unsure: str = Field(default="", max_length=40)


class SaveChange(BaseModel):
    id: str = Field(max_length=20)
    action: str
    quote: str = Field(max_length=600)
    due: str | None = None


class SaveBody(BaseModel):
    text: str = Field(max_length=ex.MAX_CHARS)
    summary: str = Field(max_length=300)
    project: str = ""
    items: list[SaveItem] = Field(max_length=40)
    changes: list[SaveChange] = Field(default=[], max_length=40)


class ReadBody(BaseModel):
    text: str = Field(max_length=ex.MAX_CHARS)


class AskBody(BaseModel):
    question: str = Field(max_length=asker.MAX_QUESTION)


class ReportBody(BaseModel):
    kind: str


class FlowWord(BaseModel):
    word: str = Field(min_length=2, max_length=60)
    remove: bool = False


class ItemPatch(BaseModel):
    status: str | None = None
    text: str | None = Field(default=None, max_length=300)
    due: str | None = None


def valid_day(s):
    if not s:
        return None
    try:
        return dt.date.fromisoformat(s).isoformat()
    except ValueError:
        raise HTTPException(400, f"bad date {s!r}")


@app.get("/api/state")
def state(request: Request):
    key, seed, owner = workspace(request)
    doc = spaces.load(key, seed)
    public = {k: v for k, v in doc.items() if k != "secrets"}  # the GitHub token never leaves the server
    return {**public, "owner": owner, "today": dates.now().date().isoformat(), "github_enabled": bool(GH_ID)}


def known_repos(doc):
    return sorted({w["repo"] for w in doc["watch"]} | set((doc.get("github_user") or {}).get("repos", [])))


@app.post("/api/read")
def read(body: ReadBody, request: Request):
    key, seed, _ = workspace(request)
    now = time.time()
    hits = [t for t in recent_reads.get(key, []) if now - t < 3600]
    if len(hits) >= READS_PER_HOUR:
        raise HTTPException(429, "That's a lot of updates for one hour. Try again a little later.")
    recent_reads[key] = hits + [now]
    doc = spaces.load(key, seed)
    repos = known_repos(doc)
    try:
        log = [i for i in reversed(doc["items"]) if i.get("status") == "open"]
        out = ex.extract(body.text, [p["name"] for p in doc["projects"]], repos, log=log)
        out["heard"] = flowwords.misheard(body.text, flowwords.known_terms(doc))
        return out
    except ex.InputError as e:
        raise HTTPException(422, str(e))
    except ex.ExtractError as e:
        raise HTTPException(503, str(e))


@app.post("/api/report")
def write_report(body: ReportBody, request: Request):
    key, seed, _ = workspace(request)
    rate_limit(key)
    try:
        return reports.report(body.kind, spaces.load(key, seed))
    except reports.InputError as e:
        raise HTTPException(422, str(e))
    except reports.ExtractError as e:
        raise HTTPException(503, str(e))


@app.get("/api/flow")
def flow(request: Request):
    key, seed, _ = workspace(request)
    return flowwords.tune_up(spaces.load(key, seed))


@app.post("/api/flow/words")
def flow_words(body: FlowWord, request: Request):
    key, seed, _ = workspace(request)
    word = re.sub(r"\s+", " ", body.word).strip()

    def apply(doc):
        words = [w for w in doc.get("flow_words", []) if w.lower() != word.lower()]
        if not body.remove:
            words.append(word)
        doc["flow_words"] = words[-200:]
        return {"my_words": doc["flow_words"]}

    return spaces.edit(key, apply, seed)


def rate_limit(key):
    now = time.time()
    hits = [t for t in recent_reads.get(key, []) if now - t < 3600]
    if len(hits) >= READS_PER_HOUR:
        raise HTTPException(429, "That's a lot of requests for one hour. Try again a little later.")
    recent_reads[key] = hits + [now]


@app.post("/api/ask")
def ask(body: AskBody, request: Request):
    key, seed, _ = workspace(request)
    rate_limit(key)
    try:
        return asker.ask(body.question, spaces.load(key, seed))
    except asker.InputError as e:
        raise HTTPException(422, str(e))
    except asker.ExtractError as e:
        raise HTTPException(503, str(e))


@app.post("/api/save")
def save(body: SaveBody, request: Request):
    key, seed, _ = workspace(request)
    return save_into(key, seed, body)


def save_into(key, seed, body, source="said"):
    plain = ex.norm(body.text)

    def apply(doc):
        projects = {p["name"] for p in doc["projects"]}
        entry = {"id": uuid.uuid4().hex[:10], "at": stamp(), "text": body.text.strip(),
                 "summary": body.summary.strip(), "project": body.project if body.project in projects else "",
                 "source": source, "items": []}
        for it in body.items:
            if it.kind not in ex.KINDS or not it.text.strip():
                continue
            item = {"id": uuid.uuid4().hex[:10], "kind": it.kind, "text": it.text.strip(),
                    "quote": it.quote if ex.norm(it.quote) in plain else "",
                    "due": valid_day(it.due), "project": it.project if it.project in projects else entry["project"],
                    "who": it.who, "status": "done" if it.kind == "done" else "open",
                    "entry": entry["id"], "source": source, "created": entry["at"]}
            for mark in ("urgent", "unsure"):  # kept only when the speaker really said those words
                said = getattr(it, mark).strip()
                if said and speech.has(body.text, said):
                    item[mark] = said
            if it.repo and re.fullmatch(r"[\w.-]+(/[\w.-]+)+", it.repo):
                item["repo"] = it.repo
                if it.host == "gitlab":
                    item["host"] = "gitlab"
                if it.number:
                    item["number"] = it.number
                    if not any(w["repo"] == it.repo and w["number"] == it.number for w in doc["watch"]):
                        doc["watch"].append({"repo": it.repo, "number": it.number, "source": "said",
                                             **({"host": "gitlab"} if it.host == "gitlab" else {})})
            doc["items"].append(item)
            entry["items"].append(item["id"])
        entry["changes"] = []
        by_id = {i["id"]: i for i in doc["items"]}
        for c in body.changes:  # applied only when the change's words are really in this update
            target = by_id.get(c.id)
            if not target or c.action not in ex.ACTIONS or ex.norm(c.quote) not in plain:
                continue
            if c.action == "move":
                if not valid_day(c.due):
                    continue
                target["due"] = valid_day(c.due)
            else:
                target["status"] = {"done": "done", "drop": "dropped", "reopen": "open"}[c.action]
            target["updated"] = entry["at"]
            target.setdefault("history", []).append({"at": entry["at"], "action": c.action, "said": c.quote,
                                                     "entry": entry["id"]})
            entry["changes"].append({"id": c.id, "action": c.action, "quote": c.quote})
        doc["entries"].insert(0, entry)
        return entry

    return spaces.edit(key, apply, seed)


@app.patch("/api/item/{item_id}")
def patch_item(item_id: str, body: ItemPatch, request: Request):
    key, seed, _ = workspace(request)

    def apply(doc):
        for it in doc["items"]:
            if it["id"] == item_id:
                if body.status in ("open", "done", "dropped"):
                    it["status"] = body.status
                if body.text is not None and body.text.strip():
                    it["text"] = body.text.strip()
                if body.due is not None:
                    it["due"] = valid_day(body.due)
                it["updated"] = stamp()
                return it
        raise HTTPException(404, "no such item")

    return spaces.edit(key, apply, seed)


@app.delete("/api/entry/{entry_id}")
def delete_entry(entry_id: str, request: Request):
    key, seed, _ = workspace(request)

    def apply(doc):
        before = len(doc["entries"])
        doc["entries"] = [e for e in doc["entries"] if e["id"] != entry_id]
        if len(doc["entries"]) == before:
            raise HTTPException(404, "no such entry")
        doc["items"] = [i for i in doc["items"] if i.get("entry") != entry_id]
        return {"deleted": entry_id}

    return spaces.edit(key, apply, seed)


def live(w):
    return (gitlab if w.get("host") == "gitlab" else github).status(w["repo"], w["number"])


@app.get("/api/github")
def github_status(request: Request):
    """Live state of every watched PR/MR. A merge closes the items about it (with a history line);
    failing checks, requested changes or new comments since you last looked mark it 'needs you'."""
    key, seed, _ = workspace(request)
    doc = spaces.load(key, seed)
    watched = doc["watch"][:20]
    lives = {(w["repo"], w["number"]): live(w) for w in watched}

    def apply(doc):
        closed = []
        for w in doc["watch"][:20]:
            s = lives.get((w["repo"], w["number"]))
            if not s or s["state"] == "unknown":
                continue
            if "notes" in s and "seen_notes" not in w:
                w["seen_notes"] = s["notes"]
            if s["state"] == "merged" and w.get("state") != "merged":
                where = "GitLab" if w.get("host") == "gitlab" else "GitHub"
                for it in doc["items"]:
                    if it.get("repo") == w["repo"] and it.get("number") == w["number"] and it["status"] == "open" \
                            and it["kind"] in ("pr", "task", "followup"):
                        it["status"], it["updated"] = "done", stamp()
                        it.setdefault("history", []).append({"at": it["updated"], "action": "done",
                                                             "said": f"merged on {where}", "source": "github"})
                        closed.append(it["text"])
            w["state"] = s["state"]
        return {"closed": closed, "seen": {(w["repo"], w["number"]): w.get("seen_notes", 0) for w in doc["watch"]}}

    changed = any(s["state"] != "unknown" and (w.get("state") != s["state"] or ("notes" in s and "seen_notes" not in w))
                  for w in watched for s in [lives[(w["repo"], w["number"])]])
    out = spaces.edit(key, apply, seed) if changed else {"closed": [], "seen": {(w["repo"], w["number"]): w.get("seen_notes", 0) for w in watched}}
    prs = []
    for w in watched:
        s = dict(lives[(w["repo"], w["number"])])
        new = s.get("notes", 0) - out["seen"].get((w["repo"], w["number"]), 0)
        if s["state"] in ("open", "draft") and not s.get("needs") and new > 0:
            s["needs"] = f"{new} new comment{'s' if new > 1 else ''}"
        prs.append({**s, "source": w.get("source", "said"), "host": w.get("host", "github")})
    return {"prs": prs, "closed": out["closed"]}


class Seen(BaseModel):
    repo: str = Field(max_length=200)
    number: int


@app.post("/api/github/seen")
def github_seen(body: Seen, request: Request):
    key, seed, _ = workspace(request)

    def apply(doc):
        for w in doc["watch"]:
            if w["repo"] == body.repo and w["number"] == body.number:
                w["seen_notes"] = live(w).get("notes", w.get("seen_notes", 0))
                return {"ok": True}
        raise HTTPException(404, "not watched")

    return spaces.edit(key, apply, seed)


@app.post("/api/draft/{item_id}")
def follow_up_draft(item_id: str, request: Request):
    key, seed, _ = workspace(request)
    doc = spaces.load(key, seed)
    target = next((i for i in doc["items"] if i["id"] == item_id), None)
    if not target or target["kind"] not in ("followup", "pr", "task"):
        raise HTTPException(404, "no follow-up with that id")
    rules = [i for i in doc["items"] if i["kind"] == "rule"]
    pr = github.status(target["repo"], target["number"]) if target.get("repo") and target.get("number") else None
    try:
        return drafts.draft(target, rules, pr)
    except ex.ExtractError as e:
        raise HTTPException(503, str(e))


@app.post("/api/reset")
def reset(request: Request, empty: bool = False):
    key, _, owner = workspace(request)
    if owner:
        raise HTTPException(400, "the real workspace can't be reset to demo data")
    return spaces.reset(key, fresh=empty)


@app.get("/auth/github/start")
def github_start(w: str = ""):
    """OAuth web flow, step 1: send the visitor to GitHub's own consent page (read-only scope)."""
    if not GH_ID:
        raise HTTPException(503, "GitHub sign-in isn't set up on this server yet.")
    key, _, _ = workspace(None, w)
    now = time.time()
    for st, (_, at) in list(oauth_states.items()):
        if now - at > 600:
            oauth_states.pop(st, None)
    state = secrets.token_urlsafe(24)
    oauth_states[state] = (key, now)
    query = urllib.parse.urlencode({"client_id": GH_ID, "scope": "read:user", "state": state, "allow_signup": "true"})
    return RedirectResponse(f"https://github.com/login/oauth/authorize?{query}")


@app.get("/auth/github/callback")
def github_callback(code: str = "", state: str = "", error: str = ""):
    key, at = oauth_states.pop(state, (None, 0))
    if not key or time.time() - at > 600:
        return RedirectResponse("/?github=expired")
    if error or not code:
        return RedirectResponse("/?github=cancelled")
    try:
        token = github.exchange(GH_ID, GH_SECRET, code)
        me = github.profile(token)
    except Exception:  # a failed sign-in is reported on the page, never as a server error
        return RedirectResponse("/?github=failed")
    _, seed, _ = workspace(None, key)

    def apply(doc):
        doc["github_user"] = {"login": me["login"], "name": me["name"], "avatar": me["avatar"], "repos": me["repos"],
                              "connected": stamp()}
        doc.setdefault("secrets", {})["github_token"] = token
        have = {(w["repo"], w["number"]) for w in doc["watch"]}
        added = [p for p in me["prs"] if (p["repo"], p["number"]) not in have]
        doc["watch"] += [{"repo": p["repo"], "number": p["number"], "source": "github"} for p in added]
        return len(added)

    added = spaces.edit(key, apply, seed)
    return RedirectResponse(f"/?github=connected&prs={added}")


@app.post("/api/github/disconnect")
def github_disconnect(request: Request):
    key, seed, _ = workspace(request)

    def apply(doc):
        doc.pop("github_user", None)
        doc.pop("secrets", None)
        doc["watch"] = [w for w in doc["watch"] if w.get("source") != "github"]
        return {"ok": True}

    return spaces.edit(key, apply, seed)


@app.get("/api/deadlines.ics")
def ics(request: Request, w: str = ""):
    # A download link can't send headers, so the key comes as ?w=.
    key, seed, _ = workspace(request, w)
    return Response(calendar(spaces.load(key, seed)), media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="shiplog-deadlines.ics"'})


@app.get("/api/calendar")
def calendar_link(request: Request):
    """A private subscribe link for Google/Apple Calendar. It carries its own random token, never
    the workspace key, so sharing the calendar can't open the log."""
    key, seed, _ = workspace(request)

    def apply(doc):
        if not doc.get("cal"):
            doc["cal"] = secrets.token_urlsafe(18)
            spaces.backend.put("cal-" + doc["cal"], {"w": key})
        return doc["cal"]

    token = spaces.load(key, seed).get("cal") or spaces.edit(key, apply, seed)
    return {"path": f"/cal/{token}.ics"}


@app.get("/cal/{token}.ics")
def calendar_feed(token: str):
    ref = spaces.backend.get("cal-" + token) if re.fullmatch(r"[\w-]{20,40}", token) else None
    if not ref:
        raise HTTPException(404, "no such calendar")
    key, seed, _ = workspace(None, ref["w"])
    return Response(calendar(spaces.load(key, seed)), media_type="text/calendar")


def calendar(doc):
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ShipLog//EN", "CALSCALE:GREGORIAN",
             "X-WR-CALNAME:ShipLog deadlines", "REFRESH-INTERVAL;VALUE=DURATION:PT6H"]
    for it in doc["items"]:
        if it.get("due") and it["status"] == "open" and it["kind"] in ("deadline", "task", "followup"):
            day = it["due"].replace("-", "")
            nxt = (dt.date.fromisoformat(it["due"]) + dt.timedelta(days=1)).strftime("%Y%m%d")
            title = re.sub(r"[,;\\\n]", " ", it["text"])
            lines += ["BEGIN:VEVENT", f"UID:{it['id']}@shiplog", f"DTSTAMP:{dt.datetime.now(dt.timezone.utc):%Y%m%dT%H%M%SZ}",
                      f"DTSTART;VALUE=DATE:{day}", f"DTEND;VALUE=DATE:{nxt}", f"SUMMARY:{title}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"

BASE_URL = os.environ.get("SHIPLOG_URL", "https://shiplog-1037019152152.asia-south1.run.app")


@app.get("/api/telegram")
def telegram_link(request: Request):
    """A one-time link that ties a Telegram chat to this workspace. The code expires after one use."""
    key, _, _ = workspace(request)
    if not tg.enabled():
        raise HTTPException(404, "Telegram capture is not set up on this server")
    code = secrets.token_urlsafe(12).replace("-", "a").replace("_", "b")
    spaces.backend.put("tg-code-" + code, {"w": key, "at": time.time()})
    return {"url": tg.link(code)}


def tg_workspace(chat):
    ref = spaces.backend.get(f"tg-chat-{chat}")
    if ref:
        return ref["w"], False
    # A stranger (a judge) gets their own demo copy, the same as opening the web page.
    key = "wtg" + hashlib.sha256(f"{chat}:{tg.secret()}".encode()).hexdigest()[:24]
    spaces.backend.put(f"tg-chat-{chat}", {"w": key})
    return key, True


def tg_message(chat, text):
    if text.startswith("/start"):
        code = text.split(maxsplit=1)[1].strip() if " " in text else ""
        ref = spaces.backend.get("tg-code-" + code) if re.fullmatch(r"[A-Za-z0-9]{8,30}", code) else None
        if ref and time.time() - ref.get("at", 0) < 3600:
            spaces.backend.put(f"tg-chat-{chat}", {"w": ref["w"]})
            spaces.backend.put("tg-code-" + code, {"used": True})
            return tg.send(chat, "Linked to your ShipLog. Hold the Flow key and talk: what you finished, what's due, "
                                 "PRs, rules. I'll show what I understood before anything is saved.")
        key, new = tg_workspace(chat)
        return tg.send(chat, "Hi! I'm ShipLog. Talk to me with the Flow keyboard about your work: what you finished, "
                             "deadlines, PRs, people not to ping. Ask questions too, like \"what's due this week?\"\n\n"
                             f"This chat has its own ShipLog to try (with sample data). See it here: {BASE_URL}/?key={key}")
    key, _ = tg_workspace(chat)
    seed = "empty" if OWNER_KEY and hmac.compare_digest(key, OWNER_KEY) else "demo"
    try:
        rate_limit(key)
    except HTTPException as e:
        return tg.send(chat, e.detail)
    doc = spaces.load(key, seed)
    if re.search(r"\?\s*$", text) and len(text.split()) <= 25:
        try:
            a = asker.ask(text, doc)
        except (asker.InputError, asker.ExtractError) as e:
            return tg.send(chat, str(e))
        quotes = "\n".join(f"   \"{c['quote']}\" ({c['at'][:10]})" for c in a["cites"])
        return tg.send(chat, a["answer"] + ("\n\nFrom your log:\n" + quotes if quotes else ""))
    try:
        log = [i for i in reversed(doc["items"]) if i.get("status") == "open"]
        draft = ex.extract(text, [p["name"] for p in doc["projects"]], known_repos(doc), log=log)
        draft["heard"] = flowwords.misheard(text, flowwords.known_terms(doc))
    except (ex.InputError, ex.ExtractError) as e:
        return tg.send(chat, str(e))
    if not draft.get("items") and not draft.get("changes"):
        return tg.send(chat, tg.understood(draft))
    spaces.backend.put(f"tg-pending-{chat}", {"text": text, "draft": draft, "w": key})
    return tg.send(chat, tg.understood(draft), buttons=[("Save", "save"), ("Discard", "discard")])


def tg_button(chat, data):
    pending = spaces.backend.get(f"tg-pending-{chat}")
    if not pending or not pending.get("draft"):
        return tg.send(chat, "That one was already handled.")
    spaces.backend.put(f"tg-pending-{chat}", {})
    if data != "save":
        return tg.send(chat, "Discarded. Nothing was saved.")
    d, key = pending["draft"], pending["w"]
    seed = "empty" if OWNER_KEY and hmac.compare_digest(key, OWNER_KEY) else "demo"
    fields = SaveItem.model_fields
    body = SaveBody(text=pending["text"], summary=(d.get("summary") or "")[:300], project="",
                    items=[SaveItem(**{k: (v if v is not None or k in ("due", "date_words", "repo", "number") else "")
                                       for k, v in it.items() if k in fields}) for it in d.get("items", [])],
                    changes=[SaveChange(id=c["id"], action=c["action"], quote=c["quote"], due=c.get("due"))
                             for c in d.get("changes", [])])
    entry = save_into(key, seed, body, source="telegram")
    n = len(entry["items"]) + len(entry["changes"])
    return tg.send(chat, f"Saved {n} to your log. Open ShipLog to see it on Today.")


@app.post("/telegram/webhook")
async def telegram_webhook(request: Request):
    if not tg.enabled() or not hmac.compare_digest(request.headers.get("X-Telegram-Bot-Api-Secret-Token", ""), tg.secret()):
        raise HTTPException(403, "not from Telegram")
    u = await request.json()
    try:
        if "callback_query" in u:
            q = u["callback_query"]
            tg.call("answerCallbackQuery", callback_query_id=q["id"])
            tg_button(q["message"]["chat"]["id"], q.get("data", ""))
        elif (u.get("message") or {}).get("text"):
            m = u["message"]
            tg_message(m["chat"]["id"], m["text"].strip())
    except Exception as e:  # always answer 200, or Telegram retries the same update for hours
        print("telegram update failed:", repr(e))
    return {"ok": True}


@app.get("/")
def page():
    return FileResponse(STATIC / "index.html")
