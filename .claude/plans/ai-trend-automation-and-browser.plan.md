# Plan: AI-Trend Automation — Automated Topic Assignment

**Source PRD**: `.claude/prds/ai-trend-automation-and-browser.prd.md`
**Selected Milestone**: Milestone 1 — Automated topic assignment
**Complexity**: Medium

## Summary
Replace the manual keyword→topic curation step in `1.assign_topics.ipynb` with an AI agent (Claude Code as reasoning core, packaged as a skill + CLI tools), while keeping the existing deterministic substring matcher and the curated taxonomy. The notebook's accreted Python dicts (`topic2keywords`, `useless_kw`) are migrated to versioned JSON as the single source of truth; deterministic logic is extracted into a tested `ai_trend` package with a CLI; a `curate-topics` skill lets Claude turn spaCy candidate keywords + example papers into taxonomy extensions autonomously. Output `*_topics.csv` files stay byte-compatible in schema (`topic` column, `;`-joined multi-label) so Milestones 2 (trends) and 4 (site) are unaffected.

## Architecture (confirmed approach: automate keyword curation)
```
config/
  taxonomy.json            topic -> [keywords]      (migrated from notebook, version-controlled)
  useless_keywords.json    [noise keywords]         (migrated from notebook)

ai_trend/                  new tested Python package
  candidates.py            spaCy NER candidate extraction (from obtain_cadidate_keywords)
  assign.py                substring matcher (from obtain_topic_for_text / assign_topics)
  taxonomy.py              load / validate / merge taxonomy + blocklist JSON
  curate_io.py             build curation prompt (candidates + example papers); parse + merge AI response
  cli.py                   `ai-trend candidates|assign|curate` entrypoints

.claude/skills/curate-topics/SKILL.md   the AI reasoning step Claude runs

Flow per conference-year:
  csv ─▶ ai-trend candidates ─▶ candidates.json
       ─▶ [curate-topics skill: Claude reasons] ─▶ merge into config/taxonomy.json + useless_keywords.json
       ─▶ ai-trend assign ─▶ <csv>_topics.csv   (deterministic, reproducible)
```

## Patterns to Mirror
| Category | Source | Pattern |
|---|---|---|
| Topic logic | `1.assign_topics.ipynb` (`obtain_topic_for_text`, `assign_topics`, `obtain_cadidate_keywords`) | Substring multi-label match over `title+abstract` lowercased; spaCy `en_core_sci_lg` NER for candidates. Port verbatim into `ai_trend/`, do not redesign the matching semantics. |
| File naming | `data/{year}/{N}_{conf}.csv` → `..._topics.csv`; conf prefixes `5_iclr`, `6_cvpr`, `7_icml`, `10_ICCV`, `12_nips` | CLI must read/write these exact names so existing data and downstream code keep working. |
| CSV schema | `data/2025/5_iclr.csv_topics.csv:1` | Columns `title,year,source,authors,class,keywords,abstract,pdf_link` + appended `topic` (`;`-joined). Preserve exactly. |
| spaCy model | `data/spacy-en_core_sci_lg-0.5.1` | Load the local model by path (`spacy.load("data/spacy-en_core_sci_lg-0.5.1")`), not by pip name. |
| Python pkg layout | `data/scrapy_crawl/scrapy_crawl/` (only existing package) | Plain package with `__init__.py`; no framework. Mirror this minimalism. |
| Tests | none exist | No test pattern in repo — this plan establishes `tests/` with pytest (AAA structure per ECC testing rules). State explicitly: net-new. |

## Files to Change
| File | Action | Why |
|---|---|---|
| `config/taxonomy.json` | CREATE | Single source of truth for topic→keywords, migrated from notebook dicts (incl. all per-year accretions). |
| `config/useless_keywords.json` | CREATE | Migrated noise blocklist. |
| `ai_trend/__init__.py` | CREATE | Package marker. |
| `ai_trend/taxonomy.py` | CREATE | Load/validate/merge taxonomy + blocklist; enforce no duplicate keyword across topics. |
| `ai_trend/candidates.py` | CREATE | Port `obtain_cadidate_keywords` + `count_keywords` + `get_keyword_by_spacy`; emit candidates.json with counts + example titles. |
| `ai_trend/assign.py` | CREATE | Port `obtain_topic_for_text` / `assign_topics`; read a CSV, write `*_topics.csv`. |
| `ai_trend/curate_io.py` | CREATE | Build the curation prompt payload from candidates; parse Claude's JSON decision and merge into config (with `other` bucket for genuinely-new topics). |
| `ai_trend/cli.py` | CREATE | `ai-trend candidates|assign|curate` subcommands. |
| `.claude/skills/curate-topics/SKILL.md` | CREATE | The AI reasoning step: instructs Claude to classify each candidate keyword as noise, existing-topic, or new-topic-proposal, anchored on the taxonomy. |
| `scripts/migrate_notebook_taxonomy.py` | CREATE | One-shot: import the notebook dicts and dump to the two JSON files (run once, kept for provenance). |
| `tests/test_taxonomy.py`, `tests/test_assign.py`, `tests/test_candidates.py`, `tests/test_curate_io.py` | CREATE | Unit coverage ≥80% for deterministic logic + prompt builder/parser. |
| `pyproject.toml` | CREATE | Declare `ai-trend` console script + deps (pandas, spacy, scispacy model path) + pytest config. |
| `requirements.txt` | UPDATE | Add `pandas`, `pytest`; pin what the package needs (currently missing pandas). |
| `1.assign_topics.ipynb` | UPDATE (later) | Leave intact for M1; optionally add a cell that calls the new package so the notebook stays runnable. Not required to ship M1. |

## Tasks
### Task 1: Migrate taxonomy + blocklist to JSON
- **Action**: Write `scripts/migrate_notebook_taxonomy.py` to reproduce the notebook's final `topic2keywords` and `useless_kw` (after all `update_topic2keywords` / `.update()` calls) and dump to `config/taxonomy.json` and `config/useless_keywords.json`. Verify the dumped taxonomy reproduces the same topic set seen in existing `*_topics.csv`.
- **Mirror**: The exact dict contents in `1.assign_topics.ipynb` — no manual re-typing; execute the notebook's dict-building code.
- **Validate**: `python scripts/migrate_notebook_taxonomy.py && python -c "import json; t=json.load(open('config/taxonomy.json')); assert 'graph' in t and 'llm' in t and len(t)>40"`

### Task 2: Extract deterministic assignment into `ai_trend` (tests first)
- **Action**: Port `obtain_topic_for_text` / `assign_topics` into `ai_trend/assign.py` reading config JSON; port candidate extraction into `ai_trend/candidates.py`. Write `tests/test_assign.py` + `tests/test_candidates.py` first (RED), then implement (GREEN).
- **Mirror**: Substring multi-label semantics and lowercasing exactly as in the notebook; local spaCy model path.
- **Validate**: `pytest tests/test_assign.py tests/test_candidates.py -q`

### Task 3: Reproducibility check against existing labels
- **Action**: Run `ai-trend assign data/2025/5_iclr.csv` with the migrated config and diff the `topic` column against the committed `data/2025/5_iclr.csv_topics.csv`. Expect near-identical labels (this proves the port is faithful before any AI touches it).
- **Mirror**: PRD success metric "topic-assignment agreement with prior manual labels".
- **Validate**: A `scripts/check_agreement.py` that reports % identical `topic` rows; target ≥99% (deterministic port should be ~100%).

### Task 4: Build the CLI
- **Action**: Implement `ai_trend/cli.py` with `candidates <csv> [--threshold N] [-o candidates.json]`, `assign <csv> [-o out.csv]`, `curate <candidates.json> <decision.json>` (applies a decision file to config). Register console script `ai-trend` in `pyproject.toml`.
- **Mirror**: File-naming conventions; error handling per ECC rules (fail fast with clear messages on missing file / bad schema; never silently swallow).
- **Validate**: `ai-trend candidates data/2025/5_iclr.csv -o /tmp/c.json && ai-trend assign data/2025/5_iclr.csv -o /tmp/t.csv && head -1 /tmp/t.csv | grep -q ',topic'`

### Task 5: Build the `curate-topics` skill (the AI reasoning core)
- **Action**: Write `.claude/skills/curate-topics/SKILL.md` instructing Claude to: read `candidates.json` (keyword, count, example titles), and for each candidate decide one of {`noise` → add to blocklist, `existing:<topic>` → map to a taxonomy topic, `new:<name>` → propose a new emerging topic}, defaulting genuinely-novel-but-unmapped keywords to an `other` bucket rather than forcing a fit. Output a `decision.json` consumed by `ai-trend curate`. `ai_trend/curate_io.py` builds the prompt payload and validates/merges the decision (reject duplicate keywords, preserve existing taxonomy entries).
- **Mirror**: PRD decisions — fully autonomous, keep taxonomy, anchor new topics as proposals. Risk mitigation: "unlabeled/other" bucket.
- **Validate**: `pytest tests/test_curate_io.py -q` (prompt builder produces valid payload; parser rejects malformed/duplicate decisions; merge is idempotent). Manual: run the skill on 2025 ICLR candidates and confirm a sane `decision.json`.

### Task 6: End-to-end autonomous dry run
- **Action**: On a fresh checkout of one conference-year, run candidates → curate-topics skill → assign with no manual keyword editing, producing `*_topics.csv`. Record agreement vs the committed file and any new topics the AI proposed.
- **Validate**: `scripts/check_agreement.py` reports agreement; reviewer confirms no manual `topic2keywords` edits were needed (the M1 acceptance criterion).

## Validation
```bash
# Unit + coverage (target >=80% on ai_trend/)
pytest --cov=ai_trend --cov-report=term-missing -q

# Deterministic port faithfulness
python scripts/migrate_notebook_taxonomy.py
ai-trend assign data/2025/5_iclr.csv -o /tmp/iclr2025_topics.csv
python scripts/check_agreement.py data/2025/5_iclr.csv_topics.csv /tmp/iclr2025_topics.csv   # expect ~100%

# Full autonomous slice (no manual keyword curation)
ai-trend candidates data/2025/5_iclr.csv -o /tmp/cand.json
#   -> run /curate-topics skill on /tmp/cand.json -> /tmp/decision.json
ai-trend curate /tmp/cand.json /tmp/decision.json   # merges into config/*.json
ai-trend assign data/2025/5_iclr.csv -o /tmp/iclr2025_ai.csv
```

## Risks
| Risk | Likelihood | Mitigation |
|---|---|---|
| spaCy `en_core_sci_lg-0.5.1` + Python 3.7 env is fragile/old; may not import cleanly in a modern env | Medium | Pin the working env in `pyproject.toml`; keep loading the local model by path; if 3.7 blocks tooling, isolate spaCy to the `candidates` step and let the rest run on a newer interpreter. Flag if upgrade is needed before coding. |
| Migrated JSON taxonomy diverges from notebook dicts (typos, ordering, dup keywords) | Medium | Task 1 generates JSON *by executing* the notebook code, not retyping; Task 3 diffs against committed labels to catch drift. |
| AI curation forces novel keywords into ill-fitting existing topics, skewing trends | Medium | `other` bucket + `new:` proposals instead of forced fit; decisions are version-controlled and diffable before assignment. |
| Multi-label `;` format or column order changes, breaking downstream M2/M4 | Low | Schema assertion test on output; preserve exact column append order. |
| Notebook code has Python-2-ism `df1.append(...)` (removed in pandas 2.x) in trend code | Low | Out of M1 scope (that's M2), but note: port to `pd.concat` when M2 is planned. |

## Acceptance
- [ ] All tasks complete
- [ ] `pytest --cov=ai_trend` ≥ 80%
- [ ] Deterministic re-assignment of an existing conference-year matches committed labels ~100%
- [ ] One conference-year fully labeled via candidates → skill → assign with **zero** manual keyword editing
- [ ] `config/taxonomy.json` + `config/useless_keywords.json` are the single source of truth; notebook dicts no longer hand-edited
- [ ] Output `*_topics.csv` schema byte-compatible with existing files
- [ ] Patterns mirrored (substring semantics, file naming, local spaCy path), not reinvented
