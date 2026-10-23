"""Speak once, ship everywhere: stand-ups, weekly reports and posts come only from the log."""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "app"))

import reports  # noqa: E402

TODAY = dt.date(2026, 10, 23)
DOC = {"entries": [{"id": "e1", "at": "2026-10-23T09:00:00+05:30", "text": "Submitted ShipLog and Amma's Hour this morning.", "project": ""},
                   {"id": "e0", "at": "2026-10-10T09:00:00+05:30", "text": "Old update about Qloo.", "project": ""}],
       "items": [{"id": "i1", "kind": "deadline", "text": "GitLab due", "quote": "GitLab is due Tuesday", "due": "2026-10-27", "status": "open"},
                 {"id": "i2", "kind": "pr", "text": "PR 21403", "quote": "PR 21403 waiting", "repo": "kestra-io/kestra", "number": 21403,
                  "status": "done", "updated": "2026-10-23T10:01:00+05:30"},
                 {"id": "i3", "kind": "task", "text": "Old closed", "quote": "old", "status": "done", "updated": "2026-10-01T10:00:00+05:30"}]}


def test_the_window_keeps_recent_entries_open_items_and_recently_closed_ones():
    ids = {r["id"] for r in reports.window(DOC, 1, TODAY)}
    assert ids == {"e1", "i1", "i2"}


def test_a_draft_with_traced_citations_is_kept():
    recs = reports.window(DOC, 7, TODAY)
    text, cites, unknown = reports.check({"text": "Yesterday: submitted ShipLog. Today: GitLab due 27 Oct; PR 21403 merged.",
                                          "cites": [{"id": "e1", "quote": "Submitted ShipLog"}]}, recs)
    assert cites[0]["id"] == "e1" and unknown == []


def test_numbers_not_in_the_log_are_caught():
    recs = reports.window(DOC, 7, TODAY)
    _, _, unknown = reports.check({"text": "Merged PR 99999 and got 500 stars.", "cites": [{"id": "e1", "quote": "Submitted ShipLog"}]}, recs)
    assert "99999" in unknown and "500" in unknown


def test_an_empty_window_says_so_without_calling_the_model():
    out = reports.report("standup", {"entries": [], "items": []}, TODAY)
    assert out["empty"] and out["text"] == reports.EMPTY


def test_spoken_requests_are_recognised():
    assert reports.spoken_request("Write my stand-up") == "standup"
    assert reports.spoken_request("please make me a weekly report") == "weekly"
    assert reports.spoken_request("draft a post") == "post"
    assert reports.spoken_request("I wrote the post about Qloo") is None


def test_x_length_counts_links_as_23():
    assert reports.x_length("see https://example.com/a/very/long/link/that/goes/on") == 4 + 23
