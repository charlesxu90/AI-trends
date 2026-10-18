"""Tests for the method ontology (hierarchical tree of AI methods)."""

from __future__ import annotations

import json

import pytest

from ai_trend.ontology import (
    OntologyError,
    load_method_refs,
    load_ontology,
    validate_ontology,
    write_ontology,
)


def _tree():
    return {
        "version": "0.2",
        "domains": [
            {
                "code": "GEN",
                "name": "Generation",
                "summary": "Make things.",
                "children": [
                    {"name": "Image", "children": [
                        {"name": "Text-to-image", "examples": ["LDM", "DiT"]},
                    ]},
                ],
            }
        ],
        "facets": [{"name": "Modality", "tags": ["image", "text"]}],
        "heuristics": ["Ask for the central verb."],
    }


def test_validate_accepts_well_formed_tree():
    onto = validate_ontology(_tree())
    domains = onto["domains"]
    assert domains[0]["name"] == "Generation" and domains[0]["code"] == "GEN"
    assert domains[0]["children"][0]["children"][0]["examples"] == ["LDM", "DiT"]
    assert onto["facets"] == [{"name": "Modality", "tags": ["image", "text"]}]
    assert onto["heuristics"] == ["Ask for the central verb."]
    assert onto["version"] == "0.2"


def test_validate_defaults_optional_sections():
    onto = validate_ontology({"domains": []})
    assert onto == {"domains": [], "facets": [], "heuristics": []}


def test_validate_returns_new_object_without_mutating_input():
    tree = _tree()
    snapshot = json.dumps(tree)
    onto = validate_ontology(tree)
    onto["domains"][0]["name"] = "changed"
    onto["facets"][0]["tags"].append("x")
    assert json.dumps(tree) == snapshot


def test_validate_rejects_missing_domains_list():
    with pytest.raises(OntologyError, match="domains"):
        validate_ontology({"roots": []})


def test_validate_rejects_empty_name():
    tree = _tree()
    tree["domains"][0]["children"][0]["name"] = "  "
    with pytest.raises(OntologyError, match="name"):
        validate_ontology(tree)


def test_validate_rejects_duplicate_sibling_names():
    tree = _tree()
    family = tree["domains"][0]["children"][0]
    family["children"].append({"name": "Text-to-image"})
    with pytest.raises(OntologyError, match="duplicate"):
        validate_ontology(tree)


def test_validate_rejects_unknown_keys():
    tree = _tree()
    tree["domains"][0]["childs"] = []
    with pytest.raises(OntologyError, match="unknown"):
        validate_ontology(tree)


def test_validate_rejects_unknown_top_level_keys():
    tree = _tree()
    tree["extra"] = 1
    with pytest.raises(OntologyError, match="unknown"):
        validate_ontology(tree)


def test_validate_rejects_bad_facet():
    tree = _tree()
    tree["facets"] = [{"name": "Modality", "tags": "image"}]
    with pytest.raises(OntologyError, match="facet"):
        validate_ontology(tree)


def test_validate_rejects_non_string_heuristics():
    tree = _tree()
    tree["heuristics"] = ["ok", 1]
    with pytest.raises(OntologyError, match="heuristics"):
        validate_ontology(tree)


def test_validate_rejects_non_string_examples():
    tree = _tree()
    tree["domains"][0]["children"][0]["children"][0]["examples"] = ["ok", 3]
    with pytest.raises(OntologyError, match="examples"):
        validate_ontology(tree)


def test_validate_error_names_the_offending_path():
    tree = _tree()
    tree["domains"][0]["children"][0]["children"][0]["examples"] = "LDM"
    with pytest.raises(OntologyError, match="Generation > Image > Text-to-image"):
        validate_ontology(tree)


def test_load_and_write_round_trip(tmp_path):
    src = tmp_path / "ontology.json"
    src.write_text(json.dumps(_tree()), encoding="utf-8")

    onto = load_ontology(src)
    out = write_ontology(tmp_path / "site", onto)

    assert out == tmp_path / "site" / "ontology.json"
    assert json.loads(out.read_text(encoding="utf-8")) == onto


def test_load_missing_file_fails_clearly(tmp_path):
    with pytest.raises(OntologyError, match="not found"):
        load_ontology(tmp_path / "nope.json")


def test_repo_ontology_is_valid():
    onto = load_ontology()
    codes = [d.get("code") for d in onto["domains"]]
    assert len(codes) == 16 and len(set(codes)) == 16
    assert {"PRED", "GEN", "REPR", "SEG", "RECON", "OPT"} <= set(codes)
    assert onto["facets"] and onto["heuristics"]


def test_validate_accepts_and_normalizes_leaf_keywords():
    tree = _tree()
    tree["domains"][0]["children"][0]["children"][0]["keywords"] = [" Text-to-Image ", "^benchmark"]
    leaf = validate_ontology(tree)["domains"][0]["children"][0]["children"][0]
    assert leaf["keywords"] == ["text-to-image", "^benchmark"]


def test_validate_rejects_non_string_keywords():
    tree = _tree()
    tree["domains"][0]["children"][0]["children"][0]["keywords"] = ["ok", ""]
    with pytest.raises(OntologyError, match="keywords"):
        validate_ontology(tree)


def test_load_method_refs_validates_entries(tmp_path):
    good = tmp_path / "refs.json"
    good.write_text(json.dumps({"LDM": {"title": "High-Resolution Image Synthesis", "year": 2022,
                                        "url": "https://arxiv.org/abs/2112.10752"}}), encoding="utf-8")
    assert load_method_refs(good)["LDM"]["year"] == 2022

    bad = tmp_path / "bad.json"
    bad.write_text(json.dumps({"LDM": {"title": "x", "year": "2022"}}), encoding="utf-8")
    with pytest.raises(OntologyError, match="LDM"):
        load_method_refs(bad)


def test_repo_method_refs_cover_every_example():
    onto, refs = load_ontology(), load_method_refs()

    def examples(nodes):
        for node in nodes:
            yield from node.get("examples", [])
            yield from examples(node.get("children", []))

    assert sorted(set(examples(onto["domains"])) - set(refs)) == []
