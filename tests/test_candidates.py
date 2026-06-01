"""Tests for candidate-keyword extraction.

The spaCy NER is exercised via a fake ``nlp`` (no model download / load in unit
tests). One opt-in integration test loads the real model when available.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from ai_trend.candidates import (
    DEFAULT_MODEL_PATH,
    candidate_keywords,
    count_occurrences,
    load_model,
)
from ai_trend.taxonomy import Taxonomy


class _FakeEnt:
    def __init__(self, text):
        self.text = text


class _FakeDoc:
    def __init__(self, ents):
        self.ents = ents


class _FakeNLP:
    """Returns a fixed entity set regardless of input, mimicking NER output."""

    def __init__(self, entities):
        self._entities = entities
        self.max_length = 1_000_000

    def __call__(self, _text):
        return _FakeDoc([_FakeEnt(e) for e in self._entities])


def test_count_occurrences_counts_substring_hits():
    titles = ["graph networks", "a graph study", "vision only"]
    assert count_occurrences(titles, "graph") == 2


def test_candidate_keywords_filters_known_and_noise_and_threshold():
    # Arrange
    titles = [
        "splatting for 3d",
        "splatting renderer",
        "splatting fast",
        "graph paper",  # 'graph' is known -> excluded
        "model soup",  # 'model' is noise -> excluded
    ]
    taxonomy = Taxonomy(topic2keywords={"graph": ["graph"]}, useless_kw={"model"})
    nlp = _FakeNLP(["splatting", "graph", "model"])

    # Act — threshold 2 keeps only keywords occurring > 2 times
    result = candidate_keywords(titles, taxonomy, threshold=2, nlp=nlp)

    # Assert
    assert [c.keyword for c in result] == ["splatting"]
    assert result[0].count == 3


def test_candidate_keywords_sorted_by_count_desc():
    titles = ["aaa bbb", "aaa", "bbb", "bbb"]  # aaa:2, bbb:3
    taxonomy = Taxonomy(topic2keywords={"x": ["zzz"]}, useless_kw=set())
    nlp = _FakeNLP(["aaa", "bbb"])

    result = candidate_keywords(titles, taxonomy, threshold=1, nlp=nlp)

    assert [c.keyword for c in result] == ["bbb", "aaa"]


def test_candidate_keywords_includes_example_titles():
    titles = ["splatting one", "splatting two", "splatting three", "unrelated"]
    taxonomy = Taxonomy(topic2keywords={"x": ["zzz"]}, useless_kw=set())
    nlp = _FakeNLP(["splatting"])

    result = candidate_keywords(titles, taxonomy, threshold=1, examples=2, nlp=nlp)

    assert result[0].examples == ["splatting one", "splatting two"]


def test_load_model_missing_path_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_model(tmp_path / "does-not-exist")


@pytest.mark.skipif(
    not DEFAULT_MODEL_PATH.exists(), reason="scispaCy model not present"
)
def test_real_model_extracts_entities():
    nlp = load_model()
    taxonomy = Taxonomy(topic2keywords={"placeholder": ["zzzzz"]}, useless_kw=set())
    titles = ["diffusion models for image generation"] * 6
    result = candidate_keywords(titles, taxonomy, threshold=5, nlp=nlp)
    # at least one real entity should survive filtering at this volume
    assert any(c.count >= 6 for c in result)
