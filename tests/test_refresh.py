"""Tests for the refresh orchestrator (deterministic core, no crawl/curate)."""

from __future__ import annotations

import json

import pandas as pd

from ai_trend.refresh import _source_csvs, refresh


def _setup(tmp_path):
    config = tmp_path / "config"
    config.mkdir()
    (config / "taxonomy.json").write_text(
        json.dumps({"graph": ["graph"], "llm": ["llm"], "transformer": ["transformer"]}),
        encoding="utf-8",
    )
    (config / "useless_keywords.json").write_text("[]", encoding="utf-8")
    (config / "conferences.json").write_text(
        json.dumps({"conferences": [
            {"key": "iclr", "label": "ICLR", "tokens": ["iclr"], "month": 5}]}),
        encoding="utf-8",
    )
    data = tmp_path / "data"
    cols = ["title", "year", "source", "authors", "class", "keywords", "abstract", "pdf_link"]
    (data / "2024").mkdir(parents=True)
    (data / "2025").mkdir(parents=True)
    pd.DataFrame([["graph paper", 2024, "ICLR", "'A'", "poster", "", "graph", "x"]], columns=cols).to_csv(
        data / "2024" / "5_iclr.csv", index=False)
    pd.DataFrame([["graph transformer", 2025, "ICLR", "'B'", "poster", "", "graph transformer", "y"]], columns=cols).to_csv(
        data / "2025" / "5_iclr.csv", index=False)
    return config, data


def test_source_csvs_excludes_derived(tmp_path):
    d = tmp_path / "data" / "2025"
    d.mkdir(parents=True)
    (d / "5_iclr.csv").write_text("title\n", encoding="utf-8")
    (d / "5_iclr.csv_topics.csv").write_text("title,topic\n", encoding="utf-8")
    (d / "5_iclr.csv_topics.csv_emerging.xlsx").write_text("", encoding="utf-8")
    sources = _source_csvs(tmp_path / "data")
    assert [p.name for p in sources] == ["5_iclr.csv"]


def test_refresh_deterministic_core(tmp_path):
    config, data = _setup(tmp_path)
    site = tmp_path / "site"

    summary = refresh(
        config_dir=config,
        data_dir=data,
        raw_dir=tmp_path / "no_raw",   # missing -> process skipped
        site_dir=site,
        do_crawl=False,
        do_curate=False,
        log=lambda *_: None,
    )

    assert summary["assigned"] == 2
    assert summary["trends"] == 2
    assert summary["site_shards"] == 2
    # assign produced topic files
    topics = pd.read_csv(data / "2025" / "5_iclr.csv_topics.csv")
    assert topics["topic"].iloc[0] == "graph;transformer"
    # trends + site written
    assert (data / "trends" / "trends.json").exists()
    assert (site / "manifest.json").exists()


def test_refresh_curate_skipped_without_client(tmp_path):
    config, data = _setup(tmp_path)
    # do_curate True but client None -> curation silently skipped, core still runs
    summary = refresh(
        config_dir=config, data_dir=data, raw_dir=tmp_path / "no_raw",
        site_dir=tmp_path / "s", do_curate=True, client=None, log=lambda *_: None,
    )
    assert summary["curated"] == 0 and summary["assigned"] == 2
