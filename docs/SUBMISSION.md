# ShipLog: submission pack (No Hands: The Wispr Challenge)

Form: https://www.wemakedevs.org/wispr/submit (all 7 fields required; editable until Fri 30 Oct, 23:59 IST).

| # | Field | Value | Who |
|---|---|---|---|
| 1 | Project name | ShipLog | ready |
| 2 | Track | Builders | ready |
| 3 | Live link | https://shiplog-1037019152152.asia-south1.run.app (no sign-up; each visitor gets their own copy of the demo) | ready |
| 4 | Demo video (≤ 2 min, unlisted YouTube or Loom) | record from the script below | Ankith |
| 5 | About | below | ready (read it once, change anything that isn't how you'd say it) |
| 6 | Wispr usage card | Wispr Flow → Insights → Your usage → Share (image, ≤ 5 MB) | Ankith |
| 7 | Feedback on Wispr Flow | in your own words; real notes from the build below to pick from | Ankith |

Repo: https://github.com/Ankith-m1006/shiplog

## 5. About

**Problem.** I run ten hackathons at once, plus open pull requests on Kestra, claims waiting for maintainers and reviewers I must not ping twice. All of it lived in one long markdown tracker that I updated by hand after every step. Updating it broke my flow, and when I skipped it I missed follow-ups and nearly missed deadlines.

**Who it's for.** Developers and hackathon builders juggling many repos, PRs and deadlines, who would rather talk than type.

**What ShipLog does.** I talk an update through Wispr Flow. ShipLog pulls out what's done, what's due, who to chase and the rules I set ("don't ping the JDBC reviewer again"), shows the exact words each item came from, and saves only what I confirm. Then it shows what needs me this week, the live GitHub status of every PR I mentioned, follow-up drafts that refuse to break my rules, and answers questions about my own work only from what I saved, with the quote. If it isn't in my log, it says so instead of guessing.

**How Wispr Flow was used.** Flow is the input: ShipLog has no microphone code, Flow types into it on my phone and laptop like into any other app. The whole project was built by voice too: the spec, every prompt to my coding assistant, review notes and the daily #NoHandsChallenge posts were dictated. Flow turned run-on, half-corrected speech into clean text with lists, numbers and PR ids intact, which is exactly what a tracker needs.

## 4. Demo video script (about 1:50)

1. **0:00-0:15 The problem.** Scroll the giant TRACKER.md. "Ten hackathons, open PRs, reviewers I must not ping twice. Updating this by hand broke my flow every time."
2. **0:15-0:45 Capture.** Phone, ShipLog open, hold the Flow key and say a real update: "Opened the editor font fix as PR 21694 on Kestra today. The DEV week three post is due Monday at noon. Don't ping flcarre about the CI re-run." Tap Read it.
3. **0:45-1:05 Review.** Show the three items, each with "you said" and the date worked out from "Monday at noon". "The model proposes, code checks every quote. Nothing is saved until I say so." Save.
4. **1:05-1:25 Today.** Overdue, due this week, the new rule, and the PR list with live GitHub states ("checked 19:37"). Tap Draft follow-up on a PR covered by a rule: it refuses, quoting the rule.
5. **1:25-1:45 Ask.** "Who should I not ping right now?" Answer with both quotes and dates. Then "Did PR 21628 get merged?" → "That isn't in your log yet, so I won't guess."
6. **1:45-1:55 Close.** Wispr usage card on screen. "Built and used entirely by voice. Live link in the description, no sign-up."

## 7. Feedback notes from the build (real, from this project's messages)

- **Worked:** long spoken briefs (a 6-step plan for a whole night) arrived numbered and in order; spoken counts came out as digits; PR numbers like #21376 came out right once said as numbers.
- **Got in the way:** project names it hadn't seen ("ShipLog" → "Shiplock", "FalkorDB" → "Falter DB", "WeMakeDevs" → "Vmac dose"), "hashtag 203" typed as words, and it once wrote its own name as "Whisper Flows". The dictionary fixed most of these once added.
- **Want next:** (write your own)
