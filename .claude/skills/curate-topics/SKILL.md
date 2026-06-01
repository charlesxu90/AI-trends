---
name: curate-topics
description: >-
  Autonomously curate candidate keywords into the AI-Trend taxonomy. Given a
  conference papers CSV, extract candidate keywords, decide for each whether it
  is noise, belongs to an existing topic, seeds a new emerging topic, or should be
  parked in the "other" bucket, then apply the decision and assign topics. Use
  when adding a new conference-year or refreshing topic assignments.
---

# Curate Topics

You are the reasoning core that replaces the manual keyword→topic curation step in
the AI-Trend pipeline. The deterministic parts (spaCy candidate extraction,
substring assignment) are CLI tools; **your job is the judgement in the middle.**

## Environment

All commands run from the repo root with the project env, isolated from the user
site-packages:

```bash
RUN="PYTHONNOUSERSITE=1 ./env/bin/ai-trend"
```

The taxonomy lives in `config/taxonomy.json` (topic → keyword list) and
`config/useless_keywords.json` (noise blocklist). `config/other_keywords.json` is
the ledger of real-but-unmapped keywords. Treat these as the single source of truth.

## Inputs

- `CSV` — path to the papers file, e.g. `data/2025/5_iclr.csv`
- `CONFERENCE` — short name, e.g. `iclr`
- `YEAR` — e.g. `2025`

## Procedure

### 1. Extract candidates

```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend candidates "$CSV" \
  --conference "$CONFERENCE" --year "$YEAR" -o /tmp/candidates.json
```

Read `/tmp/candidates.json`. It contains:
- `existing_topics` — the current taxonomy topic labels (your anchor set)
- `candidates` — `[{keyword, count, examples}]`, most frequent first

### 2. Decide each candidate

For **every** candidate, choose exactly one action. Use `count` and `examples` to
judge what the keyword actually means in context.

| Action | When | Requires |
|---|---|---|
| `existing` | The keyword is a clear synonym/variant/instance of an existing topic | `topic` ∈ `existing_topics` |
| `new` | A genuinely distinct, substantive research theme not covered by any existing topic, with enough volume to matter (rule of thumb: `count` ≥ 8 and clearly coherent across `examples`) | `topic` (a concise lowercase label) |
| `noise` | Generic ML vocabulary, methodology words, or anything not a research topic (e.g. "approach", "framework", "evaluation", "method") | — |
| `other` | A real, specific concept that is not yet worth its own topic (too niche/rare, or you are unsure). Parks it for later review instead of forcing a bad fit | — |

Decision principles (these encode the project's intent — follow them):
- **Anchor on the existing taxonomy.** Prefer `existing` over `new`. Only create a
  `new` topic when nothing existing fits; this keeps trends comparable year-over-year.
- **Never force a fit.** If a keyword does not clearly belong to an existing topic
  and is not clearly its own theme, use `other`, not a stretched `existing`.
- **Be conservative with `new`.** A handful of new topics per conference-year is
  normal; dozens is a sign you are over-splitting — reconsider toward `existing`/`other`.
- **Keywords are matched case-sensitively against lowercased text.** Always emit
  keywords in **lowercase**, or they will never match any paper.
- **Reuse `topic` labels exactly** as they appear in `existing_topics` (mind the
  existing case-variant labels; pick the one that already carries the most keywords).

### 3. Write the decision

Write `/tmp/decision.json`:

```json
{
  "decisions": [
    {"keyword": "gaussian splatting", "action": "existing", "topic": "splatting"},
    {"keyword": "state space model",  "action": "existing", "topic": "state space model"},
    {"keyword": "test-time training", "action": "new", "topic": "test-time training"},
    {"keyword": "framework",          "action": "noise"},
    {"keyword": "spectral graph",     "action": "other"}
  ]
}
```

Include an entry for **every** candidate — do not silently drop any.

### 4. Apply and verify

```bash
# Preview first
PYTHONNOUSERSITE=1 ./env/bin/ai-trend curate --dry-run /tmp/decision.json
# Then apply (writes config/taxonomy.json, useless_keywords.json, other_keywords.json)
PYTHONNOUSERSITE=1 ./env/bin/ai-trend curate /tmp/decision.json
```

If `curate` reports a `DecisionError` (unknown topic, duplicate keyword, bad
action), fix `/tmp/decision.json` and re-run — do not edit the config by hand.

### 5. Assign topics

```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend assign "$CSV"   # writes <CSV>_topics.csv
```

## Output

Report a short summary: counts per action, any `new` topics created, and how many
keywords were parked in `other`. Surface the `new` topics explicitly so a human can
later confirm they belong in the taxonomy.

## Guardrails

- Do not hand-edit `config/*.json`; go through `ai-trend curate` so validation runs.
- Do not delete existing topics or keywords; this skill only adds.
- Keep the run reproducible: the decision file is the record of what you chose.
