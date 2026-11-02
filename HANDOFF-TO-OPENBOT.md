# Freelance Listings Import — Handover to Openbot

**Purpose:** Daily import of new freelance job/listing opportunities from two sources into Marc Adrian's Notion freelance-opportunities database, which feeds his public job board at `marcpadz.github.io/freelance-opportunities-board`.

**Taken over by:** Openbot (external agent), via Offhand MCP task  
**Handed over by:** Ziggy (Marc's assistant on Vellum)  
**Date:** Nov 2, 2026 (~07:53 MYT)

---

## 1. What this task does (one sentence)

Every weekday morning at 10:00 AM Asia/Kuala_Lumpur it pulls new issues of two newsletter sources (Freelance Opportunities! + The Writer's Job News) from Gmail, scrapes two job boards (onlinejobs.ph + FreeUp), dedupes everything against the existing Notion rows, writes only the genuinely-new listings into Notion, and sends a one-line notification summarizing counts per source.

---

## 2. The schedule (live config)

| Field | Value |
|---|---|
| Schedule ID | `409285a6-87d5-415e-91dd-2bd7a3764878` |
| Name | Daily freelance listings import |
| Cadence | Every day at 10:00 AM Asia/Kuala_Lumpur (`0 10 * * *`) |
| Next run | 2026-11-02T02:00:00.000Z |
| Last status | ok (ran 2026-11-01T02:00 UTC) |
| Mode | execute (script runs in a sandbox turn) |
| Timeout cap | 30 min (1800000 ms) — split the work if it approaches that |
| Retries | 3 max, 1m backoff |

The full schedule message (the authoritative run instructions) is embedded in the schedule record. Read it with `assistant schedules get 409285a6-87d5-415e-91dd-2bd7a3764878`.

---

## 3. Source A — Newsletters (from Gmail to Notion)

### Account
`thelowkeymarketer@gmail.com` — Google OAuth must be active. The connection was repaired Oct 31 by setting `assistant config set platform.baseUrl https://platform.vellum.ai` (previously every OAuth request failed with "missing assistant ID" because the CLI resolved the platform base URL to localhost:8000). Verify with `assistant oauth status google` before running.

### Senders + what to fetch
- `freelanceopportunities@mail.beehiiv.com` → "Freelance Opportunities!" (FFO)
- `thewritersjob@mail.beehiiv.com` → "The Writer's Job News" (TWJN)

For each sender, search Gmail newest-first, take the latest issue **not yet imported** (compare against `state.json`'s `imported_issues` list). Check `labelIds:INBOX` to get the received copy.

### Decode + parse
Decode each new issue: plain text part preferred, HTML fallback. Parse listings into rows using this field mapping:
- **Position** = `<org> — <role>`
- **Category** = one of Writers / Designers / Developers / Video / Audio / Other (per the section header mapping in `build/import_newsletters.py`)
- **Type** = Full-time / Part-time / Fellowship / Grant / Hourly / Freelance / Other
- **Status** = Active
- **Source URL**, **Pay**, **Deadline**, **Location**, **Issue Date**, **Newsletter URL**, **Source Details**, **Verified** = false

### Dedupe
Query the Notion database and skip any org/role already present. Use `scrape_oj_fu.notion_existing()` which returns `(urls, titles)` sets.

### Write to Notion
Parent database: `3eaa198a-6ad6-8130-992f-dc88084d1f11`  
Data source collection: `collection://3eaa198a-6ad6-81d7-bb7c-000bae85ee04`  
Database title: "📚 Freelance Opportunities — Website Headless"  
Write via `notion-create-pages` (parent data_source_id). If it errors with `pages: expected array, received undefined`, delegate the write to a builder subagent (per the skill's failure-modes reference).

### Skill to load
`newsletter-listings-to-notion` — load it first and follow its current instructions over this note. Its `extract-newsletter.py` does the decode/parse step.

### State update
After a successful run, update `scratch/freelance-list/state.json` with the newly imported issues (sender, newsletter, issue, issue_date, gmail_id, imported timestamp, rows_imported, note).

---

## 4. Source B — Job boards (scrape_oj_fu.py)

Run: `cd scratch/freelance-list && python3 scrape_oj_fu.py --import`

### What the script does (end to end, no hand-holding needed)

**onlinejobs.ph:**
1. Login via vault creds (`onlinejobs.ph:username` + `password`), curl POST to `/authenticate` with csrf-token from the login page.
2. Search 7 keywords: ai, automation, web design, content, sales, marketing, social media.
3. Parse cards: title, type, posted date, description, tags, pay, URL.
4. Dedupe within-run by slug, dedupe across keywords.

**FreeUp:**
1. Opens an ego-browser task space named `freeup`, fetches `https://timeclock.freeeup.com/project/boardv2` in-page (session cookies ride along).
2. If the session is dead (lands on /login), tries clicking Login on a pre-filled form; otherwise skips FreeUp gracefully — **no CDP anywhere**.
3. Parses tickets into rows.

**Then both sources together:**
- Scope filter: keep only rows matching AI / automation / web design / content / sales / marketing / social media (category assigned by first-match wins).
- Dedupe against Notion DB (URLs + titles).
- Write new rows via Notion REST (`assistant oauth request --provider notion ...`).
- Print `imported N rows` at the end.
- Candidates land in `oj_fu_candidates.json`.
- Updates `oj_fu_state.json` with `last_run` and `imported_ids`.

### Vault creds needed
- `onlinejobs.ph:username` + `onlinejobs.ph:password` (revealed via `assistant credentials reveal --service onlinejobs.ph --field <field>`)

### FreeUp note
FreeUp is skipped when the ego session is dead. That's expected behavior — report it as "FreeUp: skipped (no session)" and don't block the run on it.

---

## 5. Notification (always send, merge both sources)

```
assistant notifications send --source-channel scheduler --title "Freelance listings import" \
  --message "Imported N new listings (newsletters: N1; onlinejobs.ph: N2; FreeUp: N3) into your Notion database."
```

- If nothing new anywhere: "No new freelance listings since the last import."
- If a source fails, say which one and why.
- Verify sends with `assistant notifications list` — a send can ERROR even when delivered; don't re-send blindly.

---

## 6. State file — scratch/freelance-list/state.json

This is the source of truth for what's been imported. Key shape:

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

Last real import: 2026-10-27 (TWJN Pro 185 = 2 rows; onlinejobs.ph = 55 new rows; FreeUp skipped).  
Runs on Oct 30, Oct 31, and Nov 1 were all blocked (OAuth "missing assistant ID" then python3 permission-gated) — nothing imported, dedupe state unchanged.

---

## 7. Failure modes & recovery

| Symptom | Cause | Fix |
|---|---|---|
| `assistant oauth request --provider google` → "missing assistant ID" | `VELLUM_ENVIRONMENT=local` makes the CLI resolve platform base URL to localhost:8000 | `assistant config set platform.baseUrl https://platform.vellum.ai` (global fix, heals every process) |
| python3 blocked on non-interactive turns | Permission gate: bash with args/compounds denied outside interactive client | Run Source B from an interactive turn, or split into bare commands |
| OAuth spinner shows "stuck in waiting" but connection already landed | Surface lie | Verify with `assistant oauth status <provider>` + `assistant oauth ping <provider>` |
| `assistant oauth request` body > ~1 MiB | Proxy caps request bodies | Shrink payload under ~1 MiB; resumable upload (X-Goog-Upload-URL) not possible through proxy |
| DELETE via oauth proxy returns empty stdout | 204 = success | Treat empty stdout on DELETE as success, not failure |
| Schedule runs <1s "error" | Token-mint handshake dying fast (localhost bug) | Same fix as first row: set platform.baseUrl |
| `assistant schedules runs <UUID>` | Needs full UUID, short ID returns "Schedule not found" | Always use the full UUID |

Never trust a UI spinner or a schedule's top-of-list status row — check the full run history with `assistant schedules runs <full-uuid>`.

---

## 8. Credentials inventory

| Service | Where stored | How to access |
|---|---|---|
| Google (thelowkeymarketer@gmail.com) | OAuth connection | `assistant oauth status google`; `assistant oauth request --provider google` |
| Gmail (marcpadz@gmail.com) | OAuth connection | `assistant oauth request --provider google --account marcpadz@gmail.com` |
| Notion | OAuth connection | `assistant oauth request --provider notion` |
| onlinejobs.ph | Vault | `assistant credentials reveal --service onlinejobs.ph --field username\|password` |
| FreeUp | Vault | None stored — ego-browser session only; skipped if no live session |

---

## 9. Files you should read first

All under `scratch/freelance-list/`:

| File | What it is |
|---|---|
| `state.json` | Import history + dedupe state (read this first) |
| `scrape_oj_fu.py` | Source B script — full logic, read before modifying |
| `build/import_newsletters.py` | Source A example parse logic (FFO Oct 9 + TWJN 283) |
| `outreach-notes.md` | Cold-outreach drafts (TOPPAN, EmPower You, Poppy) — related but separate task |
| `oj_fu_candidates.json` | Last Source B candidate output |
| `oj_fu_state.json` | Last Source B run state |
| `toppan-audit.md`, `empower-you-audit.md` | Site audits behind the outreach notes |

Related workspace files:
- `memory/concepts/notion-freelance-db.md` — Notion DB structure, field conventions
- `memory/concepts/freelance-board-site.md` — GitHub Pages board, 246/246 rows live
- `memory/concepts/cold-outreach-campaign.md` — Outreach campaign status

---

## 10. History — from first import to today

This is the full timeline of the freelance-listings pipeline, from the day it started being populated until the most recent sync:

**Oct 1–2, 2026** — Pipeline concept born. Marc's first working session: cold outreach became my first real task. The outreach-site-recon procedure (single `curl` calls, batched with `for` loops, ~40 checks in a dozen calls) was developed on EmPower You and TOPPAN audits.

**Oct 3, 2026** — First bulk import of the Freelance Opportunities! newsletter (Oct 3 issue, 118 rows) and TWJN issues into the Notion database. The `ffo_oct15_*` and `FFO_OCT3_*` files date from this wave.

**Oct 4, 2026** — Marc's longest work night (~03:34–07:45 MYT): the 124-row Notion import completed, then the board repo was made public + GitHub Pages wired. The count bug (reported "144 posts" but live count was 122) was fixed end to end: Notion CLI OAuth connected via the card he tapped, `jobs.ts` regenerated, commit `1cda8da2`, **live at 246 of 246**. Pattern learned: his reported numbers are mental models, not observations — verify live first.

**Oct 27, 2026** — Last successful full daily run: TWJN Pro 185 (2 free-preview rows) + onlinejobs.ph (55 new rows after dedupe vs 1,836 existing Notion URLs; 210 cards across 7 keywords, 105 kept, 21 dropped by scope filter). FreeUp skipped (no CDP session).

**Oct 28–29, 2026** — Source B (scrape_oj_fu.py) migrated from raw CDP to the ego-browser bridge (task space `freeup`, in-page `page.fetch` of timeclock.freeeup.com/project/boardv2). FreeUp still skipped — vault has no FreeUp creds, session expired in ego profile.

**Oct 30–31, 2026** — Daily runs blocked: Google OAuth "missing assistant ID" (platform base URL bug), then python3 permission-gated. Notifications sent (signals 6e50b685, 4658f236).

**Nov 1, 2026** — Google OAuth FIXED (config-level). New blocker: python3 still permission-gated on non-interactive turns, so neither Source A decode/parse nor scrape_oj_fu.py could run. FFO Oct 30 issue and TWJN 286 fetched fine but not imported.

**Nov 2, 2026 (today)** — Schedule last ran OK (2026-11-01T02:00 UTC, 1m 46s). The 10:00 AM MYT run is due in ~2 hours. Everything is staged and ready; the only thing standing between Openbot and a clean run is restoring the interactive python3 path (or running Source B interactively).

---

## 11. Continuous improvement — how to expand and maintain

### Add a new newsletter source
1. Add the sender email to the Source A list.
2. Fetch newest issue, decode (plain > HTML), parse to the same field mapping.
3. Dedupe against Notion (urls + titles).
4. Write rows, update state.json.

### Add a new job board
1. Write a scraper (curl for public pages, ego-browser for login-gated ones — follow the FreeUp pattern: task space, in-page fetch, graceful skip if session dead).
2. Scope-filter with the same CATS regex list.
3. Dedupe, write via Notion REST, update `oj_fu_state.json`.
4. Update the schedule message to include the new source in the notification merge.

### Maintenance checklist (run it on each fire)
- [ ] Verify Google + Notion OAuth active (`assistant oauth status <provider>`)
- [ ] Verify state.json is current (last_run matches the last successful import)
- [ ] Run Source A (newsletters) first — it has the newest signal
- [ ] Run Source B (`python3 scrape_oj_fu.py --import`)
- [ ] Send the merged notification
- [ ] Update state.json with both sources' results
- [ ] If anything failed, record it in `failed_runs` and notify Marc

### The cold-outreach thread (related, not part of this task)
Outreach notes are drafted in `outreach-notes.md` (TOPPAN, EmPower You, Poppy). Each has a `{{PROOF}}` slot waiting on Marc's proof-point number + his pick of 2 targets. Nothing has been sent. This is a separate task from the listings import — don't conflate them.

---

## 12. What Openbot needs from Marc (human-required steps)

1. **Offhand auth** — the offhand MCP server is `needs-auth`; the task fire requires the `mcp__offhand__*` surface in an interactive turn. I could not authenticate it from shell (`assistant mcp auth offhand` timed out / needs callback_base_url).
2. **Google OAuth** — verify `assistant oauth status google` is ACTIVE before the first run.
3. **onlinejobs.ph vault creds** — confirm `onlinejobs.ph:username` and `password` are in the vault (they were used successfully on Oct 27).
4. **First run supervision** — watch the 10:00 AM MYT run once, confirm both sources import and the notification sends.

---

## 13. Quick commands to open

```
assistant schedules get 409285a6-87d5-415e-91dd-2bd7a3764878
assistant oauth status google
assistant oauth status notion
assistant credentials reveal --service onlinejobs.ph --field username
cat scratch/freelance-list/state.json
cd scratch/freelance-list && python3 scrape_oj_fu.py --import
```

---

**End of bundle.** Questions or pivots — ping me (Ziggy) on the vellum channel. I don't re-litigate abandoned paths; if Marc changes direction, just go the new way.