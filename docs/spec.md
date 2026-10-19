# ShipLog: design spec

Written 19 Oct 2026. Builders track, No Hands: The Wispr Challenge (WeMakeDevs × Wispr Flow).

## The problem (real, mine)

I run many things at once: 10+ hackathons with different deadlines, open pull requests on Kestra plugins, claims waiting for maintainers, reviewers I must not ping twice. All of it lives in one long markdown tracker that I update by hand after every step. Updating it interrupts the work, and when I skip it I miss deadlines and forget follow-ups.

**User:** a developer or hackathon builder juggling many repos, PRs and deadlines, who would rather talk than type.

## What ShipLog does

I talk a messy update through Wispr Flow (phone or laptop). ShipLog turns it into a clean log entry, tasks, deadlines, PR links and "don't do this" rules. I check and edit what it understood, then save. After that it answers "what needs me this week?", shows live PR status from GitHub, and drafts follow-ups that respect my rules. It never posts or sends anything.

## Screens (phone-first, one page)

1. **Capture.** A big text box (Wispr types into it). "Read it" sends it to Gemini. The review card lists every extracted item (log line, task, deadline, PR, follow-up, rule) with the exact words it came from. Each item can be edited or removed. "Save" stores the confirmed items and the original text.
2. **Today.** Due this week (IST), overdue, open follow-ups, and watched PRs with live GitHub state (open/merged, review decision, CI), each marked "from GitHub, checked <time>". Unknown status is shown as unknown, not failure.
3. **Log.** A timeline of entries; each shows the clean summary and, on tap, the original spoken words. Search and project filter. Edit and delete.
4. **Ask.** Free questions answered only from saved records (and the last GitHub check), each answer citing the entries it used. Follow-up drafts for a PR or person, editable, with a Copy button.

Plus: deadlines as an `.ics` download (a real calendar file; ShipLog does not claim to send reminders).

## Trust rules (these are the product)

- **Every extracted item carries a quote** from the update; code checks the quote is really in the text. An item whose quote is not found is dropped and shown as "couldn't trace". PR numbers and dates must also appear in, or be resolvable from, the text.
- Dates: relative dates ("tomorrow", "next Wednesday") resolve against the capture time in IST; if it can't be resolved, it stays "unresolved" and the user picks.
- Labels on every fact: **you said** (from a capture), **GitHub** (fetched, with time), **sample** (demo seed).
- Rules ("don't ping Malay again", "claims paused until merges") are stored and the follow-up drafter must obey them; a draft for something blocked by a rule is refused with the reason.
- Text in updates and GitHub content is data, never instructions.

## Architecture

- **Backend:** Python FastAPI, one service on Cloud Run (asia-south1), same pattern as DawaiGraph.
- **AI:** Gemini (`gemini-3.5-flash`) over REST with a JSON response schema; validated with pydantic; one retry on bad output; clear error if the key is missing or rate-limited.
- **Storage:** one JSON document per workspace behind a small `Store` interface: local files in dev, a Cloud Storage bucket in production.
- **Workspaces, no sign-up:** each browser gets a random workspace key (sent as `X-Workspace`) and starts with its own copy of the demo data; "Reset demo" restores it. My real workspace uses a long private key set as a server secret, never in the repo.
- **GitHub:** read-only REST on public repos (optional server-side token for rate limit), cached 5 minutes.
- **Frontend:** one static `index.html` with vanilla JS, white, clean, large tap targets.

## Demo data

A public-safe copy of my real October: hackathon deadlines, my real public Kestra PRs (their live status comes from GitHub, so it is real), log entries rewritten without secrets, file paths or anyone else's details.

## Out of scope (for now)

Login, multiple users per workspace, sending messages, auto-posting, push reminders, any write to GitHub.

## Build order

- **Day 1 (19 Oct):** repo, store, workspaces, extraction + quote check, review card, save, log, demo seed, tests.
- **Day 2 (20 Oct):** Today view, GitHub live status, follow-up drafts with rules, `.ics`.
- **Daily after:** Ask, polish, my real daily use, deploy, README, demo video (28 Oct), submit 29 Oct.

## Tests

Unit tests for date resolution, quote tracing, schema validation, rule-blocked drafts and workspace isolation; an end-to-end Playwright run of capture → review → save → log on a phone viewport.
