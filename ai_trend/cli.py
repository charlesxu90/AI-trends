"""``ai-trend`` command-line interface.

Subcommands:

* ``candidates`` -- extract candidate keywords from a papers CSV into a curation
  payload (JSON) for the ``curate-topics`` skill.
* ``curate`` -- apply the skill's decision JSON to the taxonomy config.
* ``assign`` -- assign topics to a papers CSV using the current taxonomy.

The deterministic ``assign`` and the AI-curation seam are deliberately separate so
the reasoning step (the skill) sits cleanly between extraction and assignment.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ai_trend.taxonomy import DEFAULT_CONFIG_DIR, Taxonomy

OTHER_LEDGER_FILENAME = "other_keywords.json"


def _eprint(message: str) -> None:
    print(message, file=sys.stderr)


def _load_other_ledger(config_dir: Path) -> list[str]:
    path = config_dir / OTHER_LEDGER_FILENAME
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


def _save_other_ledger(config_dir: Path, keywords: list[str]) -> None:
    path = config_dir / OTHER_LEDGER_FILENAME
    path.write_text(
        json.dumps(sorted(set(keywords)), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _default_topics_path(csv_path: Path) -> Path:
    # Mirror the notebook's naming: data/2025/5_iclr.csv -> 5_iclr.csv_topics.csv
    return csv_path.with_name(csv_path.name + "_topics.csv")


# ---- subcommands ------------------------------------------------------------
def cmd_candidates(args: argparse.Namespace) -> int:
    import pandas as pd

    from ai_trend.candidates import candidate_keywords, candidates_to_dicts
    from ai_trend.curate_io import build_curation_payload

    csv_path = Path(args.csv)
    if not csv_path.exists():
        _eprint(f"error: input CSV not found: {csv_path}")
        return 2

    config_dir = Path(args.config)
    taxonomy = Taxonomy.load(config_dir)
    # Exclude keywords already parked in the 'other' ledger so they don't resurface.
    ledger = _load_other_ledger(config_dir)
    if ledger:
        taxonomy = taxonomy.add_noise(ledger)

    df = pd.read_csv(csv_path)
    if "title" not in df.columns:
        _eprint(f"error: CSV has no 'title' column: {csv_path}")
        return 2
    titles = df["title"].astype(str).str.lower().tolist()

    candidates = candidate_keywords(
        titles,
        taxonomy,
        model_path=args.model,
        threshold=args.threshold,
        examples=args.examples,
    )
    payload = build_curation_payload(
        candidates,
        taxonomy,
        conference=args.conference,
        year=args.year,
    )
    payload["candidates"] = candidates_to_dicts(candidates)

    out_path = Path(args.output) if args.output else None
    text = json.dumps(payload, indent=2, ensure_ascii=False)
    if out_path:
        out_path.write_text(text + "\n", encoding="utf-8")
        _eprint(f"wrote {len(candidates)} candidates -> {out_path}")
    else:
        print(text)
    return 0


def cmd_curate(args: argparse.Namespace) -> int:
    from ai_trend.curate_io import apply_decision, parse_decision

    decision_path = Path(args.decision)
    if not decision_path.exists():
        _eprint(f"error: decision file not found: {decision_path}")
        return 2

    config_dir = Path(args.config)
    taxonomy = Taxonomy.load(config_dir)
    raw = json.loads(decision_path.read_text(encoding="utf-8"))
    decisions = parse_decision(raw)
    result = apply_decision(taxonomy, decisions)

    if args.dry_run:
        _eprint(f"dry-run: {result.summary}; other={result.other_keywords}")
        return 0

    result.taxonomy.save(config_dir)
    if result.other_keywords:
        ledger = _load_other_ledger(config_dir)
        _save_other_ledger(config_dir, [*ledger, *result.other_keywords])
    _eprint(f"applied {result.summary}; parked {len(result.other_keywords)} in 'other'")
    return 0


def cmd_trends(args: argparse.Namespace) -> int:
    from ai_trend.trends import (
        compute_all_trends,
        render_markdown,
        trend_to_dict,
    )

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        _eprint(f"error: data directory not found: {data_dir}")
        return 2

    taxonomy = Taxonomy.load(Path(args.config))
    trends = compute_all_trends(
        taxonomy,
        data_dir,
        top_n=args.top_n,
        min_prev=args.min_prev,
        min_count=args.min_count,
    )
    if not trends:
        _eprint(f"error: no *_topics.csv found under {data_dir}")
        return 2

    if args.format == "markdown":
        text = render_markdown(trends)
    else:
        payload = [
            trend_to_dict(t, include_counts=args.include_counts) for t in trends
        ]
        text = json.dumps(payload, indent=2, ensure_ascii=False)

    if args.output:
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(text + "\n", encoding="utf-8")
        _eprint(f"wrote trends for {len(trends)} conference-years -> {out_path}")
    else:
        print(text)
    return 0


def cmd_refresh(args: argparse.Namespace) -> int:
    from ai_trend.refresh import refresh

    client = None
    if args.curate:
        try:
            from ai_trend.curate_ai import make_client

            client = make_client()
        except Exception as exc:  # missing SDK or key: degrade, don't abort the run
            # log the exception *type* only — never the message (could echo the key)
            _eprint(f"warning: --curate skipped: no Anthropic client ({type(exc).__name__})")

    summary = refresh(
        config_dir=Path(args.config),
        data_dir=args.data_dir,
        raw_dir=args.raw_dir,
        site_dir=args.site_dir,
        crawl_config=args.crawl_config,
        do_crawl=args.crawl,
        do_curate=args.curate,
        client=client,
        model=args.model,
        spacy_model=args.spacy_model,
        log=_eprint,
    )
    _eprint(f"refresh complete: {summary}")
    return 0


def cmd_ingest_url(args: argparse.Namespace) -> int:
    from ai_trend.registry import ConferenceRegistry
    from ai_trend.sources import SourceError, detect_source

    registry = ConferenceRegistry.load(Path(args.config))
    try:
        spec = detect_source(args.url, registry)
    except SourceError as exc:
        _eprint(f"error: {exc}")
        return 2

    conf = registry.conference_for_token(spec.token)
    out = Path(args.data_dir) / str(spec.year) / f"{conf.month}_{conf.key}.csv"
    try:
        if spec.source == "cvf":
            from ai_trend.cvf import scrape_to_csv

            n = scrape_to_csv(spec.label, spec.year, out)
        else:
            from ai_trend.openreview import fetch_to_csv

            n = fetch_to_csv(spec.venueid, spec.label, spec.year, out)
    except Exception as exc:  # network/parse failure: report cleanly, don't dump a traceback
        _eprint(f"error: download failed for {spec.label} {spec.year} ({type(exc).__name__}: {exc}). "
                f"The source may be slow/unreachable — try again.")
        return 1
    if n == 0:
        _eprint(f"warning: 0 papers found for {spec.label} {spec.year} (check the URL/venue).")
        return 1
    _eprint(f"downloaded {n} papers ({spec.label} {spec.year}, {spec.source}) -> {out}")

    if args.full:
        from ai_trend.assign import assign_csv

        taxonomy = Taxonomy.load(Path(args.config))
        assign_csv(str(out), str(out) + "_topics.csv", taxonomy)
        _eprint(f"assigned -> {out}_topics.csv (current taxonomy; run candidates+curate for new topics)")
        _regenerate_trends_and_site(args, taxonomy, registry)
    return 0


def _regenerate_trends_and_site(args, taxonomy, registry) -> None:
    import json as _json

    from ai_trend.site import export_site
    from ai_trend.trends import compute_all_trends, trend_to_dict

    trends = compute_all_trends(taxonomy, args.data_dir)
    tp = Path(args.data_dir) / "trends" / "trends.json"
    tp.parent.mkdir(parents=True, exist_ok=True)
    tp.write_text(_json.dumps([trend_to_dict(t, include_counts=True) for t in trends], ensure_ascii=False), encoding="utf-8")
    manifest = export_site("docs/data", taxonomy=taxonomy, registry=registry, data_dir=args.data_dir)
    _eprint(f"regenerated trends + site ({len(manifest['shards'])} shards)")


def cmd_citations(args: argparse.Namespace) -> int:
    import pandas as pd
    import requests

    from ai_trend.citations import fetch_citations, titles_for_topics

    csv = Path(args.topics_csv)
    if not csv.exists():
        _eprint(f"error: topics CSV not found: {csv}")
        return 2
    df = pd.read_csv(csv)

    if args.topics:
        topic_set = {t.strip() for t in args.topics.split(",") if t.strip()}
    else:
        from ai_trend.registry import ConferenceRegistry
        from ai_trend.trends import compute_all_trends, parse_conference

        registry = ConferenceRegistry.load(Path(args.config))
        conference = parse_conference(csv.name, registry.token_to_label)
        try:
            year = int(csv.parent.name)
        except ValueError:
            _eprint("error: cannot infer year from path; pass --topics explicitly")
            return 2
        taxonomy = Taxonomy.load(Path(args.config))
        trend = next(
            (t for t in compute_all_trends(taxonomy, args.data_dir)
             if t.conference == conference and t.year == year),
            None,
        )
        if trend is None:
            topic_set = set()
        elif args.scope == "emerging":
            topic_set = set(trend.emerging)
        elif args.scope == "top":
            topic_set = set(trend.top)
        else:  # top-emerging
            topic_set = set(trend.top + trend.emerging)
    if not topic_set:
        _eprint("error: no topics to scope citations (no trend found); pass --topics")
        return 2

    titles = titles_for_topics(df, topic_set)
    if args.limit:
        titles = titles[: args.limit]
    _eprint(f"citations: {len(titles)} papers in topics {sorted(topic_set)[:6]}...")
    cache_path = str(csv) + ".citations.json"
    fetch_citations(titles, cache_path, requests.Session(), throttle=args.throttle, log=_eprint)
    _eprint(f"citations cached -> {cache_path} (re-run export-site to surface them)")
    return 0


def cmd_verify_citations(args: argparse.Namespace) -> int:
    import glob

    import requests

    from ai_trend.citations import verify_existing

    if args.topics_csv:
        sidecars = [str(Path(args.topics_csv)) + ".citations.json"]
    else:
        sidecars = sorted(glob.glob(f"{args.data_dir}/*/*.citations.json"))
    sidecars = [s for s in sidecars if Path(s).exists()]
    if not sidecars:
        _eprint("no citation sidecars found")
        return 1

    session = requests.Session()
    totals = {"checked": 0, "changed": 0, "unverified": 0}
    for sc in sidecars:
        summary = verify_existing(sc, session, min_count=args.min, throttle=args.throttle, log=_eprint)
        _eprint(f"  {Path(sc).name}: {summary}")
        for k in totals:
            totals[k] += summary[k]
    _eprint(f"verify-citations: {totals}; re-run export-site to apply")
    return 0


def cmd_import_citations(args: argparse.Namespace) -> int:
    import glob

    from ai_trend.citations import merge_into_sidecar

    paths: list[str] = []
    for p in args.paths:
        paths.extend(glob.glob(p) if any(c in p for c in "*?[") else [p])
    if not paths:
        # default: every *_emerging.xlsx under the data dir
        paths = sorted(glob.glob(f"{args.data_dir}/*/*_emerging.xlsx"))
    if not paths:
        _eprint("no *_emerging.xlsx files found")
        return 1

    total = 0
    for path in sorted(paths):
        try:
            sidecar, added = merge_into_sidecar(path)
            _eprint(f"  {Path(path).name} -> {sidecar.name} (+{added})")
            total += 1
        except Exception as exc:
            _eprint(f"  skipped {path}: {exc}")
    _eprint(f"imported {total} citation file(s); re-run export-site to surface them")
    return 0


def cmd_crawl(args: argparse.Namespace) -> int:
    from ai_trend.crawl import crawl, load_jobs

    config_path = Path(args.crawl_config)
    if not config_path.exists():
        _eprint(f"error: crawl config not found: {config_path}")
        return 2
    spider, details, jobs = load_jobs(config_path)
    if not jobs:
        _eprint("no crawl jobs defined; nothing to do")
        return 0
    only = set(args.only.split(",")) if args.only else None
    results = crawl(
        jobs, raw_dir=args.raw_dir, spider=spider, details=details,
        only=only, dry_run=args.dry_run,
    )
    ok = sum(1 for r in results if r.ok)
    for r in results:
        if not r.ok:
            _eprint(f"  FAILED {r.job.output_name()}: {r.message}")
    _eprint(f"crawl: {ok}/{len(results)} jobs ok -> {args.raw_dir}")
    return 0 if ok else 1


def cmd_process(args: argparse.Namespace) -> int:
    from ai_trend.ingest import process
    from ai_trend.registry import ConferenceRegistry

    raw_dir = Path(args.raw_dir)
    if not raw_dir.exists():
        _eprint(f"error: raw dir not found: {raw_dir}")
        return 2
    registry = ConferenceRegistry.load(Path(args.config))
    written = process(raw_dir, args.out_dir, registry)
    for path in written:
        _eprint(f"  wrote {path}")
    _eprint(f"process: merged {len(written)} conference-year CSV(s)")
    return 0


def cmd_export_site(args: argparse.Namespace) -> int:
    from ai_trend.site import export_site

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        _eprint(f"error: data directory not found: {data_dir}")
        return 2

    taxonomy = Taxonomy.load(Path(args.config))
    manifest = export_site(
        args.out_dir,
        taxonomy=taxonomy,
        data_dir=data_dir,
        top_n=args.top_n,
        min_prev=args.min_prev,
        min_count=args.min_count,
        abstract_chars=args.abstract_chars,
    )
    papers = sum(s["count"] for s in manifest["shards"])
    _eprint(
        f"exported {len(manifest['shards'])} shards / {papers} papers -> {args.out_dir}"
    )
    return 0


def cmd_assign(args: argparse.Namespace) -> int:
    from ai_trend.assign import assign_csv

    csv_path = Path(args.csv)
    if not csv_path.exists():
        _eprint(f"error: input CSV not found: {csv_path}")
        return 2

    taxonomy = Taxonomy.load(Path(args.config))
    out_path = Path(args.output) if args.output else _default_topics_path(csv_path)
    assign_csv(str(csv_path), str(out_path), taxonomy)
    _eprint(f"assigned topics -> {out_path}")
    return 0


# ---- parser -----------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="ai-trend", description=__doc__)
    parser.add_argument(
        "--config",
        default=str(DEFAULT_CONFIG_DIR),
        help="config directory holding taxonomy.json / useless_keywords.json",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_cand = sub.add_parser("candidates", help="extract candidate keywords for curation")
    p_cand.add_argument("csv", help="papers CSV (needs a 'title' column)")
    p_cand.add_argument("-o", "--output", help="write payload JSON here (default: stdout)")
    p_cand.add_argument("--threshold", type=int, default=5, help="min keyword count")
    p_cand.add_argument("--examples", type=int, default=3, help="example titles / keyword")
    p_cand.add_argument(
        "--model",
        default=None,
        help="path to the scispaCy model (default: bundled model)",
    )
    p_cand.add_argument("--conference", default=None)
    p_cand.add_argument("--year", default=None)
    p_cand.set_defaults(func=cmd_candidates)

    p_cur = sub.add_parser("curate", help="apply a curation decision to the taxonomy")
    p_cur.add_argument("decision", help="decision JSON produced by the curate-topics skill")
    p_cur.add_argument("--dry-run", action="store_true", help="report changes, write nothing")
    p_cur.set_defaults(func=cmd_curate)

    p_asg = sub.add_parser("assign", help="assign topics to a papers CSV")
    p_asg.add_argument("csv", help="papers CSV (needs 'title' and 'abstract' columns)")
    p_asg.add_argument("-o", "--output", help="output CSV (default: <csv>_topics.csv)")
    p_asg.set_defaults(func=cmd_assign)

    p_trd = sub.add_parser("trends", help="compute top/emerging/fading topics")
    p_trd.add_argument("--data-dir", default="data", help="root holding <year>/ folders")
    p_trd.add_argument("-o", "--output", help="output file (default: stdout)")
    p_trd.add_argument("--format", choices=["json", "markdown"], default="json")
    p_trd.add_argument("--top-n", type=int, default=5)
    p_trd.add_argument(
        "--min-prev",
        type=int,
        default=1,
        help="min previous-year count for emerging/fading eligibility",
    )
    p_trd.add_argument(
        "--min-count",
        type=int,
        default=10,
        help="min current-year count for a topic to count as emerging",
    )
    p_trd.add_argument(
        "--include-counts", action="store_true", help="embed per-topic counts (json)"
    )
    p_trd.set_defaults(func=cmd_trends)

    p_ref = sub.add_parser("refresh", help="run the full pipeline (process->assign->trends->export)")
    p_ref.add_argument("--crawl", action="store_true", help="also run the OpenReview crawl")
    p_ref.add_argument("--curate", action="store_true", help="also run AI topic curation (needs ANTHROPIC_API_KEY)")
    p_ref.add_argument("--data-dir", default="data")
    p_ref.add_argument("--raw-dir", default="data/scrapy_crawl")
    p_ref.add_argument("--site-dir", default="docs/data")
    p_ref.add_argument("--crawl-config", default="config/crawl.json")
    p_ref.add_argument("--model", default=None, help="Anthropic model for curation")
    p_ref.add_argument("--spacy-model", default=None, help="scispaCy model path or package name")
    p_ref.set_defaults(func=cmd_refresh)

    p_url = sub.add_parser("ingest-url", help="download a conference from an OpenReview/thecvf URL")
    p_url.add_argument("url", help="OpenReview group/venue URL or openaccess.thecvf.com URL")
    p_url.add_argument("--data-dir", default="data")
    p_url.add_argument("--full", action="store_true", help="also assign + trends + export (current taxonomy)")
    p_url.set_defaults(func=cmd_ingest_url)

    p_cit = sub.add_parser("citations", help="fetch Semantic Scholar citation counts (bounded, cached)")
    p_cit.add_argument("topics_csv", help="a *_topics.csv file")
    p_cit.add_argument("--topics", default=None, help="comma-separated topics to scope (overrides --scope)")
    p_cit.add_argument("--scope", choices=["emerging", "top", "top-emerging"], default="emerging",
                       help="which trend topics to fetch citations for (default: emerging)")
    p_cit.add_argument("--data-dir", default="data")
    p_cit.add_argument("--limit", type=int, default=None, help="cap number of papers")
    p_cit.add_argument("--throttle", type=float, default=1.1, help="seconds between API calls")
    p_cit.set_defaults(func=cmd_citations)

    p_ver = sub.add_parser("verify-citations", help="re-verify high cached citation counts by title match")
    p_ver.add_argument("topics_csv", nargs="?", default=None, help="a *_topics.csv (default: all sidecars)")
    p_ver.add_argument("--min", type=int, default=150, help="re-verify counts above this")
    p_ver.add_argument("--data-dir", default="data")
    p_ver.add_argument("--throttle", type=float, default=1.1)
    p_ver.set_defaults(func=cmd_verify_citations)

    p_imp = sub.add_parser("import-citations", help="import pre-downloaded *_emerging.xlsx citations into sidecars")
    p_imp.add_argument("paths", nargs="*", help="xlsx files/globs (default: data/*/*_emerging.xlsx)")
    p_imp.add_argument("--data-dir", default="data")
    p_imp.set_defaults(func=cmd_import_citations)

    p_crawl = sub.add_parser("crawl", help="run OpenReview crawl jobs from config/crawl.json")
    p_crawl.add_argument("--crawl-config", default="config/crawl.json")
    p_crawl.add_argument("--raw-dir", default="data/scrapy_crawl")
    p_crawl.add_argument("--only", default=None, help="comma-separated tokens to crawl (e.g. icml)")
    p_crawl.add_argument("--dry-run", action="store_true", help="print commands, run nothing")
    p_crawl.set_defaults(func=cmd_crawl)

    p_proc = sub.add_parser("process", help="merge crawled JSON into per-conference CSVs")
    p_proc.add_argument("--raw-dir", default="data/scrapy_crawl")
    p_proc.add_argument("--out-dir", default="data")
    p_proc.set_defaults(func=cmd_process)

    p_exp = sub.add_parser("export-site", help="build static-site JSON for GitHub Pages")
    p_exp.add_argument("--data-dir", default="data", help="root holding <year>/ folders")
    p_exp.add_argument("--out-dir", default="docs/data", help="site data output directory")
    p_exp.add_argument("--top-n", type=int, default=5)
    p_exp.add_argument("--min-prev", type=int, default=1)
    p_exp.add_argument("--min-count", type=int, default=10)
    p_exp.add_argument("--abstract-chars", type=int, default=240)
    p_exp.set_defaults(func=cmd_export_site)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    # The candidates subcommand has its own --model default handling.
    if getattr(args, "model", None) is None and args.command == "candidates":
        from ai_trend.candidates import DEFAULT_MODEL_PATH

        args.model = str(DEFAULT_MODEL_PATH)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
