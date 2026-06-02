# AI-Trend Automation (Milestones 1–2)

Milestone 1: automated topic assignment. Milestone 2: automated trend computation.



Replaces the manual keyword→topic curation in `1.assign_topics.ipynb` with an
AI agent (Claude Code as the reasoning core) plus deterministic CLI tools. The
curated taxonomy is preserved; assignment stays reproducible.

## Pipeline

```
papers.csv ─▶ ai-trend candidates ─▶ candidates.json
            ─▶ /curate-topics skill (Claude decides noise/existing/new/other)
            ─▶ ai-trend curate decision.json ─▶ updates config/*.json
            ─▶ ai-trend assign ─▶ papers.csv_topics.csv   (deterministic)
```

- **Source of truth:** `config/taxonomy.json` (topic → keywords),
  `config/useless_keywords.json` (noise blocklist), `config/other_keywords.json`
  (real-but-unmapped keywords parked for later review).
- **Reasoning seam:** `.claude/skills/curate-topics/SKILL.md` — the only
  non-deterministic step; everything else is pure, tested Python.

## Environment

Python 3.10 in a repo-local venv (`env/`). The scispaCy model
(`data/spacy-en_core_sci_lg-0.5.1`) needs the pinned stack in
`requirements-lock.txt`. Always run isolated from user site-packages:

```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend --help
```

Recreate the env:

```bash
conda create -y -p ./env python=3.10
PYTHONNOUSERSITE=1 ./env/bin/pip install -e . --no-deps
PYTHONNOUSERSITE=1 ./env/bin/pip install -r requirements-lock.txt
```

## Commands

```bash
# 1. Extract candidate keywords for a new conference-year
PYTHONNOUSERSITE=1 ./env/bin/ai-trend candidates data/2025/5_iclr.csv \
    --conference iclr --year 2025 -o /tmp/candidates.json

# 2. Curate: run the skill (autonomous), or apply a hand-checked decision file
PYTHONNOUSERSITE=1 ./env/bin/ai-trend curate /tmp/decision.json

# 3. Assign topics (deterministic; writes <csv>_topics.csv)
PYTHONNOUSERSITE=1 ./env/bin/ai-trend assign data/2025/5_iclr.csv

# 4. Compute trends across all conference-years (Milestone 2)
PYTHONNOUSERSITE=1 ./env/bin/ai-trend trends --include-counts -o data/trends/trends.json
PYTHONNOUSERSITE=1 ./env/bin/ai-trend trends --format markdown   # README-style tables
```

## Trends (Milestone 2)

`ai-trend trends` computes **top / emerging / fading** topics per conference-year
into `data/trends/trends.json` (structured) or README-style markdown.

- Identity is **file-based** (folder = year, filename prefix = conference); the
  in-file `source`/`year` columns are unreliable and ignored.
- Definitions: top = top-N by count; emerging/fading = top-N by highest/lowest
  change ratio `(cur-prev)/prev` vs the same conference one year earlier.
- Eligibility (refined from the notebook to suppress back-labeling noise):
  emerging needs `prev >= --min-prev` (default 1; keeps the ratio finite) **and**
  `cur >= --min-count` (default 10; real current volume). Fading needs only
  `prev >= --min-prev` (a fading topic shrinks toward zero, so no current floor).
  Tune via `--min-prev` / `--min-count`; lower them for small/sparse venues.
- Verified to reproduce the README 2025 ICLR table (top/emerging/fading) exactly
  under the default thresholds.
- **Cross-year consistency requires one taxonomy across all years.** The 2021–2023
  `*_topics.csv` were re-assigned with the unified taxonomy for this reason; without
  that, stale baselines make newer topics spuriously "emerge."

## Provenance & verification

- `scripts/migrate_notebook_taxonomy.py` regenerates `config/*.json` by executing
  the notebook's dict-building cells (faithful, not retyped).
- `scripts/check_agreement.py` diffs a fresh `topic` column against a committed
  `*_topics.csv`. The deterministic port reproduces the 2024 + 2025 labels at
  **100%** (15,327 papers) — the conference-years the final notebook regenerated.

## Tests

```bash
PYTHONNOUSERSITE=1 ./env/bin/python -m pytest --cov=ai_trend
```

43 tests, 95% coverage. Tests that need the scispaCy model self-skip when absent.

## Conference registry (Milestone 3)

The tracked conferences live in `config/conferences.json` (label + filename
tokens). Adding a venue is a config edit — no code change. `ai_trend/registry.py`
loads it; trends/site discovery read conference identity from it.

## GitHub Pages site (Milestone 4)

```bash
# Rebuild the site's data (after re-assigning topics / trends)
PYTHONNOUSERSITE=1 ./env/bin/ai-trend export-site   # writes docs/data/*
```

- `ai_trend/site.py` exports `docs/data/manifest.json`, `docs/data/trends.json`,
  and per-conference-year shards `docs/data/papers/<LABEL>_<year>.json` (abstracts
  truncated to ~240 chars; shards loaded on demand).
- The site is static (`docs/index.html` + `docs/assets/`): a trends dashboard
  (top/emerging/fading + a counts bar chart) and a paper browser (filter by
  venue/year/topic, full-text search, PDF links). Clicking any topic drills into
  its papers. No framework/build step.
- **Enable Pages:** GitHub repo → Settings → Pages → "Deploy from a branch" →
  branch `main`, folder `/docs`. The site then serves at the Pages URL.
- Verified with a headless smoke test (no JS errors; drill-down, filters, and
  conference switching all work against the real data).

## Monthly unattended refresh (Milestone 5)

End-to-end orchestration: **crawl → process → assign → AI-curate → trends → export-site**.

```bash
# Deterministic core only (re-derive labels/trends/site from existing data):
PYTHONNOUSERSITE=1 ./env/bin/ai-trend refresh

# Full pipeline (needs ANTHROPIC_API_KEY for curation; valid crawl config):
ANTHROPIC_API_KEY=sk-... PYTHONNOUSERSITE=1 ./env/bin/ai-trend refresh --crawl --curate
```

Stages:
- `ai-trend crawl` — runs OpenReview Scrapy jobs from `config/crawl.json`. **venue/domain
  strings change every cycle and must be updated**; CVPR/ICCV are not on OpenReview
  (CVF, separate/manual). Best-effort: a failed job never aborts the run.
- `ai-trend process` — merges crawled JSON → `data/<year>/<month>_<key>.csv`
  (tolerates concatenated-array JSON; de-dupes by title).
- `ai-trend assign` — deterministic topic labels (M1).
- AI curation — `ai_trend/curate_ai.py` does the `curate-topics` reasoning headless
  via the Anthropic API (`ANTHROPIC_API_KEY`); skipped gracefully if unavailable.
- `ai-trend trends` / `export-site` — M2 / M4 outputs.

`ai-trend refresh` is idempotent: with no new data it just re-derives outputs, so a
scheduled run is safe anytime (produces no diff when nothing changed).

### Scheduled workflow → PR

`.github/workflows/refresh.yml` runs monthly (cron `0 6 1 * *`) + manual dispatch:
sets up the pinned env, pip-installs the scispaCy model (`en_core_sci_lg`) and
`anthropic`/`scrapy`, runs `refresh --crawl --curate`, and **opens a PR** with the
regenerated `config/`, `data/**_topics.csv`, `docs/`, and `README` for review.
Merging triggers the Pages deploy.

**Setup required:** add repo secret `ANTHROPIC_API_KEY`, and enable
Settings → Actions → General → "Allow GitHub Actions to create and approve pull
requests". Keep `config/crawl.json` venue strings current.

## URL-driven ingestion (Milestone 6)

Add a conference-year from a single URL — driven in natural language via the
**`add-conference`** Claude Code skill, or directly:

```bash
# OpenReview (auto-discovers venues by venue id — no hand-maintained venue strings):
PYTHONNOUSERSITE=1 ./env/bin/ai-trend ingest-url "https://openreview.net/group?id=ICML.cc/2025/Conference"

# thecvf (CVPR/ICCV):
PYTHONNOUSERSITE=1 ./env/bin/ai-trend ingest-url "https://openaccess.thecvf.com/CVPR2024?day=all"

# add --full to also assign + trends + export with the current taxonomy
```

- `ai_trend/sources.py` detects the source (host) and extracts conference+year,
  resolved against the registry's `source` field (`openreview` | `cvf`).
- `ai_trend/openreview.py` paginates api2 `/notes?content.venueid=<id>` and derives
  `class` from each note's venue (oral/spotlight/poster).
- `ai_trend/cvf.py` scrapes `openaccess.thecvf.com/<CONF><YEAR>?day=all`
  (requests + BeautifulSoup; CVPR/ICCV have no abstracts).
- Needs the `web` extra: `pip install -e '.[web]'` (requests + beautifulsoup4).

### Citations (Semantic Scholar)

```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend citations data/2025/7_icml.csv_topics.csv
```

- Bounded to the conference-year's **top + emerging** topic papers (or `--topics`),
  **cached** (`<csv>.citations.json`, resumable), with retry/backoff.
- Unauthenticated S2 is slow (~1 paper/sec, frequent 429s) — runs as a separate
  opt-in step. `0` (zero citations) is distinct from `null` (lookup failed).
- `export-site` automatically surfaces cached citations: a count badge on paper
  cards and a "Most cited" sort.

## Notes / known follow-ups

- 2021–2023 `*_topics.csv` have been re-assigned with the unified taxonomy (done in
  M2) so cross-year trends are comparable.
- The README trend tables are still hand-written and now lag
  `data/trends/trends.json`; regenerate with `ai-trend trends --format markdown`
  when you want them refreshed.
- **CVPR / ICCV crawl** is not automated (CVF source, not OpenReview) — those
  years are added manually for now.
- **Crawl venue strings** in `config/crawl.json` need per-cycle maintenance; the
  scheduled run degrades gracefully when they're stale (no new data → no PR).
