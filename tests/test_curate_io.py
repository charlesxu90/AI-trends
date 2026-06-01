"""Tests for the curation payload builder and decision parser/merger."""

from __future__ import annotations

import pytest

from ai_trend.candidates import Candidate
from ai_trend.curate_io import (
    DecisionError,
    apply_decision,
    build_curation_payload,
    parse_decision,
)
from ai_trend.taxonomy import Taxonomy


def _taxonomy():
    return Taxonomy(
        topic2keywords={"graph": ["graph"], "llm": ["large language model"]},
        useless_kw={"model"},
    )


# ---- payload builder --------------------------------------------------------
def test_build_payload_includes_topics_and_candidates():
    candidates = [Candidate("splatting", 12, ["a splatting paper"])]
    payload = build_curation_payload(
        candidates, _taxonomy(), conference="iclr", year=2025
    )
    assert payload["existing_topics"] == ["graph", "llm"]
    assert payload["conference"] == "iclr"
    assert payload["year"] == "2025"
    assert payload["candidates"][0]["keyword"] == "splatting"
    assert payload["candidates"][0]["count"] == 12


# ---- decision parsing -------------------------------------------------------
def test_parse_decision_valid():
    raw = {
        "decisions": [
            {"keyword": "splatting", "action": "new", "topic": "splatting"},
            {"keyword": "gnn", "action": "existing", "topic": "graph"},
            {"keyword": "approach", "action": "noise"},
            {"keyword": "mesh", "action": "other"},
        ]
    }
    decisions = parse_decision(raw)
    assert [d.action for d in decisions] == ["new", "existing", "noise", "other"]


def test_parse_decision_rejects_missing_decisions_key():
    with pytest.raises(DecisionError):
        parse_decision({"oops": []})


def test_parse_decision_rejects_unknown_action():
    raw = {"decisions": [{"keyword": "x", "action": "frobnicate"}]}
    with pytest.raises(DecisionError):
        parse_decision(raw)


def test_parse_decision_requires_topic_for_existing():
    raw = {"decisions": [{"keyword": "x", "action": "existing"}]}
    with pytest.raises(DecisionError):
        parse_decision(raw)


def test_parse_decision_rejects_duplicate_keyword():
    raw = {
        "decisions": [
            {"keyword": "x", "action": "noise"},
            {"keyword": "x", "action": "other"},
        ]
    }
    with pytest.raises(DecisionError):
        parse_decision(raw)


def test_parse_decision_rejects_blank_keyword():
    raw = {"decisions": [{"keyword": "  ", "action": "noise"}]}
    with pytest.raises(DecisionError):
        parse_decision(raw)


# ---- decision application ---------------------------------------------------
def test_apply_decision_maps_existing_and_creates_new():
    decisions = parse_decision(
        {
            "decisions": [
                {"keyword": "gnn", "action": "existing", "topic": "graph"},
                {"keyword": "splatting", "action": "new", "topic": "splatting"},
            ]
        }
    )
    result = apply_decision(_taxonomy(), decisions)
    assert "gnn" in result.taxonomy.topic2keywords["graph"]
    assert result.taxonomy.topic2keywords["splatting"] == ["splatting"]


def test_apply_decision_existing_unknown_topic_raises():
    decisions = [type("D", (), {"keyword": "x", "action": "existing", "topic": "nope"})()]
    with pytest.raises(DecisionError):
        apply_decision(_taxonomy(), decisions)


def test_apply_decision_noise_and_other():
    decisions = parse_decision(
        {
            "decisions": [
                {"keyword": "approach", "action": "noise"},
                {"keyword": "mesh", "action": "other"},
            ]
        }
    )
    result = apply_decision(_taxonomy(), decisions)
    assert "approach" in result.taxonomy.useless_kw
    assert result.other_keywords == ["mesh"]
    # 'other' is not added to the taxonomy or blocklist
    assert "mesh" not in result.taxonomy.useless_kw


def test_apply_decision_does_not_mutate_input():
    original = _taxonomy()
    decisions = parse_decision(
        {"decisions": [{"keyword": "gnn", "action": "existing", "topic": "graph"}]}
    )
    apply_decision(original, decisions)
    assert original.topic2keywords["graph"] == ["graph"]


def test_apply_decision_summary_counts():
    decisions = parse_decision(
        {
            "decisions": [
                {"keyword": "a", "action": "noise"},
                {"keyword": "b", "action": "noise"},
                {"keyword": "c", "action": "other"},
            ]
        }
    )
    result = apply_decision(_taxonomy(), decisions)
    assert result.summary["noise"] == 2
    assert result.summary["other"] == 1
