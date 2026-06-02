"""End-to-end pipeline orchestration for the unattended monthly refresh.

Chains: crawl -> process -> assign -> (AI curate) -> trends -> export-site.

Stages degrade gracefully: crawl and AI curation are best-effort (a failure logs
and continues), while the deterministic core (process/assign/trends/export) is
expected to succeed. Running with no new crawl data still re-derives trends and
the site, so the scheduled job is safe to run anytime — it simply produces no diff
when nothing changed.
"""

from __future__ import annotations

import glob
from pathlib import Path
from typing import TYPE_CHECKING, Any, Callable

from ai_trend.registry import ConferenceRegistry
from ai_trend.taxonomy import DEFAULT_CONFIG_DIR, Taxonomy

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_trend.curate_ai import AnthropicLike

DEFAULT_DATA_DIR = "data"
DEFAULT_RAW_DIR = "data/scrapy_crawl"
DEFAULT_SITE_DIR = "docs/data"
DEFAULT_CRAWL_CONFIG = "config/crawl.json"


def _source_csvs(data_dir: Path) -> list[Path]:
    """Source paper CSVs under data/<year>/, excluding derived/aux files."""
    out: list[Path] = []
    for path in sorted(Path(data_dir).glob("[0-9][0-9][0-9][0-9]/*.csv")):
        if path.name.endswith("_topics.csv"):
            continue
        out.append(path)
    return out


def refresh(
    *,
    config_dir: Path | str = DEFAULT_CONFIG_DIR,
    data_dir: Path | str = DEFAULT_DATA_DIR,
    raw_dir: Path | str = DEFAULT_RAW_DIR,
    site_dir: Path | str = DEFAULT_SITE_DIR,
    crawl_config: Path | str = DEFAULT_CRAWL_CONFIG,
    do_crawl: bool = False,
    do_discover: bool = False,
    do_curate: bool = False,
    client: "AnthropicLike | None" = None,
    model: str | None = None,
    spacy_model: str | None = None,
    log: Callable[[str], None] = print,
) -> dict[str, Any]:
    """Run the pipeline and return a summary dict."""
    config_dir = Path(config_dir)
    data_dir = Path(data_dir)
    registry = ConferenceRegistry.load(config_dir)
    summary: dict[str, Any] = {"crawled": 0, "discovered": 0, "processed": 0, "curated": 0, "assigned": 0}

    # 1. crawl (best-effort)
    if do_crawl:
        summary["crawled"] = _run_crawl(crawl_config, raw_dir, log)

    # 1b. discover & ingest newly-available conference-years (probe-based watch)
    if do_discover:
        summary["discovered"] = _discover_and_ingest(registry, data_dir, log)

    # 2. process crawled JSON -> source CSVs
    from ai_trend.ingest import process

    written: list[Path] = []
    if Path(raw_dir).exists():
        written = process(raw_dir, data_dir, registry)
        summary["processed"] = len(written)
        log(f"process: {len(written)} conference-year CSV(s) merged")

    # 3. AI curation on newly-processed conference-years (best-effort)
    if do_curate and client is not None and written:
        summary["curated"] = _run_curate(
            written, client, config_dir, registry, model, spacy_model, log
        )

    # 4. assign topics for every source CSV with the current taxonomy
    from ai_trend.assign import assign_csv

    taxonomy = Taxonomy.load(config_dir)
    sources = _source_csvs(data_dir)
    for csv in sources:
        out = csv.with_name(csv.name + "_topics.csv")
        assign_csv(str(csv), str(out), taxonomy)
    summary["assigned"] = len(sources)
    log(f"assign: {len(sources)} conference-year(s) labelled")

    # 5. trends
    from ai_trend.trends import compute_all_trends, trend_to_dict
    import json

    trends = compute_all_trends(taxonomy, data_dir)
    trends_path = data_dir / "trends" / "trends.json"
    trends_path.parent.mkdir(parents=True, exist_ok=True)
    trends_path.write_text(
        json.dumps([trend_to_dict(t, include_counts=True) for t in trends], ensure_ascii=False),
        encoding="utf-8",
    )
    summary["trends"] = len(trends)
    log(f"trends: {len(trends)} conference-year(s) -> {trends_path}")

    # 5b. snapshot citation counts (for month-over-month "rising" velocity)
    import datetime

    from ai_trend.citations import snapshot_citations

    try:
        snap = snapshot_citations(datetime.date.today().isoformat(), data_dir=data_dir)
        log(f"snapshot: citation counts -> {snap}")
    except Exception as exc:  # best-effort
        log(f"snapshot: skipped ({exc})")

    # 6. export static site
    from ai_trend.site import export_site

    manifest = export_site(site_dir, taxonomy=taxonomy, registry=registry, data_dir=data_dir)
    summary["site_papers"] = sum(s["count"] for s in manifest["shards"])
    summary["site_shards"] = len(manifest["shards"])
    log(f"export-site: {summary['site_shards']} shards / {summary['site_papers']} papers")

    return summary


def _discover_and_ingest(registry, data_dir: Path | str, log: Callable[[str], None]) -> int:
    """Probe current+next year for each conference; ingest any newly-available ones.

    Deterministic equivalent of the track-conferences skill (no web search): if a
    venue's papers are published and not already ingested, download them. Best-effort.
    """
    import datetime

    import requests

    from ai_trend.cvf import scrape_to_csv
    from ai_trend.openreview import fetch_to_csv
    from ai_trend.probe import probe

    year_now = datetime.date.today().year
    session = requests.Session()
    ingested = 0
    for conf in registry.conferences:
        for year in (year_now, year_now + 1):
            out = Path(data_dir) / str(year) / f"{conf.month}_{conf.key}.csv"
            if out.exists():
                continue  # already ingested
            try:
                result = probe(conf, year, session=session)
            except Exception as exc:
                log(f"discover: probe {conf.label} {year} failed ({exc})")
                continue
            if not result.available:
                continue
            log(f"discover: {conf.label} {year} available ({result.count} papers) — ingesting")
            try:
                if conf.source == "cvf":
                    n = scrape_to_csv(conf.label, year, out)
                else:
                    group = conf.openreview_group or f"{conf.label}.cc"
                    n = fetch_to_csv(f"{group}/{year}/Conference", conf.label, year, out)
                log(f"discover: ingested {conf.label} {year} ({n} papers) -> {out}")
                ingested += 1
            except Exception as exc:
                log(f"discover: ingest {conf.label} {year} failed ({exc})")
    return ingested


def _run_crawl(crawl_config: Path | str, raw_dir: Path | str, log: Callable[[str], None]) -> int:
    from ai_trend.crawl import crawl, load_jobs

    config_path = Path(crawl_config)
    if not config_path.exists():
        log(f"crawl: config {config_path} missing; skipping")
        return 0
    try:
        spider, details, jobs = load_jobs(config_path)
        results = crawl(jobs, raw_dir=raw_dir, spider=spider, details=details)
        ok = sum(1 for r in results if r.ok)
        log(f"crawl: {ok}/{len(results)} jobs ok")
        for r in results:
            if not r.ok:
                log(f"  crawl FAILED {r.job.output_name()}: {r.message[:160]}")
        return ok
    except Exception as exc:  # best-effort: never abort the pipeline on crawl issues
        log(f"crawl: error ({exc}); continuing with existing data")
        return 0


def _run_curate(
    written: list[Path],
    client: "AnthropicLike",
    config_dir: Path,
    registry: ConferenceRegistry,
    model: str | None,
    spacy_model: str | None,
    log: Callable[[str], None],
) -> int:
    from ai_trend.curate_ai import DEFAULT_MODEL, curate_with_ai

    count = 0
    for csv in written:
        conf = registry.conference_for_token(csv.stem.partition("_")[2])
        try:
            result = curate_with_ai(
                csv,
                client,
                config_dir=config_dir,
                conference=conf.label if conf else None,
                year=csv.parent.name,
                model=model or DEFAULT_MODEL,
                model_path=spacy_model,
            )
            log(f"curate: {csv.name} -> {result.summary}")
            count += 1
        except Exception as exc:  # best-effort
            log(f"curate: skipped {csv.name} ({exc})")
    return count
