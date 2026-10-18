"""Fetch conference papers from PMLR (Proceedings of Machine Learning Research).

PMLR publishes ICML (and others) as ``https://proceedings.mlr.press/v<N>/``. Each
volume is a GitHub repo ``mlresearch/v<N>`` whose ``_config.yml`` names the venue
(``shortname: ICML``, ``year: '2026'``) and whose ``_posts/*.md`` hold one paper
each as YAML front matter (title, abstract, author list, pdf). This is the
key-free fallback for venues whose OpenReview API is unavailable to scripts.
Output matches :data:`ai_trend.ingest.RECORD_COLUMNS`; PMLR does not record
oral/poster, so ``class`` is left empty.
"""

from __future__ import annotations

import re
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import TYPE_CHECKING

from ai_trend.ingest import RECORD_COLUMNS

if TYPE_CHECKING:  # pragma: no cover - typing only
    import requests

GITHUB_API = "https://api.github.com/repos/mlresearch"
RAW_BASE = "https://raw.githubusercontent.com/mlresearch"
BRANCH = "gh-pages"
DEFAULT_WORKERS = 8
RETRIES = 5
_UA = {"User-Agent": "ai-trend/0.1"}
_VOLUME = re.compile(r"/v(\d+)(?:/|$)")
_FRONT_MATTER = re.compile(r"^---\s*\n(.*?)\n---", re.S)


def volume_from_url(url: str) -> str:
    """'https://proceedings.mlr.press/v306/' -> '306'."""
    from urllib.parse import urlparse

    m = _VOLUME.search(urlparse(url).path)
    if not m:
        raise ValueError(f"could not find a volume (e.g. /v306/) in the PMLR URL {url!r}")
    return m.group(1)


def _front_matter(text: str) -> dict | None:
    import yaml

    m = _FRONT_MATTER.match(text or "")
    if not m:
        return None
    data = yaml.safe_load(m.group(1))
    return data if isinstance(data, dict) else None


def parse_config(text: str) -> tuple[str, int]:
    """Volume ``_config.yml`` (plain YAML, may start with comments) -> (shortname, year)."""
    import yaml

    meta = next((d for d in yaml.safe_load_all(text) if isinstance(d, dict)), {})
    if not meta.get("shortname") or not meta.get("year"):
        raise ValueError("PMLR _config.yml is missing 'shortname' or 'year'")
    return str(meta["shortname"]), int(meta["year"])


def _author_list(authors) -> str:
    names = []
    for a in authors or []:
        if isinstance(a, dict):
            name = " ".join(str(a.get(k, "")).strip() for k in ("given", "family")).strip()
            if name:
                names.append(name)
    # match the OpenReview ``'A', 'B'`` format so site.parse_authors works uniformly
    return ", ".join(f"'{n}'" for n in names)


def parse_post(text: str, label: str, year: int) -> dict | None:
    """One ``_posts/*.md`` paper -> a record, or None if it has no title."""
    meta = _front_matter(text)
    if not meta or not str(meta.get("title") or "").strip():
        return None
    return {
        "title": " ".join(str(meta["title"]).split()),
        "year": year,
        "source": label,
        "authors": _author_list(meta.get("author")),
        "class": "",
        "keywords": "",
        "abstract": " ".join(str(meta.get("abstract") or "").split()),
        "pdf_link": str(meta.get("pdf") or ""),
    }


def _get(session: "requests.Session", url: str) -> "requests.Response":
    """GET with backoff on throttling / server errors; raises after RETRIES."""
    for attempt in range(RETRIES):
        resp = session.get(url, headers=_UA, timeout=60)
        if resp.status_code != 429 and resp.status_code < 500:
            resp.raise_for_status()
            return resp
        time.sleep(2 * 2 ** attempt)
    resp.raise_for_status()
    raise RuntimeError(f"giving up on {url} after {RETRIES} attempts")


def volume_info(volume: str, *, session: "requests.Session | None" = None) -> tuple[str, int]:
    """(shortname, year) of a PMLR volume, from its ``_config.yml``."""
    import requests

    sess = session or requests.Session()
    return parse_config(_get(sess, f"{RAW_BASE}/v{volume}/{BRANCH}/_config.yml").text)


def _post_paths(sess: "requests.Session", volume: str) -> list[str]:
    root = _get(sess, f"{GITHUB_API}/v{volume}/git/trees/{BRANCH}").json()["tree"]
    sha = next(t["sha"] for t in root if t["path"] == "_posts" and t["type"] == "tree")
    posts = _get(sess, f"{GITHUB_API}/v{volume}/git/trees/{sha}").json()["tree"]
    return sorted(t["path"] for t in posts if t["path"].endswith(".md"))


def fetch_pmlr(
    volume: str,
    label: str,
    year: int,
    *,
    session: "requests.Session | None" = None,
    workers: int = DEFAULT_WORKERS,
) -> list[dict]:
    """All papers of a PMLR volume as records (RECORD_COLUMNS)."""
    import requests

    sess = session or requests.Session()
    paths = _post_paths(sess, volume)

    def one(path: str) -> dict | None:
        return parse_post(_get(sess, f"{RAW_BASE}/v{volume}/{BRANCH}/_posts/{path}").text, label, year)

    with ThreadPoolExecutor(max_workers=workers) as pool:
        records = [r for r in pool.map(one, paths) if r]
    seen: set[str] = set()
    return [r for r in records if not (r["title"] in seen or seen.add(r["title"]))]


def fetch_to_csv(volume: str, label: str, year: int, out_path: Path | str, **kwargs) -> int:
    """Fetch a PMLR volume and write a source CSV; returns the row count."""
    import pandas as pd

    records = fetch_pmlr(volume, label, year, **kwargs)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records, columns=RECORD_COLUMNS).to_csv(out_path, index=False)
    return len(records)
