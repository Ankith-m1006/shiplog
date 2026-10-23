"""Talk to edit: a spoken update can close, move, drop or reopen items already in the log, and the
server applies a change only when its words are really in the update that was saved."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from fastapi.testclient import TestClient  # noqa: E402

import server  # noqa: E402
from store import LocalStore, Workspaces  # noqa: E402

H = {"X-Workspace": "wtesttalkedit01"}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "spaces", Workspaces(LocalStore(tmp_path)))
    c = TestClient(server.app)
    c.post("/api/reset?empty=true", headers=H)
    c.post("/api/save", headers=H, json={"text": "Amazon is due Friday. The DEV post is due Monday.", "summary": "s", "items": [
        {"kind": "deadline", "text": "Amazon", "quote": "Amazon is due Friday", "due": "2026-10-23"},
        {"kind": "deadline", "text": "DEV post", "quote": "The DEV post is due Monday", "due": "2026-10-26"}]})
    return c


def items(c):
    return {i["text"]: i for i in c.get("/api/state", headers=H).json()["items"]}


def test_the_log_sends_open_items_to_the_reader(client, monkeypatch):
    seen = {}
    monkeypatch.setattr(server.ex, "extract", lambda text, projects, repos, log=(): seen.setdefault("log", log) and
                        {"summary": "", "items": [], "changes": [], "dropped": []})
    client.post("/api/read", headers=H, json={"text": "The Amazon one is done."})
    assert {i["text"] for i in seen["log"]} == {"Amazon", "DEV post"}


def test_spoken_changes_are_applied_with_history(client):
    ids = {k: v["id"] for k, v in items(client).items()}
    text = "The Amazon one is done. Push the DEV post to Tuesday."
    r = client.post("/api/save", headers=H, json={"text": text, "summary": "s", "items": [], "changes": [
        {"id": ids["Amazon"], "action": "done", "quote": "The Amazon one is done"},
        {"id": ids["DEV post"], "action": "move", "quote": "Push the DEV post to Tuesday", "due": "2026-10-27"}]})
    assert len(r.json()["changes"]) == 2
    now = items(client)
    assert now["Amazon"]["status"] == "done" and now["DEV post"]["due"] == "2026-10-27"
    assert now["Amazon"]["history"][0]["said"] == "The Amazon one is done"


def test_a_change_whose_words_were_not_said_is_ignored(client):
    ids = {k: v["id"] for k, v in items(client).items()}
    client.post("/api/save", headers=H, json={"text": "Lunch was good.", "summary": "s", "items": [], "changes": [
        {"id": ids["Amazon"], "action": "drop", "quote": "Drop Amazon"}]})
    assert items(client)["Amazon"]["status"] == "open"
