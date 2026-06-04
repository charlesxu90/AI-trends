"""Citation counts from Semantic Scholar (S2AG), hardened and cached.

Ported from the original notebook (which used the ``semanticscholar`` pkg).
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
from dataclasses import dataclass
from functools import partial
from pathlib import Path
from typing import TYPE_CHECKING, Callable, Iterable

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd
    import requests

S2_SEARCH = "https://api.semanticscholar.org/graph/v1/paper/search"
DEFAULT_THROTTLE = 1.1  # seconds between calls (public tier ~1 req/s)
DEFAULT_RETRIES = 4
DEFAULT_BACKOFF = 2.0  # seconds, doubled each retry

# A failed lookup (429/network) — NOT a no-match. Callers must not cache it (a
# genuine no-match is cached as None). ``retry_after`` carries the server's
# Retry-After (seconds) when provided, so a source can be backed off for exactly
# as long as it asks rather than a guessed interval.
@dataclass(frozen=True)
class _Failed:
    retry_after: float | None = None


FETCH_FAILED = _Failed()  # generic failure, no Retry-After hint


def _is_failed(result) -> bool:
    return isinstance(result, _Failed)


def _retry_after_seconds(resp) -> float | None:
    headers = getattr(resp, "headers", None)
    raw = headers.get("Retry-After") if hasattr(headers, "get") else None
    try:
        return float(raw) if raw is not None else None
    except (TypeError, ValueError):
        return None


# Abort a single-source fetch run after this many consecutive request failures: a
# sign the source is rate-limiting hard, so grinding through the rest just wastes
# time (and the run is resumable).
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
) -> "list | _Failed":
    """GET the S2 relevance-search ``data`` list, or :class:`_Failed` on failure."""
    params = {"query": query.replace("-", " "), "fields": fields, "limit": limit}
    for attempt in range(retries + 1):
        try:
            resp = session.get(S2_SEARCH, params=params, timeout=30,
                               headers=_s2_headers())
            if resp.status_code == 429:
                if attempt < retries:
                    sleep(backoff * (2 ** attempt))
                    continue
                ra = _retry_after_seconds(resp)
                return _Failed(ra) if ra is not None else FETCH_FAILED
            resp.raise_for_status()
            return resp.json().get("data") or []
        except Exception:  # network/parse error
            if attempt < retries:
                sleep(backoff * (2 ** attempt))
                continue
            return FETCH_FAILED
    return FETCH_FAILED


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
    if _is_failed(data) or not data:
        return None
    return data[0].get("citationCount")


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
                ra = _retry_after_seconds(resp)
                return _Failed(ra) if ra is not None else FETCH_FAILED
            resp.raise_for_status()
            return resp.json().get("results") or []
        except Exception:
            if attempt < retries:
                sleep(backoff * (2 ** attempt))
                continue
            return FETCH_FAILED
    return FETCH_FAILED


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
    if _is_failed(results):
        return results
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
    if _is_failed(data):
        return data  # request failed — retry later, do not cache
    for result in data:
        if titles_match(title, result.get("title", "")):
            external = result.get("externalIds") or {}
            return {
                "citationCount": result.get("citationCount"),
                "arxiv": external.get("ArXiv"),
                "title": result.get("title"),
            }
    return None


CROSSREF_WORKS = "https://api.crossref.org/works"


def _crossref_request(
    session: "requests.Session",
    title: str,
    *,
    mailto: str,
    rows: int,
    retries: int,
    backoff: float,
    sleep,
) -> list | None:
    """GET Crossref ``message.items`` for a bibliographic title query, or None."""
    params = {
        "query.bibliographic": str(title),
        "rows": rows,
        "select": "title,is-referenced-by-count",
    }
    if mailto:
        params["mailto"] = mailto  # Crossref polite pool
    for attempt in range(retries + 1):
        try:
            resp = session.get(CROSSREF_WORKS, params=params, timeout=30,
                               headers={"User-Agent": "ai-trend/0.1"})
            if resp.status_code == 429:
                if attempt < retries:
                    sleep(backoff * (2 ** attempt))
                    continue
                ra = _retry_after_seconds(resp)
                return _Failed(ra) if ra is not None else FETCH_FAILED
            resp.raise_for_status()
            return resp.json().get("message", {}).get("items") or []
        except Exception:
            if attempt < retries:
                sleep(backoff * (2 ** attempt))
                continue
            return FETCH_FAILED
    return FETCH_FAILED


def search_crossref_verified(
    title: str,
    session: "requests.Session",
    *,
    mailto: str = "",
    limit: int = 5,
    retries: int = DEFAULT_RETRIES,
    backoff: float = DEFAULT_BACKOFF,
    sleep=time.sleep,
) -> dict | None:
    """Citation count (``is-referenced-by-count``) for the Crossref work whose title
    matches ``title``.

    Crossref relevance search is order-insensitive and happily returns near-titles
    (e.g. "Is Attention All You Need?" for "Attention Is All You Need"), which the
    token-set Jaccard in :func:`titles_match` would wrongly accept — so this requires
    an **exact normalised** title match. Returns ``None`` (no match) or
    :data:`FETCH_FAILED` (request failed).
    """
    items = _crossref_request(session, title, mailto=mailto, rows=limit,
                              retries=retries, backoff=backoff, sleep=sleep)
    if _is_failed(items):
        return items
    nq = _normalize_title(title)
    for item in items:
        cand = (item.get("title") or [""])[0]
        if _normalize_title(cand) == nq:  # strict: exact normalised, not Jaccard
            return {
                "citationCount": item.get("is-referenced-by-count"),
                "arxiv": None,
                "title": cand,
            }
    return None


def arxiv_cache_path(citations_cache_path: Path | str) -> Path:
    s = str(citations_cache_path)
    return Path(s[: -len(".citations.json")] + ".arxiv.json" if s.endswith(".citations.json")
                else s + ".arxiv.json")


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
            if _is_failed(result):
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


# ---- multi-source fallback ---------------------------------------------------

@dataclass(frozen=True)
class Provider:
    """A title→citation lookup with the pacing/backoff constraints of its source."""
    name: str
    search: Callable  # (title, session, *, sleep) -> dict | None | _Failed
    throttle: float   # min seconds between calls to this source (its allowed rate)
    cooldown: float   # default backoff after a rate-limit, when no Retry-After given


# Per-source constraints (https URLs' published / observed limits):
#   openalex  — key-free budget is ~1k requests then a multi-hour reset; it sends a
#               precise Retry-After, so honour that and use a long default fallback.
#   s2        — shared public pool ~1 req/s; fluctuates, so retry after minutes.
#   crossref  — polite pool is fast (~tens/s) and rarely caps; short backoff.
#   retries  — attempts per title before giving up. OpenAlex/Crossref fail fast
#              (their 429 = real budget exhaustion, hand off immediately); S2's
#              public 429 is a *transient* shared-pool collision, so retry through
#              it a few times with exponential backoff.
#
# S2 unauthenticated policy (per Semantic Scholar): ≤1 RPS per IP on a global shared
# pool, requests must be STRICTLY SERIAL (parallel unauth requests get blocked
# almost immediately), use adaptive exponential backoff on 429, and cache. We honor
# all of these: a single serial runner, 1.1s throttle (<1 RPS), exponential backoff
# in _s2_request, Retry-After honored, and a resumable on-disk cache. A free API key
# (S2_API_KEY) lifts us out of the shared pool to a dedicated 1 RPS.
_PROVIDER_SPEC = {
    "openalex": {"throttle": 0.15, "cooldown": 21600.0, "retries": 1},  # 6h fallback if no Retry-After
    "s2": {"throttle": 1.1, "cooldown": 30.0, "retries": 4},            # serial, ~1 RPS, exp-backoff
    "crossref": {"throttle": 0.1, "cooldown": 120.0, "retries": 1},
}


def build_providers(names: list[str], *, mailto: str = "") -> list[Provider]:
    """Build a fallback chain from source keys (order = priority).

    Per-source throttle/cooldown/retries come from :data:`_PROVIDER_SPEC`, tuned to
    each source's policy: OpenAlex/Crossref hand off fast on a real rate-limit, while
    S2 retries through its transient shared-pool 429s at ~1 req/s.
    """
    fn = {
        "openalex": lambda r: partial(search_openalex_verified, mailto=mailto, retries=r, backoff=1.0),
        "s2": lambda r: partial(search_paper_verified, retries=r, backoff=1.0),
        "crossref": lambda r: partial(search_crossref_verified, mailto=mailto, retries=r, backoff=1.0),
    }
    out: list[Provider] = []
    for n in names:
        n = n.strip()
        if n not in fn:
            raise ValueError(f"unknown citation source: {n!r} (choose from {sorted(fn)})")
        spec = _PROVIDER_SPEC[n]
        out.append(Provider(n, fn[n](spec["retries"]), spec["throttle"], spec["cooldown"]))
    return out


def fetch_citations_multi(
    titles: list[str],
    cache_path: Path | str,
    session: "requests.Session",
    providers: list[Provider],
    *,
    cap_sleep: float = 3600.0,
    sleep=time.sleep,
    time_fn=time.monotonic,
    log=lambda *_: None,
    progress: bool = False,
) -> dict[str, int | None]:
    """Fetch citations trying several sources with fallback (resumable, incremental).

    For each title the providers are tried in priority order; the first verified
    hit wins. A provider that rate-limits is skipped for the server's ``Retry-After``
    (or its default ``cooldown``) so the others keep going — "as one sleeps, the
    other downloads". Pacing between calls uses the *resolving* source's throttle.
    A title is cached as ``None`` only when *every* provider was reachable and all
    returned no-match. When all providers are cooling down, sleeps until the
    soonest is free (capped at ``cap_sleep`` so a multi-hour OpenAlex reset is
    re-checked periodically). Counts from different sources are interchangeable.
    """
    cache = load_cache(cache_path)
    apath = arxiv_cache_path(cache_path)
    arxiv = load_cache(apath)
    remaining = [t for t in titles if t not in cache]
    log(f"citations: {len(remaining)} to fetch via {[p.name for p in providers]} "
        f"({len(titles) - len(remaining)} cached)")
    blocked_until: dict[str, float] = {p.name: 0.0 for p in providers}
    # providers that already verified no-match for a title — never re-query them
    # (a no-match answer won't change), so revisits only retry the blocked sources.
    no_match: dict[str, set] = {t: set() for t in remaining}
    n_providers = len(providers)
    bar = _progress_bar(len(remaining)) if progress else None
    saved = 0

    def _save():
        save_cache(cache_path, cache)
        save_cache(apath, arxiv)

    try:
        while remaining:
            now = time_fn()
            if all(blocked_until[p.name] > now for p in providers):  # every source cooling
                nap = min(cap_sleep, max(1.0, min(blocked_until.values()) - now))
                log(f"citations: all sources cooling down; sleeping {int(nap)}s "
                    f"({len(remaining)} remaining)")
                sleep(nap)
                continue
            still: list[str] = []
            progressed = False
            for title in remaining:
                now = time_fn()
                usable = [p for p in providers
                          if blocked_until[p.name] <= now and p.name not in no_match[title]]
                count = None
                pace = 0.0  # throttle of the source that resolved this title
                for p in usable:
                    r = p.search(title, session, sleep=sleep)
                    if _is_failed(r):
                        backoff = r.retry_after if r.retry_after is not None else p.cooldown
                        blocked_until[p.name] = time_fn() + backoff
                        log(f"citations: {p.name} rate-limited; backing off {int(backoff)}s")
                        continue
                    pace = p.throttle
                    if r is None:
                        no_match[title].add(p.name)  # remember — don't re-query this source
                        continue
                    count = r
                    break
                if count is not None:
                    cache[title] = count["citationCount"]
                    if count.get("arxiv"):
                        arxiv[title] = count["arxiv"]
                    progressed = True
                elif len(no_match[title]) == n_providers:
                    cache[title] = None  # every source verified no-match
                    progressed = True
                else:
                    still.append(title)  # blocked sources remain untried — revisit later
                if title in cache:
                    saved += 1
                    if bar is not None:
                        bar.update(1)
                    if saved % 25 == 0:
                        _save()
                if pace:
                    sleep(pace)
            remaining = still
            if remaining and not progressed:
                # nothing advanced and items remain → everything left is blocked
                now = time_fn()
                waits = [b - now for b in blocked_until.values() if b > now]
                if not waits:
                    break  # no cooldowns pending but stuck — avoid spinning
                nap = min(cap_sleep, max(1.0, min(waits)))
                log(f"citations: all sources cooling down; sleeping {int(nap)}s "
                    f"({len(remaining)} remaining)")
                sleep(nap)
    finally:
        if bar is not None:
            bar.close()
    _save()
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
