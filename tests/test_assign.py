"""Tests for deterministic substring topic assignment.

These pin the exact behaviour ported from the notebook's ``obtain_topic_for_text``
/ ``assign_topics`` so the migration stays faithful.
"""

from __future__ import annotations

import pandas as pd

from ai_trend.assign import (
    assign_dataframe,
    build_search_text,
    match_topics,
    topics_for_paper,
)
from ai_trend.taxonomy import Taxonomy

TAXONOMY = Taxonomy(
    topic2keywords={
        "graph": ["graph", "gnn"],
        "llm": ["large language model", "llm"],
        "transformer": ["transformer", "attention"],
    },
    useless_kw=set(),
)


def test_match_topics_multi_label_in_taxonomy_order():
    # Arrange
    text = "a graph transformer for large language model reasoning"
    # Act
    matched = match_topics(text, TAXONOMY.topic2keywords)
    # Assert — order follows taxonomy insertion order, not text order
    assert matched == ["graph", "llm", "transformer"]


def test_match_topics_none_when_no_keyword_present():
    assert match_topics("a study of widgets", TAXONOMY.topic2keywords) == []


def test_match_topics_is_case_sensitive_substring():
    # Uppercase text won't match lowercase keyword (notebook quirk reproduced)
    assert match_topics("GRAPH NEURAL NETWORKS", TAXONOMY.topic2keywords) == []


def test_build_search_text_handles_missing_abstract():
    # A non-string abstract becomes the literal "None", lowercased title
    assert build_search_text("Graph GNNs", None) == "graph gnns None"


def test_build_search_text_lowercases_both_parts():
    assert build_search_text("Graph", "Transformer") == "graph transformer"


def test_topics_for_paper_uses_title_and_abstract():
    title = "An efficient model"
    abstract = "We use a Transformer with attention."
    # 'transformer'/'attention' live in the lowercased abstract
    assert topics_for_paper(title, abstract, TAXONOMY) == "transformer"


def test_topics_for_paper_joins_with_semicolon():
    result = topics_for_paper("graph gnn study", "uses llm", TAXONOMY)
    assert result == "graph;llm"


def test_assign_dataframe_appends_topic_column():
    # Arrange
    df = pd.DataFrame(
        {
            "title": ["A graph paper", "A vision study"],
            "abstract": ["uses gnn", "no signal here"],
        }
    )
    # Act
    result = assign_dataframe(df, TAXONOMY)
    # Assert
    assert list(result["topic"]) == ["graph", ""]
    # original is not mutated
    assert "topic" not in df.columns


def test_assign_dataframe_missing_column_raises():
    df = pd.DataFrame({"title": ["x"]})  # no abstract
    try:
        assign_dataframe(df, TAXONOMY)
    except ValueError as exc:
        assert "abstract" in str(exc)
    else:  # pragma: no cover
        raise AssertionError("expected ValueError for missing column")
