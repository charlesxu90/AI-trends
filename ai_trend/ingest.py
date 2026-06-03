"""Merge crawled OpenReview JSON into per-conference-year CSVs.

Ported from the original crawl-processing notebook. The spider writes one JSON file per
venue/type (e.g. ``2025/iclr2025-oral.json``), each already in the final record
schema. This step concatenates a conference-year's JSON files into a single
``data/<year>/<month>_<key>.csv``, prefixes OpenReview PDF links, and de-dupes by
title (the original notebook warned the first crawl file often repeats records).

Faithful change: the notebook used ``DataFrame.append`` (removed in pandas 2.x);
this uses ``pd.concat``.

NOTE: only OpenReview venues (ICLR / ICML / NeurIPS) flow through here. CVPR / ICCV
come from a different source (CVF) and are not handled by this module.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd

    from ai_trend.registry import Conference, ConferenceRegistry

OPENREVIEW_BASE = "https://api2.openreview.net"
RECORD_COLUMNS = ["title", "year", "source", "authors", "class", "keywords", "abstract", "pdf_link"]


def _read_records(path: Path | str) -> list[dict]:
    """Read records from a crawl JSON file, tolerating concatenated arrays.

    Some crawl outputs contain more than one JSON array back-to-back ("Trailing
    data"). We decode every top-level value and flatten, so a malformed-but-
    recoverable file still yields its records instead of aborting the run.
    """
    text = Path(path).read_text(encoding="utf-8")
    decoder = json.JSONDecoder()
    records: list[dict] = []
    idx, n = 0, len(text)
    while idx < n:
        while idx < n and text[idx].isspace():
            idx += 1
        if idx >= n:
            break
        obj, idx = decoder.raw_decode(text, idx)
        if isinstance(obj, list):
            records.extend(x for x in obj if isinstance(x, dict))
        elif isinstance(obj, dict):
            records.append(obj)
    return records


def _prefix_pdf(value: object) -> str:
    if not isinstance(value, str) or not value:
        return ""
    if value.startswith("http"):
        return value
    return OPENREVIEW_BASE + value


def merge_conference_year(raw_dir: Path | str, token: str, year: int) -> "pd.DataFrame | None":
    """Merge ``<raw_dir>/<year>/<token>*.json`` into one de-duped DataFrame.

    Returns ``None`` if no JSON files are found for that conference-year.
    """
    import pandas as pd

    pattern = str(Path(raw_dir) / str(year) / f"{token}*.json")
    files = sorted(glob.glob(pattern))
    if not files:
        return None

    records: list[dict] = []
    for f in files:
        try:
            records.extend(_read_records(f))
        except (ValueError, OSError):
            # best-effort: skip an unreadable file rather than abort the run
            continue
    if not records:
        return None

    df = pd.DataFrame(records)
    if "pdf_link" in df.columns:
        df["pdf_link"] = df["pdf_link"].apply(_prefix_pdf)
    if "title" in df.columns:
        df = df.drop_duplicates(subset="title", keep="first").reset_index(drop=True)
    return df


def process(
    raw_dir: Path | str,
    out_dir: Path | str,
    registry: "ConferenceRegistry",
) -> list[Path]:
    """Merge every conference-year found under ``raw_dir`` into ``out_dir``.

    Writes ``<out_dir>/<year>/<month>_<key>.csv`` and returns the written paths.
    """
    raw_dir = Path(raw_dir)
    out_dir = Path(out_dir)
    written: list[Path] = []

    for year_dir in sorted(p for p in raw_dir.iterdir() if p.is_dir() and p.name.isdigit()):
        year = int(year_dir.name)
        for conference in registry.conferences:
            df = _merge_for_conference(raw_dir, conference, year)
            if df is None or df.empty:
                continue
            dest_dir = out_dir / str(year)
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest = dest_dir / f"{conference.month}_{conference.key}.csv"
            df.to_csv(dest, index=False)
            written.append(dest)
    return written


def _merge_for_conference(
    raw_dir: Path, conference: "Conference", year: int
) -> "pd.DataFrame | None":
    import pandas as pd

    frames = []
    for token in conference.tokens:
        df = merge_conference_year(raw_dir, token, year)
        if df is not None:
            frames.append(df)
    if not frames:
        return None
    merged = pd.concat(frames, ignore_index=True)
    if "title" in merged.columns:
        merged = merged.drop_duplicates(subset="title", keep="first").reset_index(drop=True)
    return merged
