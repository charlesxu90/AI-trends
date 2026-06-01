"""Tests for crawl-JSON ingestion (merge to per-conference CSV)."""

from __future__ import annotations

import json

import pandas as pd

from ai_trend.ingest import (
    _prefix_pdf,
    _read_records,
    merge_conference_year,
    process,
)
from ai_trend.registry import ConferenceRegistry

REG = ConferenceRegistry.from_dicts(
    [{"key": "iclr", "label": "ICLR", "tokens": ["iclr"], "month": 5}]
)


def _rec(title, pdf="/pdf/x"):
    return {"title": title, "year": 2025, "source": "ICLR", "authors": "'A'",
            "class": "poster", "keywords": "", "abstract": "a", "pdf_link": pdf}


def test_prefix_pdf():
    assert _prefix_pdf("/pdf/x").startswith("https://api2.openreview.net/pdf/")
    assert _prefix_pdf("") == ""
    assert _prefix_pdf("http://already") == "http://already"


def test_read_records_handles_trailing_data(tmp_path):
    f = tmp_path / "x.json"
    # two concatenated arrays -> "Trailing data" for a naive parser
    f.write_text(json.dumps([_rec("A")]) + "\n" + json.dumps([_rec("B")]), encoding="utf-8")
    recs = _read_records(f)
    assert [r["title"] for r in recs] == ["A", "B"]


def test_merge_conference_year_dedupes_by_title(tmp_path):
    (tmp_path / "2025").mkdir()
    (tmp_path / "2025" / "iclr2025-oral.json").write_text(
        json.dumps([_rec("Dup"), _rec("Unique")]), encoding="utf-8"
    )
    (tmp_path / "2025" / "iclr2025-poster.json").write_text(
        json.dumps([_rec("Dup")]), encoding="utf-8"  # repeated title
    )
    df = merge_conference_year(tmp_path, "iclr", 2025)
    assert sorted(df["title"]) == ["Dup", "Unique"]  # deduped
    assert df["pdf_link"].iloc[0].startswith("https://api2.openreview.net")


def test_merge_conference_year_missing_returns_none(tmp_path):
    assert merge_conference_year(tmp_path, "iclr", 2099) is None


def test_process_writes_month_prefixed_csv(tmp_path):
    raw = tmp_path / "raw"
    (raw / "2025").mkdir(parents=True)
    (raw / "2025" / "iclr2025-oral.json").write_text(json.dumps([_rec("P1"), _rec("P2")]), encoding="utf-8")
    out = tmp_path / "data"
    written = process(raw, out, REG)
    assert written == [out / "2025" / "5_iclr.csv"]
    df = pd.read_csv(written[0])
    assert len(df) == 2 and list(df.columns)[0] == "title"
