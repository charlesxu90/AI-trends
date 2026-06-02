"""Tests for the static-site data export."""

from __future__ import annotations

import json

import pandas as pd

from ai_trend.registry import ConferenceRegistry
from ai_trend.site import build_paper_record, export_site, parse_authors
from ai_trend.taxonomy import Taxonomy


def test_parse_authors_list_string():
    assert parse_authors("'A Smith', 'B Lee'") == ["A Smith", "B Lee"]


def test_parse_authors_handles_empty_and_nan():
    assert parse_authors("") == []
    assert parse_authors(float("nan")) == []


def test_build_paper_record_splits_topics_and_truncates_abstract():
    row = {
        "title": "A Graph Paper",
        "authors": "'A'",
        "topic": "graph;llm",
        "abstract": "x" * 500,
        "pdf_link": "http://example.com/p.pdf",
    }
    rec = build_paper_record(row, "ICLR", 2025, abstract_chars=100)
    assert rec["topics"] == ["graph", "llm"]
    assert rec["conference"] == "ICLR" and rec["year"] == 2025
    assert rec["abstract"].endswith("…") and len(rec["abstract"]) <= 101
    assert rec["pdf"] == "http://example.com/p.pdf"


def test_build_paper_record_drops_empty_topic():
    rec = build_paper_record({"title": "t", "topic": "", "abstract": ""}, "ICML", 2024)
    assert rec["topics"] == []


def test_build_paper_record_includes_citations_when_available():
    row = {"title": "A", "topic": "graph", "abstract": "", "authors": "'X'", "pdf_link": ""}
    rec = build_paper_record(row, "ICLR", 2025, citations={"A": 55})
    assert rec["citations"] == 55


def test_build_paper_record_omits_citations_when_missing():
    rec = build_paper_record({"title": "B", "topic": "graph", "abstract": ""}, "ICLR", 2025, citations={"A": 55})
    assert "citations" not in rec


def test_build_paper_record_includes_delta_when_available():
    rec = build_paper_record({"title": "A", "topic": "graph", "abstract": ""}, "ICLR", 2025, deltas={"A": 12})
    assert rec["delta"] == 12


def _setup(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "taxonomy.json").write_text(
        json.dumps({"graph": ["graph"], "llm": ["llm"]}), encoding="utf-8"
    )
    (config / "useless_keywords.json").write_text("[]", encoding="utf-8")
    data = tmp_path / "data"
    (data / "2024").mkdir(parents=True)
    (data / "2025").mkdir(parents=True)
    cols = {"title": [], "authors": [], "topic": [], "abstract": [], "pdf_link": []}
    pd.DataFrame(
        {"title": ["P1"], "authors": ["'A'"], "topic": ["graph"], "abstract": ["a"], "pdf_link": ["x"]}
    ).to_csv(data / "2024" / "5_iclr.csv_topics.csv", index=False)
    pd.DataFrame(
        {"title": ["P2", "P3"], "authors": ["'B'", "'C'"], "topic": ["graph;llm", "llm"],
         "abstract": ["b", "c"], "pdf_link": ["y", "z"]}
    ).to_csv(data / "2025" / "5_iclr.csv_topics.csv", index=False)
    return config, data


def test_export_site_writes_manifest_trends_and_shards(tmp_path):
    config, data = _setup(tmp_path)
    out = tmp_path / "site"
    taxonomy = Taxonomy.load(config)

    manifest = export_site(out, taxonomy=taxonomy, data_dir=data)

    # manifest
    assert {c["label"] for c in manifest["conferences"]} >= {"ICLR"}
    assert sorted(manifest["topics"]) == ["graph", "llm"]
    assert manifest["years"] == [2024, 2025]
    assert len(manifest["shards"]) == 2

    # files exist
    assert (out / "trends.json").exists()
    assert (out / "manifest.json").exists()
    shard = json.loads((out / "papers" / "ICLR_2025.json").read_text())
    assert len(shard) == 2
    assert shard[0]["conference"] == "ICLR" and shard[0]["year"] == 2025
