"""Tests for citation fetching (fake session, no network)."""

from __future__ import annotations

import pandas as pd

from ai_trend.citations import (
    fetch_citations,
    load_cache,
    search_citation,
    titles_for_topics,
)


class _Resp:
    def __init__(self, status, payload=None):
        self.status_code = status
        self._payload = payload or {}

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _FakeSession:
    """Returns queued responses in order (per call)."""

    def __init__(self, responses):
        self._responses = list(responses)
        self.calls = 0

    def get(self, url, **kwargs):
        self.calls += 1
        return self._responses.pop(0)


def test_search_citation_success():
    sess = _FakeSession([_Resp(200, {"data": [{"title": "X", "citationCount": 42}]})])
    assert search_citation("X", sess, sleep=lambda *_: None) == 42


def test_search_citation_zero_distinct_from_none():
    sess = _FakeSession([_Resp(200, {"data": [{"title": "X", "citationCount": 0}]})])
    assert search_citation("X", sess, sleep=lambda *_: None) == 0


def test_search_citation_no_match_returns_none():
    sess = _FakeSession([_Resp(200, {"data": []})])
    assert search_citation("X", sess, sleep=lambda *_: None) is None


def test_search_citation_retries_then_succeeds_on_429():
    sess = _FakeSession([_Resp(429), _Resp(200, {"data": [{"citationCount": 7}]})])
    assert search_citation("X", sess, retries=2, sleep=lambda *_: None) == 7
    assert sess.calls == 2


def test_search_citation_gives_up_after_retries():
    sess = _FakeSession([_Resp(429), _Resp(429), _Resp(429)])
    assert search_citation("X", sess, retries=2, sleep=lambda *_: None) is None


def test_titles_for_topics_filters_by_topic():
    df = pd.DataFrame({
        "title": ["A", "B", "C"],
        "topic": ["graph;llm", "vision", "llm"],
    })
    assert set(titles_for_topics(df, {"llm"})) == {"A", "C"}


def test_sidecar_for_xlsx_mapping():
    from ai_trend.citations import sidecar_for_xlsx

    p = sidecar_for_xlsx("data/2024/6_cvpr.csv_topics.csv_emerging.xlsx")
    assert p.name == "6_cvpr.csv_topics.csv.citations.json"


def test_import_emerging_xlsx_and_merge(tmp_path):
    from ai_trend.citations import import_emerging_xlsx, load_cache, merge_into_sidecar, save_cache

    xlsx = tmp_path / "5_iclr.csv_topics.csv_emerging.xlsx"
    pd.DataFrame({
        "title": ["Paper A", "Paper B", "Paper C"],
        "ss_citations": [42, 0, float("nan")],  # NaN row skipped
    }).to_excel(xlsx, index=False)

    imported = import_emerging_xlsx(xlsx)
    assert imported == {"Paper A": 42, "Paper B": 0}

    # a live-fetched value already in the sidecar must win on overlap
    sidecar = tmp_path / "5_iclr.csv_topics.csv.citations.json"
    save_cache(sidecar, {"Paper A": 99})
    out, added = merge_into_sidecar(xlsx)
    assert out == sidecar
    merged = load_cache(sidecar)
    assert merged["Paper A"] == 99  # existing (fresh) preserved
    assert merged["Paper B"] == 0 and added == 1


def test_fetch_citations_is_resumable(tmp_path):
    cache = tmp_path / "c.json"
    # first run: 2 titles
    sess = _FakeSession([
        _Resp(200, {"data": [{"citationCount": 1}]}),
        _Resp(200, {"data": [{"citationCount": 2}]}),
    ])
    fetch_citations(["A", "B"], cache, sess, sleep=lambda *_: None)
    assert load_cache(cache) == {"A": 1, "B": 2}

    # second run: A cached (skipped), only C fetched
    sess2 = _FakeSession([_Resp(200, {"data": [{"citationCount": 3}]})])
    fetch_citations(["A", "C"], cache, sess2, sleep=lambda *_: None)
    assert sess2.calls == 1
    assert load_cache(cache) == {"A": 1, "B": 2, "C": 3}
