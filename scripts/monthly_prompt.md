You are running the monthly AI-Trend update in this repository (you are in the repo
root). Use `PYTHONNOUSERSITE=1 ./env/bin/ai-trend ...` for all CLI calls.

Goal: pick up any newly-published conference papers, refresh topics/trends/citations,
regenerate the static site, and open a PR — touching only data/docs/config and
CONFERENCES.md. Do NOT overwrite README.md (it is the project README; trends live on
the site, not in README).

Steps:
1. Follow the **track-conferences** skill: for the current and next year, web-search
   each tracked conference's date; for any conference within ~3 months whose papers
   are now published (verify with `ai-trend probe <CONF> <year>`) and not yet
   ingested, ingest it (`ai-trend ingest-url "<url>"`), then curate its new topics
   (the **curate-topics** skill) and assign. Update CONFERENCES.md (dates + links).
2. Run the deterministic refresh to catch anything else and rebuild outputs:
   `ai-trend refresh --discover --spacy-model en_core_sci_lg` (add `--curate` only if
   ANTHROPIC_API_KEY is set in the environment).
3. Recompute and snapshot: `ai-trend trends --include-counts -o data/trends/trends.json`,
   `ai-trend snapshot-citations`, then `ai-trend export-site`.
4. `ai-trend check-sources --check` and fix any gaps/dead links in CONFERENCES.md.
5. If anything changed, commit on a branch and open a PR with `gh pr create`
   summarizing what was added/updated. If nothing changed, do nothing.

Be conservative: never ingest a partially-posted venue (re-check next month if the
paper count looks far below the expected size). Keep the run idempotent.
