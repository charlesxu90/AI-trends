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
import os
import re
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

# Sentinel: the request itself failed (429/network), as opposed to a successful
# lookup that found no title match. Callers must NOT cache this — it should be
# retried — whereas a genuine no-match is cached as None (a verified negative).
FETCH_FAILED = object()

# Abort a fetch run after this many consecutive request failures: a sign S2 is
# rate-limiting hard, so grinding through the rest just wastes time (and the run
# is resumable — re-run when S2 is reachable or S2_API_KEY is set).
MAX_CONSECUTIVE_FAILURES = 10


def _s2_headers() -> dict[str, str]:
    """Request headers, adding the S2 API key from ``S2_API_KEY`` when present.

    The unauthenticated pool is shared and hard-429s under load; a free key
    (https://www.semanticscholar.org/product/api) grants a dedicated rate limit.
    """
    headers = {"User-Agent": "ai-trend/0.1"}
    key = os.environ.get("S2_API_KEY", "").strip()
    if key:
        headers["x-api-key"] = key
    return headers


TITLE_MATCH_JACCARD = 0.85


def _normalize_title(title: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", str(title).lower()).strip()


def titles_match(query: str, candidate: str) -> bool:
    """True if two titles refer to the same paper.

    Guards against Semantic Scholar's relevance search returning a *different*,
    often more-cited paper for a generic title (the cause of inflated counts).
    Exact normalised match, else high token-set overlap (Jaccard).
    """
    nq, nc = _normalize_title(query), _normalize_title(candidate)
    if not nq or not nc:
        return False
    if nq == nc:
        return True
    tq, tc = set(nq.split()), set(nc.split())
    union = tq | tc
    return bool(union) and len(tq & tc) / len(union) >= TITLE_MATCH_JACCARD


def _s2_request(
    session: "requests.Session",
    query: str,
    fields: str,
    limit: int,
    *,
    retries: int,
    backoff: float,
    sleep,
) -> list | None:
    """GET the S2 relevance-search ``data`` list (retry/backoff), or None on failure."""
    params = {"query": query.replace("-", " "), "fields": fields, "limit": limit}
    for attempt in range(retries + 1):
        try:
            resp = session.get(S2_SEARCH, params=params, timeout=30,
                               headers=_s2_headers())
            if resp.status_code == 429:
                if attempt < retries:
                    sleep(backoff * (2 ** attempt))
                    continue
                return None
            resp.raise_for_status()
            return resp.json().get("data") or []
        except Exception:  # network/parse error
            if attempt < retries:
                sleep(backoff * (2 ** attempt))
                continue
            return None
    return None


def search_citation(
    title: str,
    session: "requests.Session",
    *,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    sleep=time.sleep,
) -> int | None:
    """Raw top-hit citation count (no title verification). Prefer
    :func:`search_paper_verified` for trustworthy counts."""
    data = _s2_request(session, title, "title,citationCount", 1,
                       retries=retries, backoff=backoff, sleep=sleep)
    return (data[0].get("citationCount") if data else None)


OPENALEX_WORKS = "https://api.openalex.org/works"


def _openalex_request(
    session: "requests.Session",
    title: str,
    *,
    mailto: str,
    per_page: int,
    retries: int,
    backoff: float,
    sleep,
) -> list | None:
    """GET the OpenAlex ``results`` list for a title search, or None on failure.

    Commas/colons/pipes break OpenAlex filter syntax, so they're blanked (the
    search is fuzzy; the caller verifies the title anyway).
    """
    cleaned = re.sub(r"[,:|]+", " ", str(title)).strip()
    params = {"filter": f"title.search:{cleaned}", "per-page": per_page}
    if mailto:
        params["mailto"] = mailto  # OpenAlex "polite pool" — higher, more reliable limits
    for attempt in range(retries + 1):
        try:
            resp = session.get(OPENALEX_WORKS, params=params, timeout=30,
                               headers={"User-Agent": "ai-trend/0.1"})
            if resp.status_code == 429:
                if attempt < retries:
                    sleep(backoff * (2 ** attempt))
                    continue
                return None
            resp.raise_for_status()
            return resp.json().get("results") or []
        except Exception:
            if attempt < retries:
                sleep(backoff * (2 ** attempt))
                continue
            return None
    return None


def search_openalex_verified(
    title: str,
    session: "requests.Session",
    *,
    mailto: str = "",
    limit: int = 5,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    sleep=time.sleep,
) -> dict | None:
    """Citation count for the OpenAlex work whose title matches ``title``.

    Key-free alternative to :func:`search_paper_verified` (Semantic Scholar's
    public tier hard-429s). Returns ``None`` if no result matches, or
    :data:`FETCH_FAILED` if the request itself failed.
    """
    results = _openalex_request(session, title, mailto=mailto, per_page=limit,
                                retries=retries, backoff=backoff, sleep=sleep)
    if results is None:
        return FETCH_FAILED
    for result in results:
        candidate = result.get("title") or result.get("display_name") or ""
        if titles_match(title, candidate):
            return {
                "citationCount": result.get("cited_by_count"),
                "arxiv": None,
                "title": candidate,
            }
    return None


def search_paper_verified(
    title: str,
    session: "requests.Session",
    *,
    limit: int = 5,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    sleep=time.sleep,
) -> dict | None:
    """Citation count + arXiv id for the result whose title actually matches.

    Scans the top ``limit`` results and returns the first whose title matches
    ``title`` (see :func:`titles_match`). Returns ``None`` if no result matches —
    so an unverifiable/wrong hit is never written as a citation count — or
    :data:`FETCH_FAILED` if the request itself failed (429/network).
    """
    data = _s2_request(session, title, "title,citationCount,externalIds,year", limit,
                       retries=retries, backoff=backoff, sleep=sleep)
    if data is None:
        return FETCH_FAILED  # request failed — retry later, do not cache
    for result in data:
        if titles_match(title, result.get("title", "")):
            external = result.get("externalIds") or {}
            return {
                "citationCount": result.get("citationCount"),
                "arxiv": external.get("ArXiv"),
                "title": result.get("title"),
            }
    return None


def arxiv_cache_path(citations_cache_path: Path | str) -> Path:
    s = str(citations_cache_path)
    return Path(s[: -len(".citations.json")] + ".arxiv.json" if s.endswith(".citations.json")
                else s + ".arxiv.json")


import glob as _glob

# Tracked (not gitignored) so snapshots accumulate across CI refreshes.
DEFAULT_HISTORY_DIR = Path(__file__).resolve().parent.parent / "citation-history"


def collect_current_counts(data_dir: Path | str = "data") -> dict[str, int]:
    """Flatten every paper's current (non-null) citation count across all sidecars."""
    counts: dict[str, int] = {}
    for f in _glob.glob(str(Path(data_dir) / "*" / "*.citations.json")):
        for title, value in load_cache(f).items():
            if isinstance(value, int):
                counts[title] = value
    return counts


def snapshot_citations(
    date_str: str, *, data_dir: Path | str = "data", history_dir: Path | str = DEFAULT_HISTORY_DIR
) -> Path:
    """Write a dated snapshot of current citation counts; returns its path."""
    counts = collect_current_counts(data_dir)
    history_dir = Path(history_dir)
    history_dir.mkdir(parents=True, exist_ok=True)
    out = history_dir / f"{date_str}.json"
    out.write_text(json.dumps(counts, ensure_ascii=False), encoding="utf-8")
    return out


def latest_deltas(history_dir: Path | str = DEFAULT_HISTORY_DIR) -> dict[str, int]:
    """Citation gain per paper between the two most recent snapshots (empty if <2)."""
    files = sorted(_glob.glob(str(Path(history_dir) / "*.json")))
    if len(files) < 2:
        return {}
    prev = load_cache(files[-2])
    cur = load_cache(files[-1])
    return {
        t: cur[t] - prev[t]
        for t in cur
        if t in prev and isinstance(cur[t], int) and isinstance(prev[t], int)
    }


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


def _progress_bar(total: int):
    """A tqdm bar over ``total`` items, or None if tqdm is unavailable."""
    try:
        from tqdm import tqdm
    except ImportError:  # pragma: no cover - tqdm is a pinned dependency
        return None
    return tqdm(total=total, unit="paper", desc="citations", dynamic_ncols=True)


def fetch_citations(
    titles: list[str],
    cache_path: Path | str,
    session: "requests.Session",
    *,
    throttle: float = DEFAULT_THROTTLE,
    sleep=time.sleep,
    log=lambda *_: None,
    searcher=search_paper_verified,
    progress: bool = False,
) -> dict[str, int | None]:
    """Fetch citations for ``titles`` (resumable via cache), saving incrementally.

    Titles already present in the cache are skipped. ``searcher`` is the lookup
    used per title (default Semantic Scholar; pass :func:`search_openalex_verified`
    for the key-free OpenAlex source). With ``progress=True`` a tqdm bar is shown.
    Returns the full cache.
    """
    cache = load_cache(cache_path)
    apath = arxiv_cache_path(cache_path)
    arxiv = load_cache(apath)
    pending = [t for t in titles if t not in cache]
    log(f"citations: {len(pending)} to fetch ({len(titles) - len(pending)} cached)")
    consecutive_failures = 0
    bar = _progress_bar(len(pending)) if progress else None
    try:
        for i, title in enumerate(pending, 1):
            result = searcher(title, session, sleep=sleep)
            if bar is not None:
                bar.update(1)
            if result is FETCH_FAILED:
                # Request failed (429/network): leave uncached so it retries next run.
                consecutive_failures += 1
                if consecutive_failures >= MAX_CONSECUTIVE_FAILURES:
                    log(f"citations: aborting after {consecutive_failures} consecutive "
                        f"failures (rate-limited?); {i - 1}/{len(pending)} attempted — re-run to resume")
                    break
                if i < len(pending):
                    sleep(throttle)
                continue
            consecutive_failures = 0
            cache[title] = result["citationCount"] if result else None  # None = verified no-match
            if result and result.get("arxiv"):
                arxiv[title] = result["arxiv"]
            if i % 25 == 0 or i == len(pending):
                save_cache(cache_path, cache)
                save_cache(apath, arxiv)
                if not progress:  # the bar already conveys position
                    log(f"citations: {i}/{len(pending)}")
            if i < len(pending):
                sleep(throttle)
    finally:
        if bar is not None:
            bar.close()
    save_cache(cache_path, cache)
    save_cache(apath, arxiv)
    return cache


def verify_existing(
    cache_path: Path | str,
    session: "requests.Session",
    *,
    min_count: int = 150,
    throttle: float = DEFAULT_THROTTLE,
    sleep=time.sleep,
    log=lambda *_: None,
) -> dict:
    """Re-verify cached counts above ``min_count`` (likely wrong title-search hits).

    Replaces each with the title-verified count, or ``None`` if no result's title
    matches. Also records any arXiv ids found. Returns a summary.
    """
    cache = load_cache(cache_path)
    apath = arxiv_cache_path(cache_path)
    arxiv = load_cache(apath)
    suspects = [t for t, c in cache.items() if isinstance(c, int) and c > min_count]
    log(f"verify: {len(suspects)} cached counts > {min_count}")
    changed = dropped = 0
    for i, title in enumerate(suspects, 1):
        result = search_paper_verified(title, session, sleep=sleep)
        if result is FETCH_FAILED:
            continue  # request failed — leave the existing count untouched
        new = result["citationCount"] if result else None
        if new is None:
            dropped += 1
        if new != cache.get(title):
            changed += 1
        cache[title] = new
        if result and result.get("arxiv"):
            arxiv[title] = result["arxiv"]
        if i % 10 == 0 or i == len(suspects):
            save_cache(cache_path, cache)
            save_cache(apath, arxiv)
            log(f"verify: {i}/{len(suspects)}")
        if i < len(suspects):
            sleep(throttle)
    save_cache(cache_path, cache)
    save_cache(apath, arxiv)
    return {"checked": len(suspects), "changed": changed, "unverified": dropped}
