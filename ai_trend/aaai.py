"""Fetch AAAI main-track paper metadata from OpenAlex.

AAAI is not on OpenReview or CVF, and its OJS proceedings have no clean per-year
listing URL. OpenAlex indexes the proceedings under a single source id and exposes
title, authors, abstract (as an inverted index), and a landing page — so it is the
most reliable programmatic source. We reuse the project's existing OpenAlex
conventions (``OPENALEX_API_KEY`` / polite-pool ``mailto``; see citations.py).

Main-track filtering: OpenAlex lumps the technical track together with student
abstracts, demos, and senior-member tracks (~2,900 works/year). It exposes no
clean track label, so we use a **page-count heuristic** — main-track papers run
~7-9 pages while student abstracts/demos are 1-3. Works shorter than
:data:`MIN_MAIN_TRACK_PAGES` (or with no page span) are dropped. The dropped
count is reported by the caller. This is a heuristic, not an exact filter.

Output matches :data:`ai_trend.ingest.RECORD_COLUMNS`.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import TYPE_CHECKING

from ai_trend.ingest import RECORD_COLUMNS

if TYPE_CHECKING:  # pragma: no cover - typing only
    import requests

OPENALEX_WORKS = "https://api.openalex.org/works"
# "Proceedings of the AAAI Conference on Artificial Intelligence" (ISSN 2159-5399).
AAAI_SOURCE_ID = "S4210191458"
PAGE_LIMIT = 200  # OpenAlex max per_page
THROTTLE = 0.15  # be polite; matches the citations.py OpenAlex throttle
# Drop works shorter than this many pages (student abstracts / demos / posters).
MIN_MAIN_TRACK_PAGES = 4
# Only request the fields we use, to keep responses small.
_SELECT = "id,title,authorships,abstract_inverted_index,biblio,primary_location,doi"


def reconstruct_abstract(inverted_index: dict | None) -> str:
    """Rebuild plain text from an OpenAlex ``abstract_inverted_index``."""
    if not isinstance(inverted_index, dict) or not inverted_index:
        return ""
    positions: list[tuple[int, str]] = []
    for word, idxs in inverted_index.items():
        if isinstance(idxs, list):
            positions.extend((i, word) for i in idxs)
    positions.sort(key=lambda p: p[0])
    return " ".join(word for _, word in positions)


def page_count(work: dict) -> int | None:
    """Page span from ``biblio.first_page``/``last_page``; ``None`` if unknown."""
    biblio = work.get("biblio") or {}
    try:
        first = int(biblio["first_page"])
        last = int(biblio["last_page"])
    except (KeyError, TypeError, ValueError):
        return None
    span = last - first + 1
    return span if span > 0 else None


def _format_authors(authorships: list) -> str:
    names = []
    for a in authorships or []:
        author = a.get("author") or {}
        name = (author.get("display_name") or "").strip()
        if name:
            names.append(name)
    return ", ".join(f"'{n}'" for n in names)


def _landing(work: dict) -> str:
    loc = work.get("primary_location") or {}
    return loc.get("landing_page_url") or work.get("doi") or ""


def work_to_record(work: dict, year: int, *, min_pages: int = MIN_MAIN_TRACK_PAGES) -> dict | None:
    """Convert an OpenAlex work to a record, or ``None`` if filtered out.

    Filtered out when the title is empty or the page count is unknown / below
    ``min_pages`` (the main-track heuristic).
    """
    title = (work.get("title") or "").strip()
    if not title:
        return None
    pages = page_count(work)
    if pages is None or pages < min_pages:
        return None
    return {
        "title": title,
        "year": year,
        "source": "AAAI",
        "authors": _format_authors(work.get("authorships")),
        "class": "",
        "keywords": "",
        "abstract": reconstruct_abstract(work.get("abstract_inverted_index")),
        "pdf_link": _landing(work),
    }


def fetch_aaai(
    year: int,
    *,
    source_id: str = AAAI_SOURCE_ID,
    min_pages: int = MIN_MAIN_TRACK_PAGES,
    mailto: str = "",
    base: str = OPENALEX_WORKS,
    limit: int = PAGE_LIMIT,
    throttle: float = THROTTLE,
    session: "requests.Session | None" = None,
) -> list[dict]:
    """Paginate AAAI proceedings for ``year`` into main-track records.

    Uses OpenAlex cursor pagination. Records failing the page-count heuristic are
    dropped (see module docstring).
    """
    import requests

    sess = session or requests.Session()
    api_key = os.environ.get("OPENALEX_API_KEY", "").strip()
    records: list[dict] = []
    seen: set[str] = set()
    cursor = "*"
    while cursor:
        params = {
            "filter": f"publication_year:{year},primary_location.source.id:{source_id}",
            "select": _SELECT,
            "per-page": limit,
            "cursor": cursor,
        }
        if mailto:
            params["mailto"] = mailto  # OpenAlex "polite pool"
        if api_key:
            params["api_key"] = api_key
        resp = sess.get(base, params=params, headers={"User-Agent": "ai-trend/0.1"}, timeout=60)
        resp.raise_for_status()
        payload = resp.json()
        for work in payload.get("results", []):
            rec = work_to_record(work, year, min_pages=min_pages)
            if rec and rec["title"] not in seen:
                seen.add(rec["title"])
                records.append(rec)
        cursor = (payload.get("meta") or {}).get("next_cursor")
        if not payload.get("results"):
            break
        if throttle:
            time.sleep(throttle)
    return records


def fetch_to_csv(year: int, out_path: Path | str, **kwargs) -> int:
    """Fetch AAAI main-track papers and write a source CSV; returns the row count."""
    import pandas as pd

    records = fetch_aaai(year, **kwargs)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records, columns=RECORD_COLUMNS).to_csv(out_path, index=False)
    return len(records)
