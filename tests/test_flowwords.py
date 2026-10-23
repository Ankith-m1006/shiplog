"""Flow tune-up: misheard names are found against names ShipLog is sure about, never guessed."""
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent / "app"))

import flowwords as fw  # noqa: E402

DOC = {"projects": [{"name": "ShipLog"}, {"name": "Graph Hacks"}],
       "watch": [{"repo": "kestra-io/plugin-jdbc", "number": 1063}],
       "github_user": {"login": "Ankith-m1006", "repos": ["Ankith-m1006/FalkorDB-demo"]},
       "items": [{"who": "flcarre"}], "flow_words": ["FalkorDB"],
       "entries": [{"text": "Pushed Shiplock day four. Asked fl carre about plugin jdbc. Falter DB is fine.", "source": "said"},
                   {"text": "Shiplock again, and the notes.", "source": "said"},
                   {"text": "Sample text Shiplock", "source": "sample"}]}


def test_known_terms_come_from_the_log_and_the_users_words():
    t = fw.known_terms(DOC)
    for want in ("ShipLog", "plugin-jdbc", "kestra-io", "Ankith-m1006", "flcarre", "FalkorDB"):
        assert want in t.values()


def test_misheard_names_are_found_and_counted_but_real_words_are_not():
    out = fw.tune_up(DOC)
    pairs = {(m["said"], m["meant"]): m["times"] for m in out["misheard"]}
    assert pairs[("Shiplock", "ShipLog")] == 2  # the sample entry doesn't count
    assert ("fl carre", "flcarre") in pairs and ("Falter DB", "FalkorDB") in pairs
    assert not any(m["said"].lower() in ("pushed", "notes", "again", "fine") for m in out["misheard"])


def test_exact_names_spelled_with_spaces_differently_are_not_flagged():
    assert fw.misheard("Shipped ShipLog today with plugin-jdbc", fw.known_terms(DOC)) == []


def test_tune_up_reports_words_time_dictionary_and_snippets():
    out = fw.tune_up(DOC)
    assert out["updates"] == 2 and out["words"] == 19
    assert out["type_min"] > out["talk_min"]
    assert "ShipLog" in out["dictionary"] and "flcarre" in out["dictionary"]
    assert {"say": "repo plugin jdbc", "text": "kestra-io/plugin-jdbc"} in out["snippets"]
