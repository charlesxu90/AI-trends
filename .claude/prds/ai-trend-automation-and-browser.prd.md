# AI-Trend Automation & Paper Browser

## Problem
Tracking hot topics across major AI conferences (CVPR, ICCV, ICML, ICLR, NIPS) currently depends on a manual notebook pipeline: a human filters keywords, hand-assigns each paper to a topic, and transcribes top/emerging/fading topics into `README.md` tables by hand. This is slow, subjective, and does not scale as conferences and years accumulate — and the only way for anyone to consume the result is to scroll a static Markdown file with no way to search or drill into the underlying papers.

## Evidence
- The repo's own `run_analysis.sh` documents manual steps: "Filter the keywords, and manually check the topics" and "manually check the topics" — confirming the bottleneck is human topic assignment.
- Outputs are hand-maintained Markdown tables in `README.md`; coverage is uneven (e.g. 2023 ICCV has only a "Top 5" row, no emerging/fading), indicating manual upkeep gaps.
- Trend tables reference topics but provide no path from a topic to the actual papers behind it — the `*_topics.csv` files (thousands of papers) are never surfaced to a reader.
- Assumption — the value of a public browsing experience to the wider community needs validation via repo traffic / stars after launch.

## Users
- **Primary (producer)**: the maintainer/researcher (you) tracking how the field is shifting, who needs the topic-assignment and trend analysis to run with minimal manual effort on a monthly cadence.
- **Primary (consumer)**: AI researchers/practitioners browsing the public GitHub Pages site to discover trends and the papers behind them.
- **Not for**: end users wanting recommendations, full-text paper hosting, or non-AI / non-conference literature. Not a general academic search engine.

## Hypothesis
We believe that **an AI agent (Claude Code as the reasoning core) that auto-assigns papers to a curated topic taxonomy, computes trends, and feeds a browsable GitHub Pages site** will **eliminate the manual topic-analysis bottleneck and make trends + their underlying papers explorable** for **the maintainer and the AI community**.
We'll know we're right when **a full monthly refresh (crawl → topic assignment → trend computation → published site) runs end-to-end with no manual topic labeling, and the site lets a user move from a trend to its papers in a few clicks.**

## Success Metrics
| Metric | Target | How measured |
|---|---|---|
| Manual labeling effort per refresh | ~0 (no hand topic assignment) | Maintainer log: steps requiring human topic edits |
| Refresh cadence achieved | Monthly, unattended | Scheduled run history succeeds without intervention |
| Topic-assignment agreement with prior manual labels | High agreement on a held-out sample | Spot-check AI labels vs existing `*_topics.csv` on a sample |
| Conferences covered | 5 (CVPR, ICCV, ICML, ICLR, NIPS), config-extensible | Config file + published data |
| Trend→paper drill-down | Available for every top/emerging/fading topic | Site QA: each topic links to its paper list |
| Site usefulness | TBD — needs validation via post-launch repo traffic/stars | GitHub insights |

## Scope
**MVP** — the minimum to test the hypothesis:
1. An **automated analysis pipeline**, driven by Claude Code skills + CLI tools, that takes crawled per-conference CSVs and produces topic-assigned papers and trend summaries (top-5 / emerging / fading) **with no manual topic labeling**, anchored to the **existing curated topic taxonomy** (graph, llm, transformer, etc.).
2. **Configurable conference set**: ship with the current 5; adding a conference is a config entry, not new bespoke code.
3. A **GitHub Pages site** offering **both**: (a) trend visualizations over time, and (b) drill-down from any topic into a searchable/filterable list of its papers (filter by conference / year / topic; link to PDF).
4. **Monthly scheduled refresh** that runs the pipeline and republishes the site unattended.

**Out of scope**
- Human-in-the-loop approval gate for topic labels — chosen automation level is fully autonomous; deferred unless quality demands it.
- Free AI-discovered/clustered topic taxonomies — MVP keeps the curated taxonomy for year-over-year comparability; topic discovery deferred.
- Crawler/spider rewrite — reuse existing Scrapy/OpenReview ingestion; only adapt as needed for the configured venues.
- Hosting full paper text, citation graphs beyond existing citation analysis, recommendations, and accounts/personalization.
- Expanding beyond the 5 conferences in the MVP (design allows it; content deferred).

## Delivery Milestones
<!-- Business outcomes, not engineering tasks. /plan turns each into a plan. -->
<!-- Status: pending | in-progress | complete -->

| # | Milestone | Outcome | Status | Plan |
|---|---|---|---|---|
| 1 | Automated topic assignment | Papers in `*_topics.csv` are labeled by an AI skill against the curated taxonomy with no manual editing | complete | `.claude/plans/ai-trend-automation-and-browser.plan.md` |
| 2 | Automated trend computation | Top-5 / emerging / fading topics per conference-year are generated automatically as structured data | complete | `.claude/plans/ai-trend-automation-and-browser.plan.md` |
| 3 | Configurable conference registry | The 5 conferences (and future ones) are defined in config; pipeline reads from it | complete | `config/conferences.json` + `ai_trend/registry.py` |
| 4 | GitHub Pages browser | Public site with trend dashboard + topic→paper drill-down, search and filters | complete | `docs/` + `ai_trend/site.py` |
| 5 | Monthly unattended refresh | Scheduled run executes the full pipeline and republishes the site without manual steps | pending | — |

## Open Questions
- [ ] What confidence threshold (if any) makes an autonomous topic label acceptable, given there is no review gate?
- [ ] How are *new* emerging topics handled if the taxonomy is fixed — do they stay unlabeled/"other" until you add them? (Hybrid was not selected.)
- [ ] Where does the scheduled refresh run (GitHub Actions vs local cron vs other), and how are crawl credentials/rate limits handled? (Implementation — for /plan.)
- [ ] Should historical `README.md` tables (2021–2025) be regenerated by the new automated pipeline for consistency, or frozen as-is?
- [ ] Does the public site need to surface the existing citation analysis (`2.popular_topics.ipynb`), or is that maintainer-only for now?

## Risks
| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Autonomous topic labels drift from prior manual quality, skewing trends | Medium | High | Spot-check against existing `*_topics.csv`; add audit/flagging if agreement is low |
| Fixed taxonomy misses genuinely new trends (the very thing this tracks) | Medium | High | Track an "unlabeled/other" bucket; periodic taxonomy review to admit new topics |
| Conference APIs / OpenReview schemas change and break crawling | Medium | Medium | Keep ingestion config-driven; fail loudly on schema mismatch |
| GitHub Pages is static — large CSVs may strain client-side browsing | Medium | Medium | Pre-build compact JSON indexes at publish time (decision for /plan) |
| Unattended monthly run fails silently | Low | Medium | Surface run status/notifications; treat a failed refresh as visible |
| LLM cost/rate for labeling thousands of papers each cycle | Medium | Low | Label only new/changed papers; cache prior assignments |

---
*Status: DRAFT — requirements only. Implementation planning pending via /plan.*
