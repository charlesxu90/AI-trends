# CLAUDE.md

Guidance for Claude Code when working in this repository.

## Working Principles

Behavioral guidelines to reduce common LLM coding mistakes. These bias toward caution over speed; for trivial tasks, use judgment.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them — don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Ask: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it — don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

### 5. Decompose Before Long Runs

**Verify cheaply before committing expensive compute. Decompose to the smallest verifiable units.**

Before running any long-execution task (multi-hour sweep, 30-seed benchmark, full dataset training, large download):
- Break the goal into the smallest tasks that can be verified quickly. A 30-seed sweep decomposes into: data-loads-OK → one-seed-runs-OK → 5-seed-completes-OK → 30-seed-sweep.
- Run the cheap checks first. A 5-second smoke test catches 90% of bugs that would otherwise waste a 10-hour sweep.
- Only commit to the long run after every cheap check passes.
- Prefer staged decomposition: verify the data pipeline → verify one method × one seed → verify N methods × one seed → verify one method × N seeds → full sweep.

The test: before kicking off anything that runs longer than a few minutes, ask "what's the cheapest test that would have caught a failure here?" — and run that first.

This applies recursively. If a subtask itself is long, decompose it further.

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, clarifying questions come before implementation rather than after mistakes, and long runs no longer fail at hour 9 of 10 because of a bug a one-seed smoke test would have caught.


## What this project is

Tracks trending topics across AI conferences (CVPR, ICCV, ICML, ICLR, NIPS).
Papers are crawled into per-conference CSVs, each paper is assigned topic labels,
and per-year top / emerging / fading topics are derived. Final trend tables live
in `README.md`.

The project is being automated: the manual keyword→topic curation is replaced by
an AI skill over deterministic CLI tools. See `AUTOMATION.md` for the full
pipeline and `.claude/prds/` + `.claude/plans/` for requirements and plans.

## Critical environment rule

The user's `~/.local/lib/python3.10/site-packages` leaks broken/incompatible
packages. **Always** run the project tools isolated from user site-packages,
using the repo-local Python 3.10 venv:

```bash
PYTHONNOUSERSITE=1 ./env/bin/python ...
PYTHONNOUSERSITE=1 ./env/bin/ai-trend ...
PYTHONNOUSERSITE=1 ./env/bin/python -m pytest --cov=ai_trend
```

The scispaCy stack is **fragile and version-pinned** (scispaCy 0.5.1 + spaCy
3.4.4 + numpy 1.23.5 + setuptools<81). Exact pins are in `requirements-lock.txt`.
Do not upgrade numpy/spaCy/setuptools without re-verifying the model loads. The
spaCy model is loaded by local path (`data/spacy-en_core_sci_lg-0.5.1`), never by
pip name.

Recreate the env:

```bash
conda create -y -p ./env python=3.10
PYTHONNOUSERSITE=1 ./env/bin/pip install -e . --no-deps
PYTHONNOUSERSITE=1 ./env/bin/pip install -r requirements-lock.txt
```

## Architecture

```
config/                     single source of truth (version-controlled)
  taxonomy.json             topic -> [keywords]
  useless_keywords.json     noise blocklist
  other_keywords.json       real-but-unmapped keywords (ledger)

ai_trend/                   tested, deterministic Python package
  taxonomy.py               load / validate / immutably-merge config
  candidates.py             scispaCy NER candidate extraction
  assign.py                 substring topic matcher (the core labeling)
  curate_io.py              build curation payload; parse + apply AI decisions
  trends.py                 top/emerging/fading per conference-year + markdown render
  registry.py               configurable conference registry (M3)
  site.py                   export static-site JSON for GitHub Pages (M4)
  ingest.py                 merge crawled JSON -> per-conference CSV (M5)
  crawl.py                  config-driven OpenReview Scrapy wrapper (M5)
  curate_ai.py              headless AI curation via Anthropic API (M5)
  refresh.py                full-pipeline orchestrator (M5)
  cli.py                    candidates|curate|assign|trends|export-site|crawl|process|refresh

config/conferences.json                 tracked conferences (label, tokens, month)
config/crawl.json                       OpenReview crawl jobs (venue/domain per cycle)
.github/workflows/pages.yml             deploy docs/ to Pages on push
.github/workflows/refresh.yml           monthly pipeline -> opens a PR (M5)
.claude/skills/curate-topics/SKILL.md   the AI reasoning step (only non-deterministic part)
scripts/migrate_notebook_taxonomy.py    regenerate config/* from the notebook
scripts/check_agreement.py              verify assignment vs committed labels
tests/                      pytest suite (target >=80% coverage; currently ~94%)

data/{year}/{N}_{conf}.csv              source papers (gitignored)
data/{year}/{N}_{conf}.csv_topics.csv   labeled output (adds `topic` column)
data/trends/trends.json                 computed trends (M2 output, gitignored)
docs/                                   static GitHub Pages site (committed)
docs/data/                              site JSON: manifest, trends, paper shards
*.ipynb                                  original/legacy pipeline (still present)
```

Pipeline: `candidates → /curate-topics skill → curate → assign → trends →
export-site`. Only the skill reasons; everything else is pure and reproducible.

## Site (Milestone 4)

Static, no framework. `ai-trend export-site` writes `docs/data/` (manifest +
trends + per-conference-year paper shards, abstracts truncated). `docs/index.html`
+ `docs/assets/{app.js,style.css}` render a trends dashboard and a drill-down
paper browser. `docs/` (incl. generated `docs/data/`, ~23 MB) is committed so
Pages can serve it. Enable: Settings → Pages → branch `main`, folder `/docs`.
Re-run `export-site` after any re-assign/trends change.

## Hard constraints (do not break)

- **Faithful assignment semantics.** `assign.py` reproduces the notebook exactly:
  search text is `f"{title.lower()} {abstract.lower()|None}"`; keywords are matched
  as **case-sensitive substrings** (so uppercase keywords never match — a
  deliberate, preserved quirk). Topics join with `;` in **taxonomy insertion
  order**. The deterministic port matches committed 2024+2025 labels at 100% over
  15,327 papers — keep it that way (`scripts/check_agreement.py`).
- **Output schema is frozen.** `*_topics.csv` columns:
  `title,year,source,authors,class,keywords,abstract,pdf_link,topic`. Downstream
  (trend computation, future site) depends on this.
- **Config is the source of truth.** Never hand-edit `config/*.json`; go through
  `ai-trend curate` so validation runs. The package only *adds* topics/keywords —
  never deletes.
- **Immutability.** `Taxonomy` mutators (`add_keywords`, `add_noise`) return new
  objects; do not mutate in place.

## Coding conventions

- Many small, focused files; functions <50 lines; explicit error handling
  (fail fast with clear messages, never swallow).
- Tests first (TDD); AAA structure; tests needing the scispaCy model self-skip
  when it is absent.
- Run the full suite before declaring work done:
  `PYTHONNOUSERSITE=1 ./env/bin/python -m pytest --cov=ai_trend`

## Trends (Milestone 2)

`ai_trend/trends.py` + `ai-trend trends` compute top/emerging/fading per
conference-year. **Conference-year identity is file-based** (folder = year,
filename prefix = conference); the in-file `source`/`year` columns are NOT trusted
(`10_ICCV` rows carry `source=CVPR`; `2024/5_iclr` mixes years). Change ratio is
`(cur-prev)/prev`. Eligibility (refined to suppress back-labeling noise):
emerging needs `prev >= min_prev` (default 1) AND `cur >= min_count` (default 10);
fading needs only `prev >= min_prev`. Verified to reproduce README 2025 ICLR
exactly under defaults.

## Known follow-ups

- **History was re-labeled.** 2021–2023 `*_topics.csv` have been re-assigned with
  the unified taxonomy so trends are comparable year-over-year. The README trend
  tables are hand-written and now lag `data/trends/trends.json`; regenerate them
  via `ai-trend trends --format markdown` when desired (some README pre-2025 rows,
  e.g. 2024 ICLR top-5, appear copy-pasted/stale).
- Git: `data/` and `env/` are gitignored. Commit/push only when the user asks.
```
