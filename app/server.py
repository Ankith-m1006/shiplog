"""ShipLog API and page.

Each browser keeps a random workspace key and sends it as X-Workspace; a new key starts with its own
copy of the demo data. The owner's real workspace uses the key in SHIPLOG_OWNER_KEY and starts empty.
"""
import datetime as dt
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
import github
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
    if not KEY_RE.match(key):
        raise HTTPException(400, "missing or malformed X-Workspace")
    owner = bool(OWNER_KEY) and hmac.compare_digest(key, OWNER_KEY)
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


class SaveBody(BaseModel):
    text: str = Field(max_length=ex.MAX_CHARS)
    summary: str = Field(max_length=300)
    project: str = ""
    items: list[SaveItem] = Field(max_length=40)


class ReadBody(BaseModel):
    text: str = Field(max_length=ex.MAX_CHARS)


class AskBody(BaseModel):
    question: str = Field(max_length=asker.MAX_QUESTION)


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
        return ex.extract(body.text, [p["name"] for p in doc["projects"]], repos)
    except ex.InputError as e:
        raise HTTPException(422, str(e))
    except ex.ExtractError as e:
        raise HTTPException(503, str(e))


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
    plain = ex.norm(body.text)

    def apply(doc):
        projects = {p["name"] for p in doc["projects"]}
        entry = {"id": uuid.uuid4().hex[:10], "at": stamp(), "text": body.text.strip(),
                 "summary": body.summary.strip(), "project": body.project if body.project in projects else "",
                 "source": "said", "items": []}
        for it in body.items:
            if it.kind not in ex.KINDS or not it.text.strip():
                continue
            item = {"id": uuid.uuid4().hex[:10], "kind": it.kind, "text": it.text.strip(),
                    "quote": it.quote if ex.norm(it.quote) in plain else "",
                    "due": valid_day(it.due), "project": it.project if it.project in projects else entry["project"],
                    "who": it.who, "status": "done" if it.kind == "done" else "open",
                    "entry": entry["id"], "source": "said", "created": entry["at"]}
            if it.repo and re.fullmatch(r"[\w.-]+/[\w.-]+", it.repo):
                item["repo"] = it.repo
                if it.number:
                    item["number"] = it.number
                    if not any(w["repo"] == it.repo and w["number"] == it.number for w in doc["watch"]):
                        doc["watch"].append({"repo": it.repo, "number": it.number, "source": "said"})
            doc["items"].append(item)
            entry["items"].append(item["id"])
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


@app.get("/api/github")
def github_status(request: Request):
    key, seed, _ = workspace(request)
    doc = spaces.load(key, seed)
    return {"prs": [{**github.status(w["repo"], w["number"]), "source": w.get("source", "said")} for w in doc["watch"][:20]]}


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
    doc = spaces.load(key, seed)
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//ShipLog//EN", "CALSCALE:GREGORIAN"]
    for it in doc["items"]:
        if it.get("due") and it["status"] == "open" and it["kind"] in ("deadline", "task", "followup"):
            day = it["due"].replace("-", "")
            nxt = (dt.date.fromisoformat(it["due"]) + dt.timedelta(days=1)).strftime("%Y%m%d")
            title = re.sub(r"[,;\\\n]", " ", it["text"])
            lines += ["BEGIN:VEVENT", f"UID:{it['id']}@shiplog", f"DTSTAMP:{dt.datetime.utcnow():%Y%m%dT%H%M%SZ}",
                      f"DTSTART;VALUE=DATE:{day}", f"DTEND;VALUE=DATE:{nxt}", f"SUMMARY:{title}", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return Response("\r\n".join(lines) + "\r\n", media_type="text/calendar",
                    headers={"Content-Disposition": 'attachment; filename="shiplog-deadlines.ics"'})


@app.get("/")
def page():
    return FileResponse(STATIC / "index.html")
