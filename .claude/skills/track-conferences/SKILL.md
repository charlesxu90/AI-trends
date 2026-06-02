---
name: track-conferences
description: >-
  Watch tracked AI conferences and ingest them as their papers go live. For the
  current and next year, web-search each conference's date; when a conference is
  within ~3 months, check (web search + `ai-trend probe`) whether its accepted
  papers are published on OpenReview/thecvf; if so, ingest and analyze it and
  update CONFERENCES.md. Use for the monthly/scheduled conference-watch run.
---

# Track Conferences (web-search driven watch)

Encodes the running logic: **discover dates → wait until ~3 months out → check if
papers are published → ingest & analyze**. You (Claude) drive this using your
**web search** tools plus the deterministic CLI. Run from the repo root with
`PYTHONNOUSERSITE=1 ./env/bin/ai-trend ...`.

## Inputs
- `today` — the current date (from the environment).
- `config/conferences.json` — tracked venues (label, source, openreview_group, month).
- `CONFERENCES.md` — the maintained table of dates + source URLs (state of record).

## Procedure

### 1. Scope: current & next year, what's unprocessed
- Compute the current year and next year from `today`.
- Run `ai-trend check-sources` to see which conference-years already have a source
  URL, and `ls data/<year>/` to see what's already ingested.
- Build the worklist: tracked conferences for {current year, next year} that are
  **not yet ingested**.

### 2. Discover dates (WebSearch)
For each worklist item missing a date in `CONFERENCES.md`:
- **WebSearch** e.g. `"<Conference> <year> dates"` / `"<Conference> <year> accepted papers"`.
- Read the official site (WebFetch) to confirm the conference date / camera-ready /
  proceedings date.
- Record the date into `CONFERENCES.md` (add the row if absent).

### 3. Window check: is it ~3 months away?
- If the conference date is **more than 3 months in the future**, do nothing now
  (it'll be re-checked next run). Stop here for that item.
- If it is **within 3 months (or already passed)** and not yet ingested, proceed.

### 4. Are the papers published?  (web search + probe)
- Deterministic check first:
  ```bash
  PYTHONNOUSERSITE=1 ./env/bin/ai-trend probe <CONF> <year>
  ```
  It constructs the expected source URL (OpenReview `content.venueid` or
  thecvf `<CONF><YEAR>?day=all`) and reports `AVAILABLE (N papers)` or `not yet`.
- If `probe` says not yet, **WebSearch/WebFetch** the venue (OpenReview group page,
  thecvf, or the official proceedings) in case the URL pattern changed this cycle.
  If you find a working URL, update `CONFERENCES.md` with it.
- If still nothing is published, stop (re-check next run).

### 5. Ingest & analyze
When papers are available, run the full pipeline (see the `add-conference` skill):
```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend ingest-url "<the live URL>"
# then: candidates -> curate (curate-topics) -> assign -> trends -> export-site
```
Then fetch citations for the new conference-year's emerging-topic papers
(`ai-trend citations ... --scope emerging`) if desired, and snapshot
(`ai-trend snapshot-citations`).

### 6. Record & publish
- Update `CONFERENCES.md`: ensure the row has the date + the working URL.
- Open a PR with the regenerated data/site (and the CONFERENCES.md update).

## Notes
- Only the **date discovery** and **fallback URL discovery** use web search; the
  availability check and ingestion are deterministic CLI tools.
- New venues (not in `config/conferences.json`) need an entry first
  (key/label/tokens/month/source/openreview_group).
- Be conservative: never ingest a partially-posted venue — re-check next run if the
  paper count looks far below the expected size.
