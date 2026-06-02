"""Fetch accepted-paper metadata from OpenReview by venue id.

URL-driven alternative to the static ``config/crawl.json`` recipes: given a venue
id (e.g. ``ICLR.cc/2025/Conference``, derived from a pasted OpenReview URL), this
paginates the api2 ``/notes?content.venueid=...`` endpoint and reads each note's
content directly — no hand-maintained per-type venue/offset strings. The paper
``class`` (oral/spotlight/poster) is derived from the note's ``venue`` value.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ai_trend.ingest import RECORD_COLUMNS

if TYPE_CHECKING:  # pragma: no cover - typing only
    import requests

API2_BASE = "https://api2.openreview.net"
PAGE_LIMIT = 1000
_TYPES = ("oral", "spotlight", "poster")


def _value(content: dict, key: str, default=""):
    node = content.get(key)
    return node.get("value", default) if isinstance(node, dict) else default


def _classify(venue: str) -> str:
    """Map a venue string like 'ICLR 2025 Poster' to oral/spotlight/poster."""
    low = venue.lower()
    for t in _TYPES:
        if t in low:
            return t
    return ""


def _format_authors(authors) -> str:
    if isinstance(authors, list):
        return ", ".join(f"'{a}'" for a in authors if a)
    return str(authors or "")


def note_to_record(note: dict, label: str, year: int, *, base: str = API2_BASE) -> dict | None:
    content = note.get("content") or {}
    title = _value(content, "title").strip()
    if not title:
        return None
    pdf = _value(content, "pdf")
    if pdf.startswith("/"):
        pdf = base + pdf
    keywords = _value(content, "keywords", [])
    return {
        "title": title,
        "year": year,
        "source": label,
        "authors": _format_authors(_value(content, "authors", [])),
        "class": _classify(_value(content, "venue")),
        "keywords": ", ".join(keywords) if isinstance(keywords, list) else str(keywords),
        "abstract": _value(content, "abstract"),
        "pdf_link": pdf,
    }


def fetch_openreview(
    venueid: str,
    label: str,
    year: int,
    *,
    base: str = API2_BASE,
    limit: int = PAGE_LIMIT,
    session: "requests.Session | None" = None,
) -> list[dict]:
    """Paginate all accepted papers for a venue id into records (RECORD_COLUMNS)."""
    import requests

    sess = session or requests.Session()
    records: list[dict] = []
    seen: set[str] = set()
    offset = 0
    while True:
        url = f"{base}/notes?content.venueid={venueid}&details=replyCount&limit={limit}&offset={offset}"
        resp = sess.get(url, headers={"User-Agent": "ai-trend/0.1"}, timeout=120)
        resp.raise_for_status()
        notes = resp.json().get("notes", [])
        if not notes:
            break
        for note in notes:
            rec = note_to_record(note, label, year, base=base)
            if rec and rec["title"] not in seen:
                seen.add(rec["title"])
                records.append(rec)
        if len(notes) < limit:
            break
        offset += limit
    return records


def fetch_to_csv(venueid: str, label: str, year: int, out_path: Path | str, **kwargs) -> int:
    import pandas as pd

    records = fetch_openreview(venueid, label, year, **kwargs)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records, columns=RECORD_COLUMNS).to_csv(out_path, index=False)
    return len(records)
