"""Speech-native reading: corrections, take-backs, hedges, urgency and spoken numbers are confirmed
in the words actually said, never taken on the model's word."""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "app"))

import extract as ex  # noqa: E402
import speech  # noqa: E402

TODAY = dt.date(2026, 10, 23)  # a Friday


def run(text, items):
    return ex.check({"summary": "s", "items": items}, text, ["ShipLog"], ["kestra-io/kestra"], TODAY)


def test_spoken_pr_numbers_become_digits():
    assert speech.words_to_number("twenty one six ninety four") == 21694
    assert speech.words_to_number("two one six nine four") == 21694
    assert speech.words_to_number("ten sixty three") == 1063
    assert speech.words_to_number("four hundred and seventy") == 470
    assert speech.spoken_numbers("I opened PR twenty one six ninety four today") == {21694: "twenty one six ninety four"}
    assert speech.words_to_number("banana") is None


def test_a_number_said_as_words_is_accepted_and_shown():
    text = "Opened PR twenty one six ninety four on kestra-io/kestra."
    draft, _ = run(text, [{"kind": "pr", "text": "Opened PR 21694", "quote": "Opened PR twenty one six ninety four",
                          "repo": "kestra-io/kestra", "number": 21694}])
    it = draft["items"][0]
    assert it["number"] == 21694 and it["said_number"] == "twenty one six ninety four" and not it["flags"]


def test_a_number_never_said_is_still_refused():
    draft, _ = run("Opened PR twenty one six ninety four.", [{"kind": "pr", "text": "PR 21695", "quote": "Opened PR", "number": 21695}])
    assert "number" not in draft["items"][0] and draft["items"][0]["flags"]


def test_a_self_correction_uses_the_corrected_date_and_says_so():
    text = "The DEV post is due Tuesday, no wait, Wednesday."
    draft, _ = run(text, [{"kind": "deadline", "text": "DEV post due", "quote": "The DEV post is due Tuesday, no wait, Wednesday",
                          "date_words": "Wednesday", "corrected_from": "Tuesday"}])
    it = draft["items"][0]
    assert it["due"] == "2026-10-28" and it["corrected"] == {"from": "Tuesday", "to": "Wednesday"} and not it["flags"]


def test_a_made_up_correction_is_not_shown():
    text = "The DEV post is due Wednesday."
    draft, _ = run(text, [{"kind": "deadline", "text": "DEV post due", "quote": "The DEV post is due Wednesday",
                          "date_words": "Wednesday", "corrected_from": "Tuesday"}])
    assert "corrected" not in draft["items"][0]


def test_picking_the_replaced_date_gets_flagged():
    text = "The DEV post is due Tuesday, no wait, Wednesday."
    draft, _ = run(text, [{"kind": "deadline", "text": "DEV post due", "quote": "The DEV post is due Tuesday",
                          "date_words": "Tuesday"}])
    assert any("corrected" in f for f in draft["items"][0]["flags"])


def test_something_taken_back_is_left_out_with_the_reason():
    text = "Ping Marco about the review. Actually scratch that. Submit the GitLab demo tonight."
    draft, dropped = run(text, [
        {"kind": "followup", "text": "Ping Marco", "quote": "Ping Marco about the review"},
        {"kind": "task", "text": "Submit GitLab demo", "quote": "Submit the GitLab demo tonight", "date_words": "tonight"}])
    assert [i["text"] for i in draft["items"]] == ["Submit GitLab demo"]
    assert dropped == [{"text": "Ping Marco", "why": "you took it back", "taken_back": True}]


def test_hedges_and_urgency_must_be_in_the_words():
    text = "I think the Qloo deadline is Saturday. Fixing the login bug is urgent. The demo is ready."
    draft, _ = run(text, [
        {"kind": "deadline", "text": "Qloo due", "quote": "the Qloo deadline is Saturday", "date_words": "Saturday", "unsure": True},
        {"kind": "task", "text": "Fix login bug", "quote": "Fixing the login bug is urgent"},
        {"kind": "done", "text": "Demo ready", "quote": "The demo is ready", "unsure": True, "urgent": True}])
    a, b, c = draft["items"]
    assert a["unsure"] == "i think" and b["urgent"] == "urgent"
    assert "unsure" not in c and "urgent" not in c


def test_speaking_vs_typing_time_is_reported():
    assert speech.stats(" ".join(["word"] * 150)) == {"words": 150, "talk_s": 60, "type_s": 225}


def test_a_take_back_inside_the_quote_counts_but_dont_forget_does_not():
    assert speech.retracted("Email Marco, actually scratch that, he replied.", "Email Marco, actually scratch that")
    assert not speech.retracted("Don't forget that the demo is Friday.", "Don't forget that the demo is Friday")
