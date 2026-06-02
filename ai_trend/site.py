"""Pre-build compact JSON for the static GitHub Pages site.

GitHub Pages is static, so the browser cannot read the CSVs directly. This module
exports:

* ``trends.json`` -- per conference-year top/emerging/fading + topic counts.
* ``papers/<LABEL>_<year>.json`` -- one shard per conference-year, loaded on
  demand when the user drills into a topic/year (keeps the initial payload small).
* ``manifest.json`` -- conferences, available shards, years, and the topics that
  actually occur (drives the site's filters).

Conference identity and year come from the **file location** via the registry
(not the unreliable in-file ``source``/``year`` columns).
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import TYPE_CHECKING

from ai_trend.registry import ConferenceRegistry
from ai_trend.taxonomy import Taxonomy
from ai_trend.trends import (
    DEFAULT_DATA_DIR,
    DEFAULT_MIN_COUNT,
    DEFAULT_MIN_PREV,
    DEFAULT_TOP_N,
    compute_all_trends,
    discover_conference_years,
    trend_to_dict,
)

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_trend.registry import ConferenceRegistry as _Reg

DEFAULT_SITE_DATA_DIR = Path(__file__).resolve().parent.parent / "docs" / "data"
DEFAULT_ABSTRACT_CHARS = 240


def parse_authors(raw: object) -> list[str]:
    """Turn the CSV ``authors`` cell (``"'A', 'B'"``) into a clean list."""
    if not isinstance(raw, str) or not raw.strip():
        return []
    try:
        value = ast.literal_eval("[" + raw + "]")
        return [str(a).strip() for a in value if str(a).strip()]
    except (ValueError, SyntaxError):
        return [raw.strip()]


def _text(value: object) -> str:
    return value.strip() if isinstance(value, str) else ""


def build_paper_record(
    row: dict,
    conference: str,
    year: int,
    abstract_chars: int = DEFAULT_ABSTRACT_CHARS,
    citations: dict | None = None,
    arxiv: dict | None = None,
) -> dict:
    topics = [t for t in str(row.get("topic", "")).split(";") if t and t != "nan"]
    abstract = _text(row.get("abstract"))
    if len(abstract) > abstract_chars:
        abstract = abstract[:abstract_chars].rstrip() + "…"
    title = _text(row.get("title"))
    record = {
        "title": title,
        "authors": parse_authors(row.get("authors")),
        "topics": topics,
        "conference": conference,
        "year": year,
        "pdf": _text(row.get("pdf_link")),
        "abstract": abstract,
    }
    if citations is not None:
        cited = citations.get(title)
        if cited is not None:
            record["citations"] = cited
    if arxiv:
        arxiv_id = arxiv.get(title)
        if arxiv_id:
            record["arxiv"] = arxiv_id
    return record


def export_site(
    out_dir: Path | str = DEFAULT_SITE_DATA_DIR,
    *,
    taxonomy: Taxonomy | None = None,
    registry: "ConferenceRegistry | None" = None,
    data_dir: Path | str = DEFAULT_DATA_DIR,
    top_n: int = DEFAULT_TOP_N,
    min_prev: int = DEFAULT_MIN_PREV,
    min_count: int = DEFAULT_MIN_COUNT,
    abstract_chars: int = DEFAULT_ABSTRACT_CHARS,
) -> dict:
    """Write the site's JSON data files and return the manifest."""
    import pandas as pd

    taxonomy = taxonomy or Taxonomy.load()
    registry = registry or ConferenceRegistry.load()
    out_dir = Path(out_dir)
    (out_dir / "papers").mkdir(parents=True, exist_ok=True)

    trends = compute_all_trends(
        taxonomy, data_dir, top_n=top_n, min_prev=min_prev, min_count=min_count
    )
    trends_payload = [trend_to_dict(t, include_counts=True) for t in trends]
    (out_dir / "trends.json").write_text(
        json.dumps(trends_payload, ensure_ascii=False), encoding="utf-8"
    )

    index = discover_conference_years(data_dir, registry.token_to_label)
    shards: list[dict] = []
    seen_topics: set[str] = set()
    for conference in sorted(index):
        for year in sorted(index[conference]):
            topics_path = index[conference][year]
            df = pd.read_csv(topics_path)
            # optional sidecars produced by `ai-trend citations` / `verify-citations`
            cite_path = Path(str(topics_path) + ".citations.json")
            citations = json.loads(cite_path.read_text(encoding="utf-8")) if cite_path.exists() else None
            arxiv_path = Path(str(topics_path) + ".arxiv.json")
            arxiv = json.loads(arxiv_path.read_text(encoding="utf-8")) if arxiv_path.exists() else None
            records = [
                build_paper_record(row, conference, year, abstract_chars, citations, arxiv)
                for row in df.to_dict("records")
            ]
            for record in records:
                seen_topics.update(record["topics"])
            rel = f"papers/{conference}_{year}.json"
            (out_dir / rel).write_text(
                json.dumps(records, ensure_ascii=False), encoding="utf-8"
            )
            shards.append({"conference": conference, "year": year, "count": len(records), "file": rel})

    manifest = {
        "conferences": [
            {"key": c.key, "label": c.label, "name": c.name} for c in registry.conferences
        ],
        "topics": sorted(seen_topics),
        "years": sorted({s["year"] for s in shards}),
        "shards": shards,
    }
    (out_dir / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False), encoding="utf-8"
    )
    return manifest
