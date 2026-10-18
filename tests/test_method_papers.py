"""Tests for matching corpus papers onto method-tree leaves."""

from __future__ import annotations

from ai_trend.method_papers import (
    compile_matcher,
    match_leaves,
    paper_link,
    short_name,
    site_ontology,
    tokenize,
)


def _ontology():
    return {
        "domains": [
            {"code": "RECON", "name": "Reconstruction", "children": [
                {"name": "3D", "children": [
                    {"name": "NeRF", "keywords": ["neural radiance field", "nerf"], "examples": ["NeRF"]},
                    {"name": "Splatting", "keywords": ["gaussian splatting"]},
                ]},
            ]},
            {"code": "GEN", "name": "Generation", "children": [
                {"name": "Advances", "children": [
                    {"name": "GANs", "keywords": ["gan"]},
                    {"name": "Benchmarks", "keywords": ["^benchmark"]},
                ]},
            ]},
        ],
        "facets": [],
        "heuristics": [],
    }


def _paper(title, year=2024, citations=None, arxiv=None, conference="CVPR"):
    record = {"title": title, "year": year, "conference": conference, "pdf": "", "authors": [], "topics": []}
    if citations is not None:
        record["citations"] = citations
    if arxiv:
        record["arxiv"] = arxiv
    return record


def test_tokenize_lowercases_and_splits_on_punctuation():
    assert tokenize("Text-to-Image: SE(3) NeRFs!") == ["text", "to", "image", "se", "3", "nerfs"]


def test_match_is_whole_word_and_plural_tolerant():
    matcher = compile_matcher(_ontology()["domains"])
    hits = match_leaves(matcher, "Fast Neural Radiance Fields", "")
    assert set(hits) == {0}
    assert hits[0] is True  # matched in the title
    assert match_leaves(matcher, "Organ segmentation", "") == {}  # 'gan' is not a word in 'organ'
    assert set(match_leaves(matcher, "Better GANs", "")) == {2}


def test_abstract_only_match_is_flagged_as_non_title():
    matcher = compile_matcher(_ontology()["domains"])
    hits = match_leaves(matcher, "A new renderer", "We build on 3D Gaussian Splatting.")
    assert hits == {1: False}


def test_title_only_keywords_ignore_the_abstract():
    matcher = compile_matcher(_ontology()["domains"])
    assert match_leaves(matcher, "Method X", "We evaluate on a benchmark.") == {}
    assert set(match_leaves(matcher, "A Benchmark for X", "")) == {3}


def test_short_name_uses_colon_prefix_when_short():
    assert short_name("DUSt3R: Geometric 3D Vision Made Easy") == "DUSt3R"
    assert short_name("Segment Anything") == "Segment Anything"
    long_prefix = "A Very Long Prefix That Is Clearly A Sentence Rather Than A Name: Subtitle"
    assert short_name(long_prefix) == long_prefix


def test_paper_link_prefers_arxiv_then_pdf_then_scholar():
    assert paper_link({"title": "T", "arxiv": "2401.00001", "pdf": "http://x/p.pdf"}) == "https://arxiv.org/abs/2401.00001"
    assert paper_link({"title": "T", "pdf": "http://x/p.pdf"}) == "http://x/p.pdf"
    assert paper_link({"title": "A B", "pdf": ""}).startswith("https://scholar.google.com/scholar?q=A%20B")


def test_site_ontology_ranks_title_hits_then_citations_per_year():
    onto = _ontology()
    matcher = compile_matcher(onto["domains"])
    papers = [
        (_paper("NeRF-W: in the wild", 2024, citations=5), "", ),
        (_paper("Something else", 2024, citations=900), "we use a neural radiance field"),
        (_paper("Mip-NeRF 2", 2024, citations=50), ""),
        (_paper("Old NeRF", 2023, citations=1), ""),
    ]
    matched = [(rec, match_leaves(matcher, rec["title"], abstract)) for rec, abstract in papers]

    site = site_ontology(onto, {}, matched, per_year=2)

    leaf = site["domains"][0]["children"][0]["children"][0]
    assert leaf["paper_count"] == 4
    years = leaf["papers"]
    assert [y["year"] for y in years] == [2024, 2023]  # newest first
    # title hits outrank the more-cited abstract-only match; capped at per_year
    assert [p["title"] for p in years[0]["papers"]] == ["Mip-NeRF 2", "NeRF-W: in the wild"]
    assert years[0]["papers"][1]["name"] == "NeRF-W"


def test_site_ontology_counts_unique_papers_up_the_tree():
    onto = _ontology()
    matcher = compile_matcher(onto["domains"])
    rec = _paper("NeRF meets Gaussian Splatting")
    site = site_ontology(onto, {}, [(rec, match_leaves(matcher, rec["title"], ""))])

    domain = site["domains"][0]
    assert domain["paper_count"] == 1  # one paper, even though it hits two leaves
    assert [leaf["paper_count"] for leaf in domain["children"][0]["children"]] == [1, 1]
    assert site["domains"][1]["paper_count"] == 0


def test_site_ontology_attaches_method_refs_without_mutating_input():
    onto = _ontology()
    refs = {"NeRF": {"title": "NeRF: Representing Scenes", "year": 2020, "url": "https://arxiv.org/abs/2003.08934"}}

    site = site_ontology(onto, refs, [])

    assert site["methods"] == refs
    assert "methods" not in onto and "paper_count" not in onto["domains"][0]


def test_site_ontology_collapses_duplicate_papers_by_title():
    onto = _ontology()
    matcher = compile_matcher(onto["domains"])
    a = _paper("Aligned NeRF", 2021, conference="NIPS")
    b = _paper("Aligned  NeRF", 2021, conference="NIPS")  # same paper listed twice
    site = site_ontology(onto, {}, [(r, match_leaves(matcher, r["title"], "")) for r in (a, b)])

    leaf = site["domains"][0]["children"][0]["children"][0]
    assert leaf["paper_count"] == 1
    assert len(leaf["papers"][0]["papers"]) == 1
