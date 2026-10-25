"""Capture from the phone: a Telegram bot. Talk into the chat with the Flow keyboard; the bot reads the
update like the web page does and replies with what it understood. Nothing is saved until Save is tapped.

Set TELEGRAM_TOKEN (and TELEGRAM_BOT, the bot's username) to turn it on."""
import hashlib
import json
import os
import urllib.request

TOKEN = os.environ.get("TELEGRAM_TOKEN", "")
BOT = os.environ.get("TELEGRAM_BOT", "shiplog_ankith_bot")
KINDS = {"done": "Done", "task": "Task", "deadline": "Deadline", "followup": "Follow-up", "rule": "Rule", "pr": "PR"}
ACTIONS = {"done": "mark done", "drop": "drop", "reopen": "reopen", "move": "move to"}


def enabled():
    return bool(TOKEN)


def secret():
    """Telegram sends this back in a header on every webhook call, so only Telegram can post updates."""
    return hashlib.sha256(("shiplog-webhook:" + TOKEN).encode()).hexdigest()[:48]


def call(method, **params):
    req = urllib.request.Request(f"https://api.telegram.org/bot{TOKEN}/{method}", data=json.dumps(params).encode(),
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=20) as r:
        return json.loads(r.read())


def send(chat, text, buttons=None):
    params = {"chat_id": chat, "text": text[:4000], "disable_web_page_preview": True}
    if buttons:
        params["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": d} for t, d in buttons]]}
    return call("sendMessage", **params)


def link(code):
    return f"https://t.me/{BOT}?start={code}"


def understood(draft):
    """What the bot read, as plain text: one line per item with the words it came from."""
    lines = []
    for it in draft.get("items", []):
        due = f" (due {it['due']})" if it.get("due") else ""
        marks = "".join(f" [{m}: \"{it[m]}\"]" for m in ("urgent", "unsure") if it.get(m))
        lines.append(f"• {KINDS.get(it['kind'], it['kind'])}: {it['text']}{due}{marks}")
        if it.get("quote"):
            lines.append(f"   you said: \"{it['quote']}\"")
    for c in draft.get("changes", []):
        to = f" {c['due']}" if c["action"] == "move" else ""
        lines.append(f"• Change: {ACTIONS[c['action']]}{to}: {c['item']}")
        lines.append(f"   you said: \"{c['quote']}\"")
    for h in draft.get("heard", []):
        lines.append(f"Flow may have misheard \"{h['said']}\": did you mean {h['meant']}?")
    if not lines:
        return "I didn't find anything to log in that. Try a deadline, a PR, something you finished or a rule."
    words = (draft.get("speech") or {}).get("words")
    head = f"Here's what I understood ({words} words):" if words else "Here's what I understood:"
    return head + "\n\n" + "\n".join(lines) + "\n\nNothing is saved until you tap Save."
