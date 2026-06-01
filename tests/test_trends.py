"""Tests for trend computation (top / emerging / fading)."""

from __future__ import annotations

import math

import pandas as pd

from ai_trend.taxonomy import Taxonomy
from ai_trend.trends import (
    compute_trends,
    count_file,
    discover_conference_years,
    parse_conference,
    topic_counts,
    trend_to_dict,
)

TAXONOMY = Taxonomy(
    topic2keywords={
        "graph": ["graph"],
        "llm": ["llm"],
        "vae": ["vae"],
        "rl": ["rl"],
    },
    useless_kw=set(),
)


# ---- parse_conference -------------------------------------------------------
def test_parse_conference_standard():
    assert parse_conference("5_iclr.csv_topics.csv") == "ICLR"
    assert parse_conference("12_nips.csv_topics.csv") == "NIPS"


def test_parse_conference_uppercase_token():
    assert parse_conference("10_ICCV.csv_topics.csv") == "ICCV"


def test_parse_conference_unknown_returns_none():
    assert parse_conference("9_neurips_workshop.csv_topics.csv") is None


# ---- topic_counts -----------------------------------------------------------
def test_topic_counts_multi_label_and_zero_init():
    topics = ["graph;llm", "graph", ""]
    counts = topic_counts(topics, TAXONOMY)
    assert counts["graph"] == 2
    assert counts["llm"] == 1
    assert counts["vae"] == 0  # present though never seen
    assert counts["rl"] == 0


def test_topic_counts_breaks_on_nan():
    counts = topic_counts(["nan", float("nan")], TAXONOMY)
    assert all(v == 0 for v in counts.values())


# ---- compute_trends ---------------------------------------------------------
def test_top_sorted_by_count():
    current = {"graph": 10, "llm": 8, "vae": 1, "rl": 0}
    trend = compute_trends("ICLR", 2025, current, None, top_n=2)
    assert trend.top == ["graph", "llm"]
    # no previous -> no emerging/fading
    assert trend.emerging == []
    assert trend.fading == []
    assert trend.previous_year is None


def test_emerging_and_fading_by_change_ratio():
    previous = {"graph": 10, "llm": 5, "vae": 10, "rl": 4}
    current = {"graph": 20, "llm": 10, "vae": 5, "rl": 2}  # graph/llm +100%, vae/rl -50%
    trend = compute_trends("ICLR", 2025, current, previous, previous_year=2024, top_n=2)
    assert trend.emerging[:2] == ["graph", "llm"]  # +1.0 each, taxonomy-order tiebreak
    assert set(trend.fading[:2]) == {"vae", "rl"}  # -0.5 each
    assert trend.previous_year == 2024


def test_first_appearance_topic_excluded_by_default():
    # min_prev defaults to 1: a topic absent the prior year (prev 0) is not eligible,
    # filtering back-labeling / coincidental first appearances.
    previous = {"graph": 10, "llm": 0, "vae": 5, "rl": 0}
    current = {"graph": 10, "llm": 7, "vae": 5, "rl": 0}  # llm 0->7, rl 0->0
    trend = compute_trends("ICLR", 2025, current, previous, previous_year=2024, top_n=3)
    assert "llm" not in trend.emerging  # prev 0 -> excluded
    assert "rl" not in trend.emerging
    assert "rl" not in trend.fading


def test_min_prev_zero_restores_first_appearance_emerging():
    previous = {"graph": 10, "llm": 0, "vae": 5, "rl": 0}
    current = {"graph": 10, "llm": 7, "vae": 5, "rl": 0}
    trend = compute_trends(
        "ICLR", 2025, current, previous, previous_year=2024,
        top_n=3, min_prev=0, min_count=0,
    )
    assert trend.emerging[0] == "llm"  # inf ratio leads when min_prev=0


def test_min_count_filters_low_volume_emerging():
    # llm has the highest ratio but tiny current volume; min_count drops it
    previous = {"graph": 50, "llm": 1, "vae": 40, "rl": 30}
    current = {"graph": 80, "llm": 6, "vae": 44, "rl": 33}
    trend = compute_trends(
        "ICLR", 2025, current, previous, previous_year=2024, top_n=2, min_count=10
    )
    assert "llm" not in trend.emerging  # cur 6 < 10
    assert trend.emerging[0] == "graph"


def test_min_count_does_not_apply_to_fading():
    # a topic that collapses to near-zero must still be eligible for fading
    previous = {"graph": 50, "llm": 40, "vae": 3, "rl": 30}
    current = {"graph": 55, "llm": 0, "vae": 1, "rl": 33}
    trend = compute_trends(
        "ICLR", 2025, current, previous, previous_year=2024, top_n=1, min_count=10
    )
    assert trend.fading[0] == "llm"  # 40 -> 0 despite cur < min_count


def test_min_prev_threshold_filters_small_baselines():
    previous = {"graph": 10, "llm": 2, "vae": 5, "rl": 1}
    current = {"graph": 11, "llm": 20, "vae": 6, "rl": 9}
    # llm/rl have tiny baselines; min_prev=5 drops them from eligibility
    trend = compute_trends(
        "ICLR", 2025, current, previous, previous_year=2024, top_n=4, min_prev=5
    )
    assert set(trend.emerging) <= {"graph", "vae"}
    assert "llm" not in trend.emerging and "rl" not in trend.emerging


def test_change_ratio_zero_to_zero_excluded():
    previous = {"graph": 0, "llm": 5, "vae": 0, "rl": 0}
    current = {"graph": 0, "llm": 3, "vae": 0, "rl": 0}
    trend = compute_trends(
        "ICLR", 2025, current, previous, previous_year=2024, top_n=4, min_count=0
    )
    # only llm had a prior baseline, so only it is eligible
    assert trend.emerging == ["llm"]
    assert trend.fading == ["llm"]


# ---- file + discovery -------------------------------------------------------
def test_count_file_reads_topic_column(tmp_path):
    csv = tmp_path / "t.csv"
    pd.DataFrame({"topic": ["graph;llm", "graph"]}).to_csv(csv, index=False)
    counts = count_file(csv, TAXONOMY)
    assert counts["graph"] == 2 and counts["llm"] == 1


def test_discover_conference_years(tmp_path):
    (tmp_path / "2024").mkdir()
    (tmp_path / "2025").mkdir()
    (tmp_path / "notayear").mkdir()
    for rel in ("2024/5_iclr.csv_topics.csv", "2025/5_iclr.csv_topics.csv"):
        pd.DataFrame({"topic": ["graph"]}).to_csv(tmp_path / rel, index=False)
    index = discover_conference_years(tmp_path)
    assert set(index["ICLR"]) == {2024, 2025}


def test_trend_to_dict_includes_counts_when_requested():
    trend = compute_trends("ICLR", 2025, {"graph": 3, "llm": 0}, None)
    d = trend_to_dict(trend, include_counts=True)
    assert d["conference"] == "ICLR"
    assert d["counts"] == {"graph": 3}  # zero-count dropped


# ---- faithfulness to README -------------------------------------------------
def test_reproduces_readme_2025_iclr():
    """End-to-end against the real data and the committed README numbers."""
    from pathlib import Path

    from ai_trend.trends import DEFAULT_DATA_DIR

    cur = Path(DEFAULT_DATA_DIR) / "2025" / "5_iclr.csv_topics.csv"
    prev = Path(DEFAULT_DATA_DIR) / "2024" / "5_iclr.csv_topics.csv"
    if not cur.exists() or not prev.exists():
        import pytest

        pytest.skip("real data not present")

    tax = Taxonomy.load()
    trend = compute_trends(
        "ICLR",
        2025,
        count_file(cur, tax),
        count_file(prev, tax),
        previous_year=2024,
    )
    assert trend.top == ["graph", "zero_few-shot", "llm", "generative model", "transformer"]
    assert trend.emerging == [
        "splatting",
        "diffusion transformer",
        "state space model",
        "Flow matching",
        "RAG",
    ]
    assert trend.fading == [
        "Deep Equilibrium Models",
        "domain adaptation",
        "Spiking Neural Networks",
        "optical flow",
        "neural collapse",
    ]
