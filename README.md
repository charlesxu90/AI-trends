# <img src="assets/logo.png" alt="" height="38" align="middle"> AI Trends in Conferences

**Live site → https://charlesxu90.github.io/AI-trends/**

Track what the field of AI is *actually* working on. AI-Trend ingests every accepted
paper from the major AI conferences, auto-labels each with research topics, and
surfaces the **top**, **emerging**, and **fading** areas year over year — with the
papers (and their citation counts) behind every trend a click away.

Conferences: **CVPR · ICCV · ICML · ICLR · NeurIPS** · Years: **2021–2025**.

## What it does

- **Topic trends** — top / emerging / fading topics per conference-year, computed
  from accepted-paper counts and year-over-year change.
- **Rising Stars** — browse/search papers, sorted by citations (and, as citation
  snapshots accumulate, by recent citation velocity), filterable by venue/year/topic.
- **Citations & links** — Semantic Scholar citation counts (title-verified to avoid
  wrong matches); each paper links to arXiv when known, else Google Scholar, plus the
  source PDF.
- **Static site** — a fast GitHub Pages browser, rebuilt from the data.

The only non-deterministic step is **topic curation** (deciding which keywords map to
which topic); everything else is pure, reproducible Python. Curation is done by an AI
skill (Claude Code) over a curated taxonomy, so trends stay comparable across years.

## How it works

```
URL / crawl ──▶ download papers ──▶ assign topics ──▶ trends ──▶ static site
(OpenReview/thecvf)  (per-conference CSV)  (substring match    (docs/, GitHub Pages)
                                            vs curated taxonomy)
                         └▶ Semantic Scholar citations (cached, verified) ─┘
```

See **[AUTOMATION.md](AUTOMATION.md)** for the full pipeline and
**[CLAUDE.md](CLAUDE.md)** for architecture and the critical environment rule.
Conference source links are tracked in **[CONFERENCES.md](CONFERENCES.md)**.

## Usage

All commands run from the repo root, isolated from user site-packages (see CLAUDE.md):

```bash
PYTHONNOUSERSITE=1 ./env/bin/ai-trend <command>
```

| Command | What it does |
|---|---|
| `ingest-url "<url>"` | Add a conference from an OpenReview or `openaccess.thecvf.com` URL |
| `probe <CONF> <year>` | Check whether a conference-year's papers are published yet |
| `assign <csv>` | Assign topics to a papers CSV (deterministic) |
| `trends [--format markdown]` | Compute top/emerging/fading per conference-year |
| `citations <csv> --scope emerging` | Fetch Semantic Scholar citations (cached, verified) |
| `verify-citations` | Re-verify suspicious (high) citation counts by title match |
| `export-site` | Rebuild the GitHub Pages data (`docs/data/`) |
| `refresh --discover [--curate]` | Full pipeline: discover new venues → ingest → assign → trends → site |
| `check-sources --check` | Validate the links in CONFERENCES.md |

Natural-language front doors (Claude Code skills): **`/add-conference`** (paste a URL),
**`/curate-topics`** (taxonomy curation), **`/track-conferences`** (watch + ingest as
papers go live).

### Setup (Python 3.10, pinned scispaCy stack)

```bash
conda create -y -p ./env python=3.10
PYTHONNOUSERSITE=1 ./env/bin/pip install -e . --no-deps
PYTHONNOUSERSITE=1 ./env/bin/pip install -r requirements-lock.txt
# optional extras: '.[web]' (ingest-url/citations), '.[crawl]' (scrapy), '.[curate]' (anthropic)
```

## Monthly automation

Two interchangeable ways to keep the site current:

1. **GitHub Actions** — `.github/workflows/refresh.yml` runs on a monthly cron (and
   `workflow_dispatch`): discover → ingest → assign → trends → snapshot → export, then
   opens a PR. Merging republishes the site (Pages deploys from `main` / `/docs`).
   Requires the `ANTHROPIC_API_KEY` secret and "Allow GitHub Actions to create pull
   requests" enabled.

2. **Claude Code via crontab** — run the agentic pipeline locally (adds web-search
   conference-date discovery and AI topic curation):

   ```cron
   0 6 1 * * /ABS/PATH/AI-trend/scripts/monthly_refresh.sh >> /ABS/PATH/AI-trend/monthly_refresh.log 2>&1
   ```

   `scripts/monthly_refresh.sh` invokes `claude -p` headlessly with
   `scripts/monthly_prompt.md` (follows the `track-conferences` + `curate-topics`
   skills, then opens a PR). Requires the `claude` and `gh` CLIs authenticated; put
   `ANTHROPIC_API_KEY=...` in a repo-root `.env` to enable headless curation.

## License

[MIT](./LICENSE)
