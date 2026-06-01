"""Tests for the Taxonomy loader, validation, and immutable mutation."""

from __future__ import annotations

import json

import pytest

from ai_trend.taxonomy import DEFAULT_CONFIG_DIR, Taxonomy, TaxonomyError


def _write_config(tmp_path, topic2keywords, blocklist):
    (tmp_path / "taxonomy.json").write_text(json.dumps(topic2keywords), encoding="utf-8")
    (tmp_path / "useless_keywords.json").write_text(json.dumps(blocklist), encoding="utf-8")


def test_load_roundtrip(tmp_path):
    # Arrange
    topic2keywords = {"graph": ["graph", "gnn"], "llm": ["large language model"]}
    blocklist = ["model", "learning"]
    _write_config(tmp_path, topic2keywords, blocklist)

    # Act
    taxonomy = Taxonomy.load(tmp_path)

    # Assert
    assert taxonomy.topic2keywords == topic2keywords
    assert taxonomy.useless_kw == {"model", "learning"}


def test_load_preserves_topic_order(tmp_path):
    # Arrange — order matters for the ;-joined topic column
    topic2keywords = {"zebra": ["z"], "alpha": ["a"], "middle": ["m"]}
    _write_config(tmp_path, topic2keywords, [])

    # Act
    taxonomy = Taxonomy.load(tmp_path)

    # Assert
    assert taxonomy.topics == ["zebra", "alpha", "middle"]


def test_load_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Taxonomy.load(tmp_path)


def test_validate_rejects_empty_keyword_list():
    taxonomy = Taxonomy(topic2keywords={"graph": []}, useless_kw=set())
    with pytest.raises(TaxonomyError):
        taxonomy.validate()


def test_validate_rejects_blank_topic_name():
    taxonomy = Taxonomy(topic2keywords={"  ": ["x"]}, useless_kw=set())
    with pytest.raises(TaxonomyError):
        taxonomy.validate()


def test_known_keywords_unions_across_topics():
    taxonomy = Taxonomy(
        topic2keywords={"graph": ["graph", "gnn"], "rep": ["graph", "embedding"]},
        useless_kw=set(),
    )
    assert taxonomy.known_keywords() == {"graph", "gnn", "embedding"}


def test_add_keywords_is_immutable_and_dedupes():
    original = Taxonomy(topic2keywords={"graph": ["graph"]}, useless_kw=set())

    updated = original.add_keywords("graph", ["graph", "gnn"])

    # original untouched
    assert original.topic2keywords == {"graph": ["graph"]}
    # new copy deduped, order preserved
    assert updated.topic2keywords == {"graph": ["graph", "gnn"]}


def test_add_keywords_creates_new_topic():
    original = Taxonomy(topic2keywords={"graph": ["graph"]}, useless_kw=set())
    updated = original.add_keywords("rag", ["retrieval-augmented"])
    assert updated.topic2keywords["rag"] == ["retrieval-augmented"]
    assert "rag" not in original.topic2keywords


def test_add_noise_is_immutable():
    original = Taxonomy(topic2keywords={"graph": ["graph"]}, useless_kw={"model"})
    updated = original.add_noise(["network", "model"])
    assert original.useless_kw == {"model"}
    assert updated.useless_kw == {"model", "network"}


def test_real_config_loads_and_validates():
    """The migrated config must be structurally valid."""
    taxonomy = Taxonomy.load(DEFAULT_CONFIG_DIR)
    taxonomy.validate()
    assert "graph" in taxonomy.topic2keywords
    assert "llm" in taxonomy.topic2keywords
    assert len(taxonomy.topic2keywords) > 100
