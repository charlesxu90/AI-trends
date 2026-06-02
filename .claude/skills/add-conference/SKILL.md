---
name: add-conference
description: >-
  Add a conference-year to AI-Trend from a single URL (OpenReview group/venue URL,
  or an openaccess.thecvf.com CVPR/ICCV URL). Runs the whole pipeline: download
  paper metadata, extract + curate topics, assign labels, optionally fetch citation
  counts, regenerate trends and the GitHub Pages site, and open a PR. Use when the
  user pastes a conference URL and asks to add/track it.
---

# Add Conference (URL → full pipeline)

The natural-language front door. The user gives a URL; you run the pipeline by
calling `ai-trend` subcommands and doing the topic-curation reasoning yourself
(the same judgement as the `curate-topics` skill).

All commands run from the repo root, isolated from user site-packages:

```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend ...
```

## Inputs
- `URL` — e.g. `https://openreview.net/group?id=ICML.cc/2025/Conference` or
  `https://openaccess.thecvf.com/CVPR2024?day=all`.
- Optionally whether to fetch citations (slow; default ask the user).

## Procedure

### 1. Download metadata
```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend ingest-url "$URL"
```
This detects the source (OpenReview vs thecvf), downloads, and writes
`data/<year>/<month>_<key>.csv`. Note the printed path as `$CSV`. (CVPR/ICCV have
no abstracts — that's expected.)

### 2. Extract + curate topics  (your reasoning — like curate-topics)
```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend candidates "$CSV" \
  --conference "$CONF" --year "$YEAR" -o /tmp/candidates.json
```
Read `/tmp/candidates.json`; for every candidate decide `existing` / `new` /
`noise` / `other` (anchor on existing topics, prefer existing, lowercase keywords,
be conservative with new). Write `/tmp/decision.json`, then:
```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend curate --dry-run /tmp/decision.json
PYTHONNOUSERSITE=1 ./env/bin/ai-trend curate /tmp/decision.json
```
(See the `curate-topics` skill for the full decision rubric.)

### 3. Assign topics
```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend assign "$CSV"
```
For cross-year trend consistency after a taxonomy change, also re-assign the other
years (re-run `assign` on each `*_topics.csv`, or re-migrate + re-assign as in
AUTOMATION.md) — mention this to the user; it re-labels existing years.

### 4. Citations (optional, slow — ask first)
Semantic Scholar is unauthenticated and rate-limited (~1 paper/sec, frequent 429s),
so this is bounded to the conference-year's top/emerging-topic papers and cached:
```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend citations "${CSV}_topics.csv"
```
Resumable — safe to re-run. Skip if the user doesn't want to wait.

### 5. Trends + site
```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend trends --include-counts -o data/trends/trends.json
PYTHONNOUSERSITE=1 ./env/bin/ai-trend export-site   # picks up citations sidecars
```
Optionally regenerate the README (`ai-trend trends --format markdown`).

### 6. Verify + PR
Smoke-check the new conference-year appears (manifest shard + browsable), then open
a PR (`/pr`) summarising the added venue, new topics, and any citations. Merging
republishes the site via the Pages workflow.

## Notes
- Source detection + venue/year come from the URL via `ai_trend/sources.py` and the
  conference registry (`config/conferences.json`, with a `source` field).
- New conferences must exist in the registry; if the URL's venue isn't there, add it
  to `config/conferences.json` first (key/label/tokens/month/source).
- Do not hand-edit `config/*.json` topics — always go through `ai-trend curate`.
