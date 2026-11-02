# freelance-listings-source

Daily freelance job listings import pipeline for Marc Adrian's freelance-opportunities job board.

This repo holds the **source code** for the daily 10:00 AM Asia/Kuala_Lumpur scheduled import that pulls new listings from two sources, dedupes against the Notion freelance database, writes new rows, and sends a summary notification.

## Contents

| File | Purpose |
|---|---|
| `scrape_oj_fu.py` | Source B — onlinejobs.ph scraper (curl login, 7 keyword searches) + FreeUp board via ego-browser task space. Scope-filter, dedupe vs Notion, REST write. Run with `--import`. |
| `build/import_newsletters.py` | Source A — newsletter parser (FFO Oct 9 + TWJN 283 example). Decodes issues, parses listings into Notion rows, dedupes, writes. |
| `state.json` | Import history + dedupe state. Source of truth for what's been imported. |
| `oj_fu_state.json` | Source B run state (last run, imported IDs). |
| `oj_fu_candidates.json` | Last Source B candidate output. |
| `HANDOFF-TO-OPENBOT.md` | Complete handover bundle for Openbot — full task instructions, schedule config, failure modes, credentials, history, expansion guide. |

## Schedule

The import runs as schedule `409285a6-87d5-415e-91dd-2bd7a3764878` ("Daily freelance listings import") on Ziggy's Vellum assistant:
- **Cadence:** Every day at 10:00 AM Asia/Kuala_Lumpur
- **Next run:** check with `assistant schedules get 409285a6-87d5-415e-91dd-2bd7a3764878`
- **Timeout cap:** 30 min (1800000 ms)

## Running Source A (newsletters)

Requires the `newsletter-listings-to-notion` skill loaded. Steps:

1. Search Gmail for newest issue from each sender (`freelanceopportunities@mail.beehiiv.com`, `thewritersjob@mail.beehiiv.com`) not yet imported (compare vs `state.json`).
2. Decode each issue (plain part preferred, HTML fallback) with `extract-newsletter.py`.
3. Parse listings into rows per field mapping (Position = `<org> — <role>`, Category, Type, Status=Active, Source URL, Pay, Deadline, Location, Issue Date, etc.).
4. Dedupe against Notion database `3eaa198a-6ad6-8130-992f-dc88084d1f11` (skip existing org/role).
5. Write new rows via `notion-create-pages` (parent data_source_id).
6. Update `state.json`.

## Running Source B (job boards)

```bash
cd scratch/freelance-list && python3 scrape_oj_fu.py --import
```

Handles everything: onlinejobs.ph login from vault creds (`onlinejobs.ph:username/password`), 7 keyword searches, FreeUp via ego-browser task space `freeup`, scope filter (AI/automation/web design/content/sales/marketing/social media), dedupe vs Notion, Notion REST writes. Prints `imported N rows` at the end.

## Notification (always send, merge both sources)

```
assistant notifications send --source-channel scheduler --title "Freelance listings import" \
  --message "Imported N new listings (newsletters: N1; onlinejobs.ph: N2; FreeUp: N3) into your Notion database."
```

## Handover

See `HANDOFF-TO-OPENBOT.md` — the complete handover bundle for Openbot, covering schedule config, both sources, state file, notifications, failure modes, credentials inventory, full history (Oct 1 → today), and how to expand/add sources.

## Related repos

- `marcpadz/freelance-opportunities-board` — GitHub Pages frontend fed by this Notion DB
- `marcpadz/OpenBot` — AG-UI coworker platform (this handover's target)