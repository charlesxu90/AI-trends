"""Citation counts from Semantic Scholar (S2AG), hardened and cached.

Ported from ``2.popular_topics.ipynb`` (which used the ``semanticscholar`` pkg).
This calls the public relevance-search endpoint directly with retry/backoff, a
resumable on-disk cache, and an explicit distinction between "0 citations" and
"lookup failed" (``None``).

The unauthenticated tier is heavily rate-limited (429s are common), so callers
should bound the work to a subset of papers (e.g. the conference-year's
top/emerging-topic papers) — see :func:`titles_for_topics`.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd
    import requests

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
DEFAULT_THROTTLE = 1.1  # seconds between calls (public tier ~1 req/s)
DEFAULT_RETRIES = 4
DEFAULT_BACKOFF = 2.0  # seconds, doubled each retry


def search_citation(
    title: str,
    session: "requests.Session",
    *,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    sleep=time.sleep,
) -> int | None:
    """Return the citation count for the best title match, or ``None`` on failure.

    ``None`` (lookup failed / no match) is deliberately distinct from ``0``
    (paper found, zero citations).
    """
    params = {"query": title.replace("-", " "), "fields": "title,citationCount", "limit": 1}
    for attempt in range(retries + 1):
        try:
            resp = session.get(S2_SEARCH, params=params, timeout=30,
                               headers={"User-Agent": "ai-trend/0.1"})
            if resp.status_code == 429:
                if attempt < retries:
                    sleep(backoff * (2 ** attempt))
                    continue
                return None
            resp.raise_for_status()
            data = resp.json().get("data") or []
            if not data:
                return None
            return data[0].get("citationCount")
        except Exception:  # network/parse error -> retry, then give up to None
            if attempt < retries:
                sleep(backoff * (2 ** attempt))
                continue
            return None
    return None


def load_cache(path: Path | str) -> dict[str, int | None]:
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else {}


def save_cache(path: Path | str, cache: dict) -> None:
    Path(path).write_text(json.dumps(cache, ensure_ascii=False, indent=0), encoding="utf-8")


_EMERGING_SUFFIX = "_emerging.xlsx"


def sidecar_for_xlsx(xlsx_path: Path | str) -> Path:
    """``<csv>_topics.csv_emerging.xlsx`` -> ``<csv>_topics.csv.citations.json``."""
    s = str(xlsx_path)
    if not s.endswith(_EMERGING_SUFFIX):
        raise ValueError(f"expected a *{_EMERGING_SUFFIX} file, got {s}")
    return Path(s[: -len(_EMERGING_SUFFIX)] + ".citations.json")


def import_emerging_xlsx(xlsx_path: Path | str, *, column: str = "ss_citations") -> dict[str, int]:
    """Read pre-downloaded citations from a ``*_emerging.xlsx`` into {title: count}."""
    import pandas as pd

    df = pd.read_excel(xlsx_path)
    if "title" not in df.columns or column not in df.columns:
        raise ValueError(f"{xlsx_path} lacks 'title'/{column!r} columns")
    out: dict[str, int] = {}
    for title, value in zip(df["title"], df[column]):
        if pd.isna(value) or not str(title).strip():
            continue
        out[str(title)] = int(value)
    return out


def merge_into_sidecar(xlsx_path: Path | str, *, column: str = "ss_citations") -> tuple[Path, int]:
    """Import an xlsx and merge it into the matching citations sidecar.

    Existing sidecar entries (e.g. fresher live fetches) are preserved; the xlsx
    fills in titles not already present. Returns ``(sidecar_path, added_count)``.
    """
    sidecar = sidecar_for_xlsx(xlsx_path)
    imported = import_emerging_xlsx(xlsx_path, column=column)
    existing = load_cache(sidecar)
    before = len(existing)
    merged = {**imported, **existing}  # existing (live fetch) wins on overlap
    save_cache(sidecar, merged)
    return sidecar, len(merged) - before


def titles_for_topics(df: "pd.DataFrame", topics: Iterable[str]) -> list[str]:
    """Titles of papers whose ``topic`` column matches any of ``topics``."""
    topic_set = {t for t in topics}
    out: list[str] = []
    for title, cell in zip(df["title"], df["topic"].fillna("")):
        labels = {t for t in str(cell).split(";") if t}
        if labels & topic_set:
            out.append(str(title))
    return out


def fetch_citations(
    titles: list[str],
    cache_path: Path | str,
    session: "requests.Session",
    *,
    throttle: float = DEFAULT_THROTTLE,
    sleep=time.sleep,
    log=lambda *_: None,
) -> dict[str, int | None]:
    """Fetch citations for ``titles`` (resumable via cache), saving incrementally.

    Titles already present in the cache are skipped. Returns the full cache.
    """
    cache = load_cache(cache_path)
    pending = [t for t in titles if t not in cache]
    log(f"citations: {len(pending)} to fetch ({len(titles) - len(pending)} cached)")
    for i, title in enumerate(pending, 1):
        cache[title] = search_citation(title, session, sleep=sleep)
        if i % 25 == 0 or i == len(pending):
            save_cache(cache_path, cache)
            log(f"citations: {i}/{len(pending)}")
        if i < len(pending):
            sleep(throttle)
    save_cache(cache_path, cache)
    return cache
