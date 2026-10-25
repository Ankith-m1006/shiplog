# ShipLog: plan to win (23 Oct -> final form edit 30 Oct 23:59 IST)

Goal: top 3 + best Builders project (results 6 Nov).

## What the research says

- **Judges** (wemakedevs.org/wispr/judges): a real problem with a user who would keep using it · Wispr used meaningfully ("part of the build AND the workflow") · a live link that works · a clear 2-minute demo. Usage card + feedback = 30%.
- **Ideas page** (wemakedevs.org/wispr/ideas): "The best entry fixes a problem from your own work." Run it on **real data**, fix its mistakes by talking them through with Flow, and **show the real output** (their examples: "the bills it made for a real day of sales", "a morning of mail it sorted").
- **Wispr Flow today:** works in every app on Mac/Windows/iPhone/Android, including the **phone keyboard**; Dictionary (learns names and terms); **Snippets** (spoken shortcuts that expand to text); Styles (tone per app); Command Mode (edit selected text by voice, Pro); Scratchpad; claims speaking is 3-5x faster than typing. **No public API** — so ShipLog meets Flow where it really lives: as text that Flow types.

## The idea that wins: ShipLog is *speech-native*

Typed updates are short and tidy. Spoken updates are long, messy, self-correcting and full of tone. ShipLog is built for the second kind, so **it works better the more you talk**, and with a keyboard there is no reason to use it. Every feature below is chosen because it only makes sense with Flow.

## Features (ranked)

1. **Brain-dump mode (core).** Talk for 1-2 minutes about your whole day; ShipLog turns it into 10-20 checked items. Handles what only speech has:
   - self-corrections: "due Tuesday, no wait, Wednesday" -> Wednesday, shown as "you corrected this";
   - hedges: "I think", "maybe" -> item marked *unsure*, asked once in review;
   - urgency in tone: "this one is really urgent" -> priority;
   - spoken numbers: "twenty one six ninety four" -> #21694.
   Shows "142 words: about 1 min talking vs ~3.5 min typing" for each update.
2. **Auto-read when Flow finishes.** Flow types the whole utterance in one burst; when the box stops changing, ShipLog reads it. Talk, let go, review appears. Hands-free.
3. **Talk to edit.** The same box takes spoken commands, so the whole log runs by voice: "mark the Amazon one done", "push the DEV post to Tuesday", "drop the flcarre rule", "what's left today?". No buttons needed; every change still shows a confirm.
4. **Flow tune-up (Wispr-only).** ShipLog compares what Flow typed with names it knows for sure (your GitHub repos, PR titles, reviewer handles, project names) and catches misheard words ("Shiplock" -> ShipLog, "Falter DB" -> FalkorDB). It fixes them in the log and gives you a one-copy list to add to your **Flow Dictionary**, plus suggested **Flow Snippets** (e.g. say "ship update" -> a template). ShipLog makes Flow better for you over time.
5. **Capture from anywhere on the phone.** A ShipLog Telegram bot: open the chat, use the Flow keyboard, talk. Updates land in your log and the bot replies with what it understood + a confirm link. Uses Flow's mobile keyboard, which is how people really use Flow on the go.
6. **More than GitHub.** GitHub: merged PR -> item done automatically; new review / failing CI on your PR -> "needs you". GitLab merge requests (public API, same flow). Live calendar: a subscribe link (webcal) so deadlines appear in Google Calendar and stay updated, no login.
7. **Speak once, ship everywhere.** From your log: today's stand-up, a weekly report, and a #NoHandsChallenge-style post draft, each with the quotes it came from. Drafts only; ShipLog never sends.
8. **Proof page (real results).** Opt-in, read-only share of my real log + numbers: updates spoken, words, items, PRs tracked, follow-ups that rules stopped, deadlines met. Plus an **eval**: 40+ of my real spoken updates, hand-labelled, accuracy of items/dates/quotes, before and after the speech-native parser. This is exactly the "show real output" the ideas page asks for.

## Day by day (Claude builds; Ankith talks)

| Day | Build | Ankith |
|---|---|---|
| Fri 23 | ✅ DONE 09:28 (fae45cd, live rev 00006): 1 brain-dump parser (corrections, hedges, urgency, spoken numbers, take-backs) + 2 auto-read; 44 tests | use ShipLog for real by voice tonight; keep raw updates |
| Sat 24 | ✅ DONE EARLY 23 Oct 09:37 (live): 3 talk-to-edit (done/move/drop/reopen by voice, history kept) + spoken questions go to Ask; 51 tests | a 2-min end-of-day brain dump |
| Sun 25 | ✅ DONE EARLY 23 Oct 09:51 (live): 4 Flow tab: misheard names vs known names + fix in review, Dictionary list + copy, add your words, repo Snippets, words said + time saved; 57 tests | add the suggested words to Flow; screenshot before/after |
| Mon 26 | ✅ DONE EARLY 23 Oct 10:05 (live): 6 Needs you (failing checks, changes requested, new comments + seen), merge -> items done with history, GitLab MRs via public API, Google Calendar subscribe (private token); 62 tests | subscribe the calendar on phone |
| Tue 27 | ✅ DONE EARLY 25 Oct (rev 00017): 5 Telegram capture bot @shiplog_ankith_bot: one-time link from Today ties the chat to your log; reads like the web page, replies with items + your words, Save/Discard buttons; questions answered from the log; strangers get a demo copy; webhook secret checked; 68 tests | link the bot from Today, talk to it daily |
| Wed 28 | ✅ DONE EARLY 23 Oct 13:25 (live): 7 stand-up / weekly / post drafts from the log, cited + number-checked, also by voice ('write my stand-up'); 68 tests | use the post draft for a real #NoHandsChallenge post |
| Thu 29 | 8 proof page + eval (40+ real updates); bug bash on phone + desktop | record the new demo (Claude records desktop, Ankith voices) |
| Fri 30 | Update the form: new video, About, fresh usage card, feedback | press save before 23:59 |

## Rules kept
- Gemini only; code checks every quote; nothing saved without confirm; never sends messages.
- Every feature: tests + e2e green before deploy; live link always works for a stranger with no sign-up.
- Secrets server-side only (.github-oauth, .owner-key, bot token). Rotate the GitHub OAuth secret after 30 Oct.

Sources: wemakedevs.org/wispr/ideas, wemakedevs.org/wispr/judges, wisprflow.ai/post/developer-tools, wisprflow.ai/post/vibe-coding-tutorial, sidsaladi.substack.com/p/wispr-flow-101-the-complete-guide, releasebot.io/updates/wispr-flow.
