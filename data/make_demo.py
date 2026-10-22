"""Build data/demo.json: a public-safe copy of my real October (14-18 Oct 2026).

Note: data/demo.json also carries two follow-ups and a 20 Oct closing update added by hand after day 2;
re-running this script drops them.

The updates are my real tracker events, retold the way I'd say them; no secrets, file paths or
other people's details. Every item quotes its update, and this script fails if a quote isn't in it.
The PRs are real public PRs, so their status on the Today screen is fetched live from GitHub.

    python data/make_demo.py
"""
import json
import pathlib
import re

OUT = pathlib.Path(__file__).with_name("demo.json")

PROJECTS = [
    ("Kestra Hacktober", "2026-10-31", "open-source contribution drive"),
    ("ShipLog", "2026-10-30", "No Hands: The Wispr Challenge"),
    ("Amazon Alexa+", "2026-10-24", "voice skill hackathon"),
    ("DEV weekly challenge", None, "weekly writing challenge"),
    ("OpenCV", "2026-10-27", "computer vision hackathon"),
    ("GitLab", "2026-10-27", "GitLab hackathon"),
    ("Qloo", "2026-10-31", "taste AI hackathon"),
    ("Graph Hacks", None, "graph database hackathon"),
]

# (time, project, what I said, summary, [(kind, item text, quote, due, extra)])
ENTRIES = [
    ("2026-10-14T19:10:00+05:30", "Kestra Hacktober",
     "Posted a follow-up on the pt_BR duration PR, tagged both reviewers. CI is green. If nobody replies in two days, one more nudge, then stop.",
     "Followed up on the pt_BR duration PR; CI is green.",
     [("done", "Followed up on the pt_BR duration PR", "Posted a follow-up on the pt_BR duration PR", None, {"repo": "kestra-io/kestra", "number": 20735}),
      ("rule", "Only one more nudge on the pt_BR PR, then stop", "one more nudge, then stop", None, {"repo": "kestra-io/kestra", "number": 20735})]),
    ("2026-10-16T16:40:00+05:30", "Kestra Hacktober",
     "PDFBox plugin got approved after three review rounds, the last one was icons for dark mode. The plugin-kestra paging fix merged today. Asked the JDBC reviewer to approve the CI run, don't ping them again. No new issue claims until some of the open PRs merge.",
     "PDFBox plugin approved, paging fix merged, asked for CI approval on JDBC.",
     [("done", "PDFBox plugin approved", "PDFBox plugin got approved after three review rounds", None, {"repo": "kestra-io/plugin-pdfbox", "number": 5}),
      ("done", "plugin-kestra paging fix merged", "The plugin-kestra paging fix merged today", None, {"repo": "kestra-io/plugin-kestra", "number": 202}),
      ("rule", "Don't ping the JDBC reviewer again", "don't ping them again", None, {"repo": "kestra-io/plugin-jdbc", "number": 1063}),
      ("rule", "No new issue claims until open PRs merge", "No new issue claims until some of the open PRs merge", None, {})]),
    ("2026-10-17T21:15:00+05:30", "DEV weekly challenge",
     "BillSahi is published on DEV for week two. Results come around the twenty-third. The Bitbucket Pipelines blueprint also merged, that's the thirty-third.",
     "Published BillSahi on DEV; Bitbucket blueprint merged.",
     [("done", "BillSahi published on DEV (week 2)", "BillSahi is published on DEV for week two", None, {}),
      ("task", "Check DEV week 2 results", "Results come around the twenty-third", "2026-10-23", {}),
      ("done", "Bitbucket Pipelines blueprint merged (33rd)", "The Bitbucket Pipelines blueprint also merged", None, {"project": "Kestra Hacktober"})]),
    ("2026-10-18T23:30:00+05:30", "Graph Hacks",
     "Submitted DawaiGraph to Graph Hacks with the video and the blog. DEV week one didn't place, lesson noted. Tomorrow I start ShipLog, and Amazon Alexa is due Friday night.",
     "Submitted DawaiGraph; DEV week 1 didn't place; ShipLog starts tomorrow.",
     [("done", "Submitted DawaiGraph to Graph Hacks", "Submitted DawaiGraph to Graph Hacks with the video and the blog", None, {}),
      ("done", "DEV week 1 didn't place", "DEV week one didn't place", None, {"project": "DEV weekly challenge"}),
      ("task", "Start building ShipLog", "Tomorrow I start ShipLog", "2026-10-19", {"project": "ShipLog"}),
      ("deadline", "Amazon Alexa+ submission", "Amazon Alexa is due Friday night", "2026-10-24", {"project": "Amazon Alexa+"})]),
]

DEADLINES = [  # from each hackathon's own page, as I logged them
    ("Amazon Alexa+", "Amazon Alexa+ submission (00:30 IST)", "2026-10-24"),
    ("OpenCV", "OpenCV submission (12:15 IST)", "2026-10-27"),
    ("GitLab", "GitLab submission (18:30 IST)", "2026-10-27"),
    ("ShipLog", "Wispr challenge submission (23:59 IST)", "2026-10-30"),
    ("Qloo", "Qloo submission (09:15 IST)", "2026-10-31"),
    ("Kestra Hacktober", "Kestra Hacktober ends", "2026-10-31"),
]

WATCH = [("kestra-io/kestra", 20735), ("kestra-io/kestra", 21008), ("kestra-io/plugin-jdbc", 1063),
         ("kestra-io/plugin-pdfbox", 5), ("kestra-io/plugin-kestra", 202)]


def norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s#/.-]", " ", s.lower())).strip()


doc = {"projects": [{"name": n, "deadline": d, "about": a} for n, d, a in PROJECTS],
       "entries": [], "items": [], "github": {},
       "watch": [{"repo": r, "number": n, "source": "sample"} for r, n in WATCH]}
seq = 0
for at, project, text, summary, items in ENTRIES:
    eid = f"demo-e{len(doc['entries']) + 1}"
    entry = {"id": eid, "at": at, "text": text, "summary": summary, "project": project,
             "source": "sample", "items": []}
    for kind, label, quote, due, extra in items:
        assert norm(quote) in norm(text), f"quote not in update: {quote!r}"
        seq += 1
        item = {"id": f"demo-i{seq}", "kind": kind, "text": label, "quote": quote, "due": due,
                "project": extra.get("project", project), "who": "",
                "status": "done" if kind == "done" else "open", "entry": eid, "source": "sample",
                "created": at}
        if extra.get("repo"):
            item["repo"], item["number"] = extra["repo"], extra["number"]
        doc["items"].append(item)
        entry["items"].append(item["id"])
    doc["entries"].insert(0, entry)
said = {(i["project"], i["due"]) for i in doc["items"] if i["kind"] == "deadline"}
for project, label, due in DEADLINES:
    if (project, due) in said:
        continue
    seq += 1
    doc["items"].append({"id": f"demo-i{seq}", "kind": "deadline", "text": label, "quote": "", "due": due,
                         "project": project, "who": "", "status": "open", "entry": None,
                         "source": "sample", "created": "2026-10-18T12:00:00+05:30"})
OUT.write_text(json.dumps(doc, ensure_ascii=False, indent=1), encoding="utf-8")
print(f"demo.json: {len(doc['entries'])} entries, {len(doc['items'])} items, {len(doc['watch'])} PRs")
