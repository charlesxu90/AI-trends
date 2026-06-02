"""Tests for the OpenReview note -> record mapping (offline)."""

from __future__ import annotations

from ai_trend.openreview import _classify, note_to_record


def _note(title="A Paper", venue="ICLR 2025 Poster", authors=("X", "Y"), pdf="/pdf/a.pdf"):
    return {"content": {
        "title": {"value": title},
        "venue": {"value": venue},
        "authors": {"value": list(authors)},
        "abstract": {"value": "we study things"},
        "keywords": {"value": ["graph", "llm"]},
        "pdf": {"value": pdf},
    }}


def test_classify_from_venue():
    assert _classify("ICLR 2025 Poster") == "poster"
    assert _classify("ICML 2025 Oral") == "oral"
    assert _classify("NeurIPS 2025 Spotlight") == "spotlight"
    assert _classify("ICLR 2025 Conference") == ""


def test_note_to_record_full():
    r = note_to_record(_note(), "ICLR", 2025)
    assert r["title"] == "A Paper"
    assert r["authors"] == "'X', 'Y'"
    assert r["class"] == "poster"
    assert r["keywords"] == "graph, llm"
    assert r["pdf_link"] == "https://api2.openreview.net/pdf/a.pdf"
    assert r["abstract"] == "we study things"
    assert r["source"] == "ICLR" and r["year"] == 2025


def test_note_to_record_skips_titleless():
    assert note_to_record({"content": {}}, "ICLR", 2025) is None


def test_note_to_record_absolute_pdf_untouched():
    r = note_to_record(_note(pdf="https://x/y.pdf"), "ICLR", 2025)
    assert r["pdf_link"] == "https://x/y.pdf"
