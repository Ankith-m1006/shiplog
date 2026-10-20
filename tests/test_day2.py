import pathlib
import sys
import threading
import urllib.error

import pytest

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "app"))

import drafts  # noqa: E402
import extract as ex  # noqa: E402
import github  # noqa: E402
from store import LocalStore, Workspaces  # noqa: E402


@pytest.mark.parametrize("text", ["", "   ", "x" * (ex.MAX_CHARS + 1)])
def test_unreadable_update_is_the_users_error_not_a_server_error(text):
    with pytest.raises(ex.InputError):
        ex.extract(text, [], [])


def test_parallel_first_loads_of_a_new_workspace_do_not_race(tmp_path):
    spaces = Workspaces(LocalStore(tmp_path))
    errors, docs = [], []

    def open_it():
        try:
            docs.append(spaces.load("wnewworkspace01"))
        except Exception as e:  # noqa: BLE001 - the test is about any crash
            errors.append(e)

    threads = [threading.Thread(target=open_it) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert len({id(d) for d in docs}) == 1
    assert [p.name for p in tmp_path.iterdir()] == ["wnewworkspace01.json"]


RULES = [
    {"kind": "rule", "status": "open", "text": "Don't ping the JDBC reviewer again", "quote": "don't ping them again",
     "repo": "kestra-io/plugin-jdbc", "number": 1063},
    {"kind": "rule", "status": "open", "text": "Never nudge Priya on weekends", "who": "Priya"},
    {"kind": "rule", "status": "open", "text": "Keep every nudge to two sentences"},
    {"kind": "rule", "status": "dropped", "text": "No messages to anyone at Kestra", "repo": "kestra-io/kestra"},
]


def test_a_rule_on_the_same_pr_or_person_blocks_the_draft():
    assert drafts.draft({"text": "Nudge on 1063", "repo": "kestra-io/plugin-jdbc", "number": 1063}, RULES)["rule"] == RULES[0]["text"]
    assert drafts.draft({"text": "Ask about the slides", "who": "priya"}, RULES)["blocked"] is True


def test_a_soft_rule_on_the_same_pr_shapes_the_draft_instead_of_blocking_it(monkeypatch):
    monkeypatch.setattr(ex, "ask_model_raw", lambda system, facts, schema: {"draft": "One last check on this one."})
    soft = [{"kind": "rule", "status": "open", "text": "Only one more nudge on the pt_BR PR, then stop",
             "repo": "kestra-io/kestra", "number": 20735}]

    out = drafts.draft({"text": "Nudge pt_BR", "repo": "kestra-io/kestra", "number": 20735}, soft)

    assert out["blocked"] is False and out["rules"] == ["Only one more nudge on the pt_BR PR, then stop"]


def test_general_rules_are_passed_to_the_writer_and_lifted_rules_are_ignored(monkeypatch):
    seen = {}

    def fake_model(system, facts, schema):
        seen["facts"] = facts
        return {"draft": "Could you take another look at #20735 when you have a moment?"}

    monkeypatch.setattr(ex, "ask_model_raw", fake_model)
    out = drafts.draft({"text": "Nudge on pt_BR", "quote": "nudge them on the pt_BR PR", "repo": "kestra-io/kestra", "number": 20735},
                       RULES, {"state": "open", "detail": "waiting for review · checks passing"})

    assert out == {"blocked": False, "draft": "Could you take another look at #20735 when you have a moment?",
                   "rules": ["Keep every nudge to two sentences"]}
    assert "GitHub status now: open (waiting for review · checks passing)" in seen["facts"]
    assert "Rules to respect: Keep every nudge to two sentences" in seen["facts"]


def test_review_and_checks_summaries():
    assert github._review([]) == "waiting for review"
    assert github._review([{"state": "COMMENTED", "user": {"login": "a"}}]) == "reviewed, no decision"
    assert github._review([{"state": "CHANGES_REQUESTED", "user": {"login": "a"}},
                           {"state": "APPROVED", "user": {"login": "a"}}]) == "approved"
    assert github._review([{"state": "APPROVED", "user": {"login": "a"}},
                           {"state": "CHANGES_REQUESTED", "user": {"login": "b"}}]) == "changes requested"
    assert github._checks([{"status": "completed", "conclusion": "success"}]) == "checks passing"
    assert github._checks([{"status": "in_progress", "conclusion": None}]) == "checks running"
    assert github._checks([{"status": "completed", "conclusion": "failure"}]) == "checks failing"


def test_unreachable_github_is_unknown_not_failed_and_retried_soon(monkeypatch):
    calls = []

    def down(repo, number):
        calls.append(number)
        raise urllib.error.HTTPError("u", 403, "rate limited", {}, None)

    monkeypatch.setattr(github, "fetch", down)
    github._cache.clear()
    first = github.status("kestra-io/kestra", 1, now=1000)
    github.status("kestra-io/kestra", 1, now=1030)
    github.status("kestra-io/kestra", 1, now=1061)

    assert first["state"] == "unknown" and "rate limit" in first["detail"]
    assert calls == [1, 1]
