"""Day 3: Ask answers only from the saved log, and every answer is backed by a checked quote."""
import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "app"))

import ask  # noqa: E402
from store import demo  # noqa: E402

DOC = demo()
RECS = ask.records(DOC)
ENTRY = next(r for r in RECS if r["type"] == "entry")


def test_records_carry_what_was_said_for_entries_and_items():
    kinds = {r["type"] for r in RECS}
    assert "entry" in kinds and kinds - {"entry"}
    assert all(r["said"] for r in RECS)


def test_a_citation_whose_quote_is_really_in_the_record_is_kept():
    quote = ENTRY["said"].split(".")[0][:60]
    out = ask.check({"found": True, "answer": "You said so.", "cites": [{"id": ENTRY["id"], "quote": quote}]}, RECS)
    assert out["found"] is True
    assert out["cites"][0]["id"] == ENTRY["id"]


def test_an_answer_whose_quotes_are_made_up_becomes_not_in_your_log():
    out = ask.check({"found": True, "answer": "The Amazon deadline moved to Monday.",
                     "cites": [{"id": ENTRY["id"], "quote": "the deadline moved to Monday"}]}, RECS)
    assert out == {"found": False, "answer": ask.NOT_FOUND, "cites": [], "dropped": 1}


def test_a_citation_to_an_unknown_record_is_dropped():
    out = ask.check({"found": True, "answer": "Yes.", "cites": [{"id": "nope", "quote": "anything"}]}, RECS)
    assert out["found"] is False and out["dropped"] == 1


def test_the_model_saying_not_found_is_respected_even_with_a_valid_quote():
    quote = ENTRY["said"][:40]
    out = ask.check({"found": False, "answer": "I don't know.", "cites": [{"id": ENTRY["id"], "quote": quote}]}, RECS)
    assert out["found"] is False and out["answer"] == ask.NOT_FOUND


def test_the_same_record_is_cited_once():
    quote = ENTRY["said"][:40]
    out = ask.check({"found": True, "answer": "You said it twice.",
                     "cites": [{"id": ENTRY["id"], "quote": quote}, {"id": ENTRY["id"], "quote": quote}]}, RECS)
    assert len(out["cites"]) == 1


def test_empty_and_overlong_questions_are_the_users_error():
    for q in ["", "   ", "x" * (ask.MAX_QUESTION + 1)]:
        try:
            ask.ask(q, DOC, dt.date(2026, 10, 22))
        except ask.InputError:
            continue
        raise AssertionError(f"no InputError for {q[:10]!r}")


def test_an_empty_log_answers_not_in_your_log_without_calling_the_model(monkeypatch):
    monkeypatch.setattr(ask, "ask_model_raw", lambda *a: (_ for _ in ()).throw(AssertionError("model called")))
    out = ask.ask("What is due?", {"entries": [], "items": []}, dt.date(2026, 10, 22))
    assert out["found"] is False
