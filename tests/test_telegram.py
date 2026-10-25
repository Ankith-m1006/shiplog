import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "app"))
from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
import telegram as tg  # noqa: E402
from store import LocalStore, Workspaces  # noqa: E402

UPDATE = "Opened PR 21694 on kestra-io/kestra today. The GitLab hackathon is due Tuesday."


def fake_extract(text, projects, repos, log=()):
    return {"summary": "PR opened, GitLab due", "items": [
        {"kind": "pr", "text": "Opened PR 21694", "quote": "Opened PR 21694", "repo": "kestra-io/kestra", "number": 21694,
         "due": None, "project": "", "who": "", "host": "", "urgent": "", "unsure": "", "date_words": None},
        {"kind": "deadline", "text": "GitLab hackathon", "quote": "The GitLab hackathon is due Tuesday",
         "due": "2026-10-27", "date_words": "Tuesday", "project": "", "who": "", "repo": None, "number": None}],
        "changes": [], "speech": {"words": 15}}


def setup(tmp_path, monkeypatch):
    sent = []
    monkeypatch.setattr(server, "spaces", Workspaces(LocalStore(tmp_path)))
    monkeypatch.setattr(tg, "TOKEN", "123:test")
    monkeypatch.setattr(tg, "call", lambda method, **p: sent.append((method, p)) or {"ok": True})
    monkeypatch.setattr(server.ex, "extract", fake_extract)
    monkeypatch.setattr(server, "recent_reads", {})
    return TestClient(server.app), sent


def post(c, update, secret=None):
    return c.post("/telegram/webhook", json=update, headers={"X-Telegram-Bot-Api-Secret-Token": secret or tg.secret()})


def msg(text, chat=42):
    return {"message": {"chat": {"id": chat}, "text": text}}


def press(data, chat=42):
    return {"callback_query": {"id": "q1", "data": data, "message": {"chat": {"id": chat}}}}


def test_only_telegram_can_post(tmp_path, monkeypatch):
    c, sent = setup(tmp_path, monkeypatch)
    assert post(c, msg("hi"), secret="wrong").status_code == 403
    assert sent == []


def test_linked_chat_reads_then_saves_only_on_save(tmp_path, monkeypatch):
    c, sent = setup(tmp_path, monkeypatch)
    ws = {"X-Workspace": "wabcdefghij12"}
    url = c.get("/api/telegram", headers=ws).json()["url"]
    code = url.split("start=")[1]
    post(c, msg(f"/start {code}"))
    assert "Linked to your ShipLog" in sent[-1][1]["text"]
    before = len(c.get("/api/state", headers=ws).json()["items"])

    post(c, msg(UPDATE))
    reply = sent[-1][1]
    assert "you said: \"The GitLab hackathon is due Tuesday\"" in reply["text"] and "(due 2026-10-27)" in reply["text"]
    assert [b["callback_data"] for b in reply["reply_markup"]["inline_keyboard"][0]] == ["save", "discard"]
    assert len(c.get("/api/state", headers=ws).json()["items"]) == before  # nothing saved yet

    post(c, press("save"))
    assert sent[-1][1]["text"].startswith("Saved 2")
    state = c.get("/api/state", headers=ws).json()
    new = state["items"][-2:]
    assert {i["kind"] for i in new} == {"pr", "deadline"} and all(i["source"] == "telegram" for i in new)
    assert any(w["number"] == 21694 for w in state["watch"])

    post(c, press("save"))  # a second tap does nothing
    assert "already handled" in sent[-1][1]["text"]
    assert len(c.get("/api/state", headers=ws).json()["items"]) == before + 2


def test_discard_saves_nothing_and_a_code_works_once(tmp_path, monkeypatch):
    c, sent = setup(tmp_path, monkeypatch)
    ws = {"X-Workspace": "wabcdefghij12"}
    code = c.get("/api/telegram", headers=ws).json()["url"].split("start=")[1]
    post(c, msg(f"/start {code}"))
    post(c, msg(f"/start {code}", chat=99))  # someone else reusing the link gets their own demo, not this log
    assert "Linked" not in sent[-1][1]["text"]
    before = len(c.get("/api/state", headers=ws).json()["items"])
    post(c, msg(UPDATE))
    post(c, press("discard"))
    assert "Nothing was saved" in sent[-1][1]["text"]
    assert len(c.get("/api/state", headers=ws).json()["items"]) == before


def test_a_stranger_gets_a_demo_copy_and_questions_are_answered(tmp_path, monkeypatch):
    c, sent = setup(tmp_path, monkeypatch)
    monkeypatch.setattr(server.asker, "ask", lambda q, doc: {"found": True, "answer": "The GitLab hackathon, Tuesday.",
                                                             "cites": [{"quote": "due Tuesday", "at": "2026-10-25T10:00"}]})
    post(c, msg("/start"))
    assert "?key=wtg" in sent[-1][1]["text"]
    post(c, msg("What's due this week?"))
    assert sent[-1][1]["text"].startswith("The GitLab hackathon, Tuesday.") and "\"due Tuesday\"" in sent[-1][1]["text"]
