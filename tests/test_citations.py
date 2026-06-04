"""Tests for citation fetching (fake session, no network)."""

from __future__ import annotations

import pandas as pd

from ai_trend.citations import (
    _s2_headers,
    fetch_citations,
    load_cache,
    search_citation,
    titles_for_topics,
)


def test_s2_headers_omits_key_when_unset(monkeypatch):
    monkeypatch.delenv("S2_API_KEY", raising=False)
    assert "x-api-key" not in _s2_headers()


def test_s2_headers_includes_key_when_set(monkeypatch):
    monkeypatch.setenv("S2_API_KEY", "secret-key")
    assert _s2_headers()["x-api-key"] == "secret-key"


class _Resp:
    def __init__(self, status, payload=None, headers=None):
        self.status_code = status
        self._payload = payload or {}
        self.headers = headers or {}

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
    cache = tmp_path / "c.citations.json"
    # first run: 2 titles (verified -> responses must carry matching titles)
    sess = _FakeSession([
        _Resp(200, {"data": [{"title": "A", "citationCount": 1}]}),
        _Resp(200, {"data": [{"title": "B", "citationCount": 2}]}),
    ])
    fetch_citations(["A", "B"], cache, sess, sleep=lambda *_: None)
    assert load_cache(cache) == {"A": 1, "B": 2}

    # second run: A cached (skipped), only C fetched
    sess2 = _FakeSession([_Resp(200, {"data": [{"title": "C", "citationCount": 3}]})])
    fetch_citations(["A", "C"], cache, sess2, sleep=lambda *_: None)
    assert sess2.calls == 1
    assert load_cache(cache) == {"A": 1, "B": 2, "C": 3}


def test_search_openalex_verified_matches_title_and_returns_count():
    from ai_trend.citations import search_openalex_verified

    sess = _FakeSession([_Resp(200, {"results": [
        {"title": "Some Unrelated Work", "cited_by_count": 9000},
        {"title": "My Niche Paper", "cited_by_count": 7},
    ]})])
    out = search_openalex_verified("My Niche Paper", sess, sleep=lambda *_: None)
    assert out["citationCount"] == 7


def test_search_openalex_verified_failed_request_returns_sentinel():
    from ai_trend.citations import FETCH_FAILED, search_openalex_verified

    sess = _FakeSession([_Resp(429), _Resp(429)])
    assert search_openalex_verified("X", sess, retries=1, sleep=lambda *_: None) is FETCH_FAILED


def test_fetch_citations_with_progress_bar(tmp_path):
    """progress=True renders a tqdm bar without changing results."""
    cache = tmp_path / "c.citations.json"
    sess = _FakeSession([_Resp(200, {"data": [{"title": "A", "citationCount": 5}]})])
    fetch_citations(["A"], cache, sess, sleep=lambda *_: None, progress=True)
    assert load_cache(cache) == {"A": 5}


def test_fetch_citations_uses_injected_searcher(tmp_path):
    """fetch_citations honours a custom searcher (e.g. OpenAlex)."""
    cache = tmp_path / "c.citations.json"
    seen = []

    def fake_searcher(title, session, sleep=None):
        seen.append(title)
        return {"citationCount": 11, "arxiv": None, "title": title}

    fetch_citations(["A"], cache, _FakeSession([]), sleep=lambda *_: None, searcher=fake_searcher)
    assert seen == ["A"]
    assert load_cache(cache) == {"A": 11}


def test_search_paper_verified_failed_request_returns_sentinel():
    from ai_trend.citations import FETCH_FAILED, search_paper_verified

    sess = _FakeSession([_Resp(429), _Resp(429)])  # retries exhausted
    out = search_paper_verified("X", sess, retries=1, sleep=lambda *_: None)
    assert out is FETCH_FAILED


def test_fetch_citations_does_not_cache_failed_request(tmp_path):
    """A 429/network failure must NOT be cached as None — else a re-run skips it
    and the real count is lost forever."""
    cache = tmp_path / "c.citations.json"
    # A: request fails (5 attempts = retries 4 + 1), B: succeeds
    sess = _FakeSession([_Resp(429)] * 5 + [_Resp(200, {"data": [{"title": "B", "citationCount": 2}]})])
    fetch_citations(["A", "B"], cache, sess, sleep=lambda *_: None)
    assert load_cache(cache) == {"B": 2}  # A absent -> still pending

    # re-run: A now reachable, gets fetched (not skipped)
    sess2 = _FakeSession([_Resp(200, {"data": [{"title": "A", "citationCount": 9}]})])
    fetch_citations(["A", "B"], cache, sess2, sleep=lambda *_: None)
    assert load_cache(cache) == {"A": 9, "B": 2}


def test_fetch_citations_circuit_breaks_on_sustained_failures(tmp_path):
    from ai_trend.citations import MAX_CONSECUTIVE_FAILURES

    cache = tmp_path / "c.citations.json"
    titles = [f"T{i}" for i in range(MAX_CONSECUTIVE_FAILURES + 5)]
    sess = _FakeSession([_Resp(429)] * 200)  # everything 429s
    fetch_citations(titles, cache, sess, sleep=lambda *_: None)
    assert load_cache(cache) == {}  # nothing cached
    # stopped after MAX_CONSECUTIVE_FAILURES failures (each = retries+1 calls), not all titles
    assert sess.calls == MAX_CONSECUTIVE_FAILURES * 5


# ---- title verification ----------------------------------------------------
def test_titles_match():
    from ai_trend.citations import titles_match

    assert titles_match("Attention Is All You Need", "attention is all you need!")
    assert titles_match("Deep Residual Learning for Image Recognition",
                        "Deep Residual Learning for Image Recognition.")
    assert not titles_match("Attention Is All You Need", "A Survey of Transformers")


def test_search_paper_verified_skips_wrong_top_hit():
    from ai_trend.citations import search_paper_verified

    # top hit is a different (more-cited) paper; the real match is 2nd
    sess = _FakeSession([_Resp(200, {"data": [
        {"title": "A Famous Unrelated Survey", "citationCount": 9000},
        {"title": "My Niche Paper", "citationCount": 7},
    ]})])
    out = search_paper_verified("My Niche Paper", sess, sleep=lambda *_: None)
    assert out["citationCount"] == 7


def test_search_paper_verified_rejects_when_no_match():
    from ai_trend.citations import search_paper_verified

    sess = _FakeSession([_Resp(200, {"data": [{"title": "Totally Different", "citationCount": 9000}]})])
    assert search_paper_verified("My Paper", sess, sleep=lambda *_: None) is None


def test_search_paper_verified_captures_arxiv():
    from ai_trend.citations import search_paper_verified

    sess = _FakeSession([_Resp(200, {"data": [
        {"title": "My Paper", "citationCount": 5, "externalIds": {"ArXiv": "2401.00001"}},
    ]})])
    out = search_paper_verified("My Paper", sess, sleep=lambda *_: None)
    assert out["arxiv"] == "2401.00001" and out["citationCount"] == 5


def test_verify_existing_nulls_unverifiable_high_counts(tmp_path):
    from ai_trend.citations import save_cache, verify_existing

    cache = tmp_path / "x.citations.json"
    save_cache(cache, {"Real Paper": 800, "Tiny": 3})  # 800 is suspect, 3 is below min
    # the high-count entry resolves only to a different title -> must be nulled
    sess = _FakeSession([_Resp(200, {"data": [{"title": "Some Other Paper", "citationCount": 9000}]})])
    summary = verify_existing(cache, sess, min_count=150, sleep=lambda *_: None)
    out = load_cache(cache)
    assert out["Real Paper"] is None  # unverified -> dropped
    assert out["Tiny"] == 3           # untouched (below threshold)
    assert summary["checked"] == 1 and summary["unverified"] == 1


# ---- Crossref source --------------------------------------------------------
def test_search_crossref_verified_exact_match():
    from ai_trend.citations import search_crossref_verified

    sess = _FakeSession([_Resp(200, {"message": {"items": [
        {"title": ["My Exact Paper Title"], "is-referenced-by-count": 12},
    ]}})])
    out = search_crossref_verified("My Exact Paper Title", sess, sleep=lambda *_: None)
    assert out["citationCount"] == 12


def test_search_crossref_verified_rejects_reordered_near_title():
    """Strict exact-normalised match: a word-reordered near-title must NOT match
    (token-set Jaccard would wrongly accept it)."""
    from ai_trend.citations import search_crossref_verified

    sess = _FakeSession([_Resp(200, {"message": {"items": [
        {"title": ["Is Attention All You Need?"], "is-referenced-by-count": 46},
    ]}})])
    assert search_crossref_verified("Attention Is All You Need", sess, sleep=lambda *_: None) is None


def test_search_crossref_failed_request_returns_sentinel():
    from ai_trend.citations import FETCH_FAILED, search_crossref_verified

    sess = _FakeSession([_Resp(429), _Resp(429)])
    assert search_crossref_verified("X", sess, retries=1, sleep=lambda *_: None) is FETCH_FAILED


def test_build_providers_unknown_source_raises():
    from ai_trend.citations import build_providers

    try:
        build_providers(["openalex", "bogus"])
        assert False, "expected ValueError"
    except ValueError:
        pass


# ---- multi-source fallback --------------------------------------------------
class _Clock:
    def __init__(self):
        self.t = 0.0

    def time(self):
        return self.t

    def sleep(self, s):
        self.t += s


def _provider(name, cooldown, results):
    from ai_trend.citations import Provider

    state = {"i": 0}

    def fn(title, session, sleep=None):
        r = results[min(state["i"], len(results) - 1)]
        state["i"] += 1
        return r

    return Provider(name, fn, 0.0, cooldown)


def test_fetch_citations_multi_falls_back_to_next_source(tmp_path):
    from ai_trend.citations import FETCH_FAILED, fetch_citations_multi, load_cache

    cache = tmp_path / "c.citations.json"
    a = _provider("a", 100, [FETCH_FAILED])          # always rate-limited
    b = _provider("b", 100, [{"citationCount": 7, "arxiv": None}])
    fetch_citations_multi(["P"], cache, None, [a, b],
                          sleep=lambda *_: None)
    assert load_cache(cache) == {"P": 7}  # fell back to b


def test_fetch_citations_multi_caches_none_on_unanimous_no_match(tmp_path):
    from ai_trend.citations import fetch_citations_multi, load_cache

    cache = tmp_path / "c.citations.json"
    a = _provider("a", 100, [None])
    b = _provider("b", 100, [None])
    fetch_citations_multi(["P"], cache, None, [a, b],
                          sleep=lambda *_: None)
    assert load_cache(cache) == {"P": None}


def test_fetch_citations_multi_sleeps_when_all_blocked_then_resumes(tmp_path):
    from ai_trend.citations import FETCH_FAILED, fetch_citations_multi, load_cache

    cache = tmp_path / "c.citations.json"
    clock = _Clock()
    # both fail first, then succeed once their cooldown elapses
    a = _provider("a", 100, [FETCH_FAILED, {"citationCount": 1, "arxiv": None}])
    b = _provider("b", 50, [FETCH_FAILED, {"citationCount": 9, "arxiv": None}])
    fetch_citations_multi(["P"], cache, None, [a, b],
                          sleep=clock.sleep, time_fn=clock.time)
    # after both blocked, it slept until b (shorter cooldown) freed, then got b's count
    assert load_cache(cache) == {"P": 9}
    assert clock.t >= 50  # it actually slept through the cooldown


# ---- source-aware constraints (Retry-After + per-source backoff) ------------
def test_failed_request_carries_retry_after_header():
    from ai_trend.citations import _is_failed, search_paper_verified

    sess = _FakeSession([_Resp(429, headers={"Retry-After": "123"})])
    r = search_paper_verified("X", sess, retries=0, sleep=lambda *_: None)
    assert _is_failed(r) and r.retry_after == 123.0


def test_fetch_citations_multi_honours_retry_after_over_cooldown(tmp_path):
    """A server Retry-After takes precedence over the provider's default cooldown."""
    from ai_trend.citations import Provider, _Failed, fetch_citations_multi, load_cache

    cache = tmp_path / "c.citations.json"
    clock = _Clock()
    state = {"i": 0}

    def fn(title, session, sleep=None):
        state["i"] += 1
        if state["i"] == 1:
            return _Failed(retry_after=40)  # ask to wait 40s, not the 9999 cooldown
        return {"citationCount": 5, "arxiv": None}

    p = Provider("a", fn, throttle=0.0, cooldown=9999)
    fetch_citations_multi(["P"], cache, None, [p],
                          sleep=clock.sleep, time_fn=clock.time)
    assert load_cache(cache) == {"P": 5}
    assert 40 <= clock.t < 9999  # slept the Retry-After, not the long default cooldown
