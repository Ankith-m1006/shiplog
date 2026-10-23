"""Day 4: GitHub/GitLab close the loop. A merge closes the items about it; failing checks, requested
changes or new comments mark a PR 'needs you'; deadlines have a private calendar subscribe link."""
import datetime as dt
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "app"))
from fastapi.testclient import TestClient  # noqa: E402

import extract as ex  # noqa: E402
import github  # noqa: E402
import gitlab  # noqa: E402
import server  # noqa: E402
from store import LocalStore, Workspaces  # noqa: E402

H = {"X-Workspace": "wtestneedsyou01"}
LIVE = {}


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(server, "spaces", Workspaces(LocalStore(tmp_path)))
    monkeypatch.setattr(github, "status", lambda repo, n: {"repo": repo, "number": n, **LIVE[(repo, n)]})
    monkeypatch.setattr(gitlab, "status", lambda repo, n: {"repo": repo, "number": n, "host": "gitlab", **LIVE[(repo, n)]})
    c = TestClient(server.app)
    c.post("/api/reset?empty=true", headers=H)
    text = "Opened PR 7 on octo/app. Opened MR 3 on group/sub/tool."
    c.post("/api/save", headers=H, json={"text": text, "summary": "s", "items": [
        {"kind": "pr", "text": "PR 7", "quote": "Opened PR 7 on octo/app", "repo": "octo/app", "number": 7},
        {"kind": "pr", "text": "MR 3", "quote": "Opened MR 3 on group/sub/tool", "repo": "group/sub/tool", "number": 3, "host": "gitlab"}]})
    return c


def state(c):
    return c.get("/api/state", headers=H).json()


def test_gitlab_merge_requests_are_watched_on_gitlab(client):
    w = {x["repo"]: x for x in state(client)["watch"]}
    assert w["group/sub/tool"]["host"] == "gitlab" and "host" not in w["octo/app"]


def test_a_merge_closes_its_items_once_with_a_history_line(client):
    LIVE[("octo/app", 7)] = {"state": "merged", "detail": "merged", "notes": 2}
    LIVE[("group/sub/tool", 3)] = {"state": "open", "detail": "waiting", "notes": 0, "needs": ""}
    r = client.get("/api/github", headers=H).json()
    assert r["closed"] == ["PR 7"]
    item = next(i for i in state(client)["items"] if i["text"] == "PR 7")
    assert item["status"] == "done" and item["history"][-1]["said"] == "merged on GitHub"
    assert client.get("/api/github", headers=H).json()["closed"] == []


def test_new_comments_need_you_until_seen_and_failing_checks_always(client):
    LIVE[("octo/app", 7)] = {"state": "open", "detail": "x", "notes": 1, "needs": ""}
    LIVE[("group/sub/tool", 3)] = {"state": "open", "detail": "x", "notes": 0, "needs": "pipeline failing"}
    first = {p["repo"]: p for p in client.get("/api/github", headers=H).json()["prs"]}
    assert not first["octo/app"].get("needs") and first["group/sub/tool"]["needs"] == "pipeline failing"
    LIVE[("octo/app", 7)]["notes"] = 3
    again = {p["repo"]: p for p in client.get("/api/github", headers=H).json()["prs"]}
    assert again["octo/app"]["needs"] == "2 new comments"
    client.post("/api/github/seen", headers=H, json={"repo": "octo/app", "number": 7})
    assert not {p["repo"]: p for p in client.get("/api/github", headers=H).json()["prs"]}["octo/app"].get("needs")


def test_the_calendar_link_uses_its_own_token_and_serves_deadlines(client):
    client.post("/api/save", headers=H, json={"text": "GitLab is due Tuesday.", "summary": "s", "items": [
        {"kind": "deadline", "text": "GitLab due", "quote": "GitLab is due Tuesday", "due": "2026-10-27"}]})
    path = client.get("/api/calendar", headers=H).json()["path"]
    assert H["X-Workspace"] not in path and client.get("/api/calendar", headers=H).json()["path"] == path
    feed = client.get(path)
    assert feed.status_code == 200 and "SUMMARY:GitLab due" in feed.text and "DTSTART;VALUE=DATE:20261027" in feed.text
    assert client.get("/cal/" + "x" * 24 + ".ics").status_code == 404


def test_a_spoken_merge_request_is_read_as_gitlab():
    draft, _ = ex.check({"summary": "", "items": [{"kind": "pr", "text": "MR 12", "quote": "merge request 12 on mygroup/tool",
                                                   "repo": "mygroup/tool", "number": 12}]},
                        "Pushed merge request 12 on mygroup/tool.", [], [], dt.date(2026, 10, 23))
    assert draft["items"][0]["host"] == "gitlab" and draft["items"][0]["repo"] == "mygroup/tool"
