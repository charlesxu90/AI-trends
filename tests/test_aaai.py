"""Tests for the AAAI OpenAlex adapter (offline)."""

from __future__ import annotations

from ai_trend.aaai import (
    fetch_aaai,
    page_count,
    reconstruct_abstract,
    work_to_record,
)


def _work(title="A Main Track Paper", first=10, last=18, abstract=None, authors=("Ada Lovelace",)):
    inv = abstract
    if abstract is not None and not isinstance(abstract, dict):
        # build an inverted index from a plain string for convenience
        inv = {w: [i] for i, w in enumerate(abstract.split())}
    return {
        "title": title,
        "biblio": {"first_page": first, "last_page": last},
        "abstract_inverted_index": inv,
        "authorships": [{"author": {"display_name": n}} for n in authors],
        "primary_location": {"landing_page_url": "https://doi.org/10.1609/aaai.x"},
        "doi": "https://doi.org/10.1609/aaai.x",
    }


def test_reconstruct_abstract_orders_by_position():
    inv = {"Hello": [0], "world": [1], "again": [2, 4], "hello": [3]}
    assert reconstruct_abstract(inv) == "Hello world again hello again"


def test_reconstruct_abstract_handles_empty():
    assert reconstruct_abstract(None) == ""
    assert reconstruct_abstract({}) == ""


def test_page_count():
    assert page_count({"biblio": {"first_page": 10, "last_page": 18}}) == 9
    assert page_count({"biblio": {"first_page": "x", "last_page": "y"}}) is None
    assert page_count({}) is None


def test_work_to_record_keeps_main_track():
    rec = work_to_record(_work(first=100, last=108, abstract="deep learning works"), 2024)
    assert rec is not None
    assert rec["source"] == "AAAI" and rec["year"] == 2024
    assert rec["authors"] == "'Ada Lovelace'"
    assert rec["abstract"] == "deep learning works"
    assert rec["pdf_link"].startswith("https://doi.org/")


def test_work_to_record_drops_short_papers():
    # 2-page student abstract -> dropped by default threshold
    assert work_to_record(_work(first=10, last=11), 2024) is None
    # unknown page span -> dropped
    assert work_to_record({"title": "No Biblio", "biblio": {}}, 2024) is None
    # empty title -> dropped
    assert work_to_record(_work(title=""), 2024) is None


def test_work_to_record_respects_custom_threshold():
    # with min_pages=1 the 2-page paper survives
    assert work_to_record(_work(first=10, last=11), 2024, min_pages=1) is not None


class _FakeResp:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        pass

    def json(self):
        return self._payload


class _FakeSession:
    """Returns two pages then stops; records the cursors requested."""

    def __init__(self, pages):
        self._pages = pages
        self.cursors = []

    def get(self, url, params=None, **kwargs):
        self.cursors.append(params["cursor"])
        return _FakeResp(self._pages[len(self.cursors) - 1])


def test_fetch_aaai_paginates_via_cursor():
    pages = [
        {"results": [_work(title="Paper One", first=1, last=9)], "meta": {"next_cursor": "C2"}},
        {"results": [_work(title="Paper Two", first=1, last=9)], "meta": {"next_cursor": None}},
    ]
    sess = _FakeSession(pages)
    recs = fetch_aaai(2024, mailto="x@y.z", throttle=0, session=sess)
    assert [r["title"] for r in recs] == ["Paper One", "Paper Two"]
    assert sess.cursors == ["*", "C2"]  # started at *, followed next_cursor


def test_fetch_aaai_dedupes_titles():
    dup = _work(title="Same Title", first=1, last=9)
    pages = [{"results": [dup, dup], "meta": {"next_cursor": None}}]
    recs = fetch_aaai(2024, throttle=0, session=_FakeSession(pages))
    assert len(recs) == 1
