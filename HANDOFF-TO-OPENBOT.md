# Openbot Handover: Daily Freelance Listings Import

**Copy/paste this entire file + the prompt below to Openbot.** It contains everything needed to take over Marc Adrian's daily freelance job listings import task.

---

## The task

Every weekday at 10:00 AM Asia/Kuala_Lumpur, import new freelance job/listing opportunities from two sources into Marc Adrian's Notion freelance-opportunities database, then send a one-line notification summarizing counts per source.

**Schedule ID:** `409285a6-87d5-415e-91dd-2bd7a3764878` ("Daily freelance listings import")
**Cadence:** Every day at 10:00 AM Asia/Kuala_Lumpur (`0 10 * * *`)
**Timeout cap:** 30 min (1800000 ms)
**Next run:** check with `assistant schedules get 409285a6-87d5-415e-91dd-2bd7a3764878`

---

## Source A — Newsletters (from Gmail to Notion)

**Account:** `thelowkeymarketer@gmail.com` (Google OAuth must be ACTIVE — verify with `assistant oauth status google`)

**Senders:**
- `freelanceopportunities@mail.beehiiv.com` → "Freelance Opportunities!" (FFO)
- `thewritersjob@mail.beehiiv.com` → "The Writer's Job News" (TWJN)

**Steps:**
1. For each sender, search Gmail newest-first (`labelIds:INBOX`). Take the latest issue **not yet imported** — compare against `state.json`'s `imported_issues` list.
2. Decode each new issue: plain text part preferred, HTML fallback.
3. Parse listings into rows with this field mapping:
   - Position = `<org> — <role>`
   - Category = Writers / Designers / Developers / Video / Audio / Other
   - Type = Full-time / Part-time / Fellowship / Grant / Hourly / Freelance / Other
   - Status = Active
   - Source URL, Pay, Deadline, Location, Issue Date, Newsletter URL, Source Details, Verified = false
4. Dedupe against Notion DB — skip any org/role already present. Use `scrape_oj_fu.notion_existing()` which returns `(urls, titles)` sets.
5. Write new rows via Notion REST: `assistant oauth request --provider notion -X POST https://api.notion.com/v1/pages`
   - Parent database: `3eaa198a-6ad6-8130-992f-dc88084d1f11`
   - Database title: "📚 Freelance Opportunities — Website Headless"
   - If `notion-create-pages` errors with `pages: expected array, received undefined`, delegate the write to a builder subagent.
6. Update `state.json` with newly imported issues.

**Skill to load:** `newsletter-listings-to-notion` — load it first and follow its current instructions.

---

## Source B — Job boards (`scrape_oj_fu.py`)

Run: `cd scratch/freelance-list && python3 scrape_oj_fu.py --import`

**What it does:**
1. **onlinejobs.ph:** Login via vault creds (`onlinejobs.ph:username/password`, reveal with `assistant credentials reveal --service onlinejobs.ph --field <field>`), curl POST `/authenticate` with csrf-token. Search 7 keywords: ai, automation, web design, content, sales, marketing, social media. Parse cards: title, type, posted date, description, tags, pay, URL. Dedupe within-run by slug.
2. **FreeUp:** Opens ego-browser task space `freeup`, fetches `timeclock.freeeup.com/project/boardv2` in-page with cookies. If session dead (lands on /login), tries clicking Login on pre-filled form, otherwise skips gracefully — no CDP anywhere.
3. **Both sources:** Scope filter (AI/automation/web design/content/sales/marketing/social media — category by first-match wins). Dedupe against Notion DB. Write new rows via Notion REST. Print `imported N rows` at end.
4. Candidates land in `oj_fu_candidates.json`. Updates `oj_fu_state.json` with `last_run` and `imported_ids`.

**FreeUp note:** Skipped when ego session is dead. Report "FreeUp: skipped (no session)" — don't block the run.

---

## Notification (always send, merge both sources)

```
assistant notifications send --source-channel scheduler --title "Freelance listings import" \
  --message "Imported N new listings (newsletters: N1; onlinejobs.ph: N2; FreeUp: N3) into your Notion database."
```

- Nothing new: "No new freelance listings since the last import."
- Source failure: say which one and why.
- Verify sends with `assistant notifications list` — a send can ERROR even when delivered; don't re-send blindly.

---

## State file — `scratch/freelance-list/state.json`

Source of truth for what's imported. Last real import: 2026-10-27 (TWJN Pro 185 = 2 rows; onlinejobs.ph = 55 new rows; FreeUp skipped). Runs on Oct 30, Oct 31, Nov 1 were all blocked — nothing imported, dedupe state unchanged.

Key shape:
```json
{
  "last_run": "ISO timestamp",
  "imported_issues": [{ sender, newsletter, issue, issue_date, gmail_id, imported, rows_imported, note }],
  "latest_seen": { "FFO": "...", "TWJN": "..." },
  "job_boards": { "last_check": "date", "result": "...", "onlinejobs_ph": "..." },
  "failed_runs": [ { date, reason } ],
  "last_oj_fu_run": { "run_at", "onlinejobs_ph_rows_imported", "freeup" }
}
```

---

## Failure modes & recovery

| Symptom | Cause | Fix |
|---|---|---|
| `assistant oauth request --provider google` → "missing assistant ID" | Platform base URL resolving to localhost:8000 | `assistant config set platform.baseUrl https://platform.vellum.ai` |
| python3 blocked on non-interactive turns | Permission gate | Run Source B from an interactive turn |
| OAuth spinner "stuck in waiting" but connection landed | Surface lie | Verify with `assistant oauth status <provider>` + `assistant oauth ping <provider>` |
| oauth request body > ~1 MiB | Proxy caps bodies | Shrink payload under ~1 MiB |
| DELETE via oauth proxy returns empty stdout | 204 = success | Treat empty stdout on DELETE as success |
| Schedule runs <1s "error" | Token-mint handshake dying fast | Same fix: set platform.baseUrl |
| `assistant schedules runs <UUID>` | Needs full UUID | Always use full UUID, not short ID |

Never trust a UI spinner or top-of-list schedule status — check `assistant schedules runs <full-uuid>`.

---

## Credentials inventory

| Service | Where | How |
|---|---|---|
| Google (thelowkeymarketer@gmail.com) | OAuth connection | `assistant oauth status google` |
| Notion | OAuth connection | `assistant oauth request --provider notion` |
| onlinejobs.ph | Vault | `assistant credentials reveal --service onlinejobs.ph --field username\|password` |
| FreeUp | None stored | Ego-browser session only; skipped if no live session |

---

## Files to read first

All under `scratch/freelance-list/`:
1. `state.json` — import history + dedupe state (read first)
2. `scrape_oj_fu.py` — Source B script, read before modifying
3. `build/import_newsletters.py` — Source A parse logic
4. `oj_fu_state.json` / `oj_fu_candidates.json` — Source B run state

---

## Full timeline (Oct 1 → today)

- **Oct 1–2:** Pipeline concept born; outreach-site-recon (curl + for loops, ~40 checks in a dozen calls) developed on EmPower You + TOPPAN audits.
- **Oct 3:** First bulk import — FFO Oct 3 issue (118 rows) + TWJN issues into Notion DB.
- **Oct 4:** Marc's work night — 124-row Notion import done, board repo public + Pages wired. Count bug fixed (246/246, commit 1cda8da2). Lesson: his reported numbers are mental models, verify live first.
- **Oct 27:** Last successful full daily run — TWJN Pro 185 (2 rows) + onlinejobs.ph (55 new rows after dedupe vs 1,836 existing). FreeUp skipped.
- **Oct 28–29:** Source B migrated from raw CDP to ego-browser bridge (task space `freeup`, in-page `page.fetch`). FreeUp still skipped — no vault creds, session expired.
- **Oct 30–31:** Daily runs blocked — Google OAuth "missing assistant ID", then python3 permission-gated.
- **Nov 1:** OAuth fixed (config-level). New blocker: python3 still permission-gated on non-interactive turns.
- **Nov 2 (today):** Schedule last ran OK (2026-11-01T02:00 UTC). 10:00 AM MYT run due soon.

---

## Expansion guide

**Add a newsletter source:** Add sender email → fetch newest issue → decode (plain > HTML) → parse to field mapping → dedupe vs Notion → write rows → update state.json.

**Add a job board:** Write scraper (curl for public pages, ego-browser for login-gated — follow FreeUp pattern: task space, in-page fetch, graceful skip) → scope filter with same CATS regex list → dedupe → write via Notion REST → update `oj_fu_state.json` → update schedule message to include new source in notification merge.

---

## Related repos

- `marcpadz/freelance-opportunities-board` — GitHub Pages frontend fed by this Notion DB
- `marcpadz/OpenBot` — AG-UI coworker platform (your platform)
- `marcpadz/freelance-listings-source` — this pipeline's source code (just pushed)

---

## Quick commands to open

```
assistant schedules get 409285a6-87d5-415e-91dd-2bd7a3764878
assistant oauth status google
assistant oauth status notion
assistant credentials reveal --service onlinejobs.ph --field username
cat scratch/freelance-list/state.json
cd scratch/freelance-list && python3 scrape_oj_fu.py --import
```

---

**Human-required steps for you:**
1. Verify Google OAuth is ACTIVE before the first run.
2. Confirm onlinejobs.ph vault creds exist (`onlinejobs.ph:username/password`).
3. Watch the first 10:00 AM MYT run once — confirm both sources import and notification sends.

---

## Prompt to give Openbot

Paste this to Openbot along with the file above:

> I'm handing over the daily freelance listings import task. The full instructions are in the attached markdown file (HANDOFF-TO-OPENBOT.md). Please:
> 1. Read the file and confirm you understand the schedule, both sources (newsletters + job boards), state file, notification format, and failure modes.
> 2. Verify Google OAuth and onlinejobs.ph vault creds are available.
> 3. Run the next scheduled import (Source A newsletters first, then Source B scrape_oj_fu.py --import).
> 4. Send the merged notification and update state.json.
> 5. Report back per-source counts and any failures.

> The source code is also on GitHub at https://github.com/marcpadz/freelance-listings_source if you need to clone it.

---

**File location:** `scratch/freelance-list/HANDOFF-TO-OPENBOT.md` (also pushed to GitHub at marcpadz/freelance-listings-source)