# ShipLog

**Talk through your work. ShipLog keeps the log, the deadlines and the follow-ups.**

Built for *No Hands: The Wispr Challenge* (WeMakeDevs × Wispr Flow), Builders track, 16-30 Oct 2026. Every prompt, spec note and commit message for this project is dictated through Wispr Flow.

I juggle ten hackathons, open pull requests and reviewers I must not ping twice, all in one long markdown tracker I update by hand. ShipLog lets me say the update instead: it pulls out what's done, what's due, who to chase and the rules I set, shows me exactly which of my words each item came from, and saves only what I confirm.

- **Every item is traced to your words.** Gemini proposes; code checks each quote is really in the update and drops anything it can't trace.
- **Dates are worked out by code, in IST**, from the words you said ("Friday night", "next Wednesday"); if they're ambiguous they stay unresolved.
- **Nothing is sent or posted.** Follow-ups are drafts you copy.

Status: in progress (day 1, 19 Oct). Design: [docs/spec.md](docs/spec.md).

## Run it

```bash
python -m venv .venv && .venv/Scripts/pip install -r requirements.txt   # Windows; use .venv/bin on macOS/Linux
set GEMINI_API_KEY=...            # never commit it
python data/make_demo.py          # rebuilds the demo seed
.venv/Scripts/python -m uvicorn server:app --app-dir app --port 8791
.venv/Scripts/python -m pytest tests
```
