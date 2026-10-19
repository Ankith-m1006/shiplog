import datetime as dt
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "app"))

import dates  # noqa: E402
import extract as ex  # noqa: E402

MON = dt.date(2026, 10, 19)  # a Monday


def test_relative_dates():
    assert dates.resolve("tomorrow", MON) == dt.date(2026, 10, 20)
    assert dates.resolve("day after tomorrow", MON) == dt.date(2026, 10, 21)
    assert dates.resolve("in 3 days", MON) == dt.date(2026, 10, 22)
    assert dates.resolve("in two weeks", MON) == dt.date(2026, 11, 2)
    assert dates.resolve("Friday night", MON) == dt.date(2026, 10, 23)
    assert dates.resolve("next Wednesday", MON) == dt.date(2026, 10, 21)
    assert dates.resolve("next week", MON) == dt.date(2026, 10, 26)


def test_same_weekday_is_not_guessed():
    assert dates.resolve("Monday", MON) is None
    assert dates.resolve("this Monday", MON) == MON
    assert dates.resolve("next Monday", MON) == dt.date(2026, 10, 26)


def test_absolute_dates():
    assert dates.resolve("29 October", MON) == dt.date(2026, 10, 29)
    assert dates.resolve("October 29th", MON) == dt.date(2026, 10, 29)
    assert dates.resolve("13 Nov", MON) == dt.date(2026, 11, 13)
    assert dates.resolve("2 January", MON) == dt.date(2027, 1, 2)
    assert dates.resolve("31 February", MON) is None
    assert dates.resolve("soon", MON) is None


TEXT = ("Finished the review fixes on PR 1063 in plugin-jdbc and pushed them. "
        "The Amazon submission is due Friday night. Don't ping the reviewer again.")


def run(items, projects=("Amazon Alexa+",), repos=("kestra-io/plugin-jdbc",)):
    return ex.check({"summary": "s", "items": items}, TEXT, list(projects), list(repos), MON)


def test_quote_must_be_in_update():
    draft, dropped = run([
        {"kind": "done", "text": "Pushed review fixes", "quote": "pushed them"},
        {"kind": "task", "text": "Write the blog", "quote": "write the blog tonight"},
    ])
    assert [i["text"] for i in draft["items"]] == ["Pushed review fixes"]
    assert dropped == [{"text": "Write the blog", "why": "its words aren't in the update"}]


def test_dates_are_resolved_by_code_not_model():
    draft, _ = run([{"kind": "deadline", "text": "Amazon submission", "quote": "The Amazon submission is due",
                     "date_words": "Friday night", "project": "amazon alexa+"}])
    item = draft["items"][0]
    assert item["due"] == "2026-10-23" and item["project"] == "Amazon Alexa+" and not item["flags"]


def test_invented_date_words_and_numbers_are_flagged():
    draft, _ = run([{"kind": "pr", "text": "jdbc PR", "quote": "PR 1063 in plugin-jdbc",
                     "date_words": "next Tuesday", "repo": "kestra-io/plugin-jdbc", "number": 1064}])
    item = draft["items"][0]
    assert "due" not in item and "number" not in item
    assert item["repo"] == "kestra-io/plugin-jdbc"
    assert len(item["flags"]) == 2


def test_known_repo_and_number_kept():
    draft, _ = run([{"kind": "pr", "text": "jdbc PR", "quote": "PR 1063", "repo": "kestra-io/plugin-jdbc",
                     "number": 1063}])
    assert draft["items"][0]["number"] == 1063 and not draft["items"][0]["flags"]


def test_number_read_from_quote_when_model_skips_it():
    draft, _ = run([{"kind": "pr", "text": "jdbc PR", "quote": "PR 1063 in plugin-jdbc", "repo": "kestra-io/plugin-jdbc"}])
    assert draft["items"][0]["number"] == 1063


def test_unknown_repo_not_confirmed():
    draft, _ = run([{"kind": "pr", "text": "x", "quote": "PR 1063", "repo": "someone/else"}])
    assert "repo" not in draft["items"][0]


def test_deadline_without_date_is_flagged():
    draft, _ = run([{"kind": "deadline", "text": "Amazon", "quote": "The Amazon submission is due"}])
    assert draft["items"][0]["flags"] == ["no date said"]


def test_too_long_update_rejected():
    try:
        ex.extract("x" * (ex.MAX_CHARS + 1), [], [])
    except ex.ExtractError:
        return
    raise AssertionError("expected ExtractError")
