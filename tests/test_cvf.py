"""Tests for the thecvf listing parser (offline fixture)."""

from __future__ import annotations

from ai_trend.cvf import parse_listing

# Minimal CVF-listing-shaped HTML: dt.ptitle + dd(authors) + dd(links).
FIXTURE = """
<dl>
  <dt class="ptitle"><a href="/html/x">A Great Vision Paper</a></dt>
  <dd><a href="/a/1">Ada Lovelace</a>, <a href="/a/2">Alan Turing</a></dd>
  <dd>
    <a href="/content/CVPR2024/papers/Great_paper.pdf">pdf</a>
    <a href="https://arxiv.org/abs/1">arXiv</a>
  </dd>
  <dt class="ptitle"><a href="/html/y">Second Paper</a></dt>
  <dd><a href="/a/3">Grace Hopper</a></dd>
  <dd><a href="https://arxiv.org/abs/2">arXiv</a></dd>
</dl>
"""


def test_parse_listing_extracts_records():
    recs = parse_listing(FIXTURE, "CVPR", 2024)
    assert len(recs) == 2
    r = recs[0]
    assert r["title"] == "A Great Vision Paper"
    assert r["authors"] == "'Ada Lovelace', 'Alan Turing'"
    assert r["source"] == "CVPR" and r["year"] == 2024
    # pdf chosen by .pdf suffix, prefixed with the CVF base
    assert r["pdf_link"] == "https://openaccess.thecvf.com/content/CVPR2024/papers/Great_paper.pdf"
    # CVF has no abstracts/keywords/class
    assert r["abstract"] == "" and r["keywords"] == "" and r["class"] == ""


def test_parse_listing_handles_missing_pdf():
    # second paper's links dd has only an arXiv link -> pdf empty, not a crash
    recs = parse_listing(FIXTURE, "CVPR", 2024)
    assert recs[1]["title"] == "Second Paper"
    assert recs[1]["pdf_link"] == ""


def test_parse_listing_empty_html():
    assert parse_listing("<html></html>", "ICCV", 2023) == []
