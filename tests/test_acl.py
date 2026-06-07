"""Tests for the ACL Anthology XML parser (offline fixture)."""

from __future__ import annotations

from ai_trend.acl import parse_acl_xml

# Minimal Anthology-shaped XML: long + short main volumes plus an excluded srw volume.
# Title carries inline markup (<fixed-case>) that must be flattened.
FIXTURE = """<?xml version='1.0' encoding='UTF-8'?>
<collection id="2024.acl">
  <volume id="long" type="proceedings">
    <meta><booktitle>Long Papers</booktitle></meta>
    <paper id="1">
      <title><fixed-case>BERT</fixed-case> for Everything</title>
      <author><first>Ada</first><last>Lovelace</last></author>
      <author><first>Alan</first><last>Turing</last></author>
      <abstract>A study of <fixed-case>NLP</fixed-case> at scale.</abstract>
      <url hash="abc">2024.acl-long.1</url>
    </paper>
    <paper id="2">
      <title>Untitled Without Title Text</title>
      <author><first>Grace</first><last>Hopper</last></author>
      <url hash="def">2024.acl-long.2</url>
    </paper>
  </volume>
  <volume id="short" type="proceedings">
    <paper id="1">
      <title>A Short Contribution</title>
      <author><first>Edsger</first><last>Dijkstra</last></author>
      <abstract>Short but sweet.</abstract>
      <url hash="ghi">2024.acl-short.1</url>
    </paper>
  </volume>
  <volume id="srw" type="proceedings">
    <paper id="1">
      <title>Student Workshop Paper</title>
      <author><first>Some</first><last>Student</last></author>
      <url hash="jkl">2024.acl-srw.1</url>
    </paper>
  </volume>
</collection>
"""


def test_parses_main_volumes_only():
    recs = parse_acl_xml(FIXTURE, 2024)
    # 2 long + 1 short = 3; the srw volume is excluded
    assert len(recs) == 3
    assert all(r["source"] == "ACL" and r["year"] == 2024 for r in recs)
    assert {r["class"] for r in recs} == {"long", "short"}


def test_flattens_markup_and_formats_fields():
    recs = parse_acl_xml(FIXTURE, 2024)
    r = recs[0]
    assert r["title"] == "BERT for Everything"
    assert r["authors"] == "'Ada Lovelace', 'Alan Turing'"
    assert r["abstract"] == "A study of NLP at scale."
    assert r["pdf_link"] == "https://aclanthology.org/2024.acl-long.1.pdf"
    assert r["keywords"] == ""


def test_paper_without_abstract_still_ingested():
    recs = parse_acl_xml(FIXTURE, 2024)
    no_abs = [r for r in recs if r["title"] == "Untitled Without Title Text"][0]
    assert no_abs["abstract"] == ""
    assert no_abs["pdf_link"] == "https://aclanthology.org/2024.acl-long.2.pdf"


def test_custom_volume_filter():
    recs = parse_acl_xml(FIXTURE, 2024, volumes=("srw",))
    assert len(recs) == 1
    assert recs[0]["title"] == "Student Workshop Paper"
