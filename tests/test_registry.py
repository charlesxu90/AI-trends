"""Tests for the configurable conference registry."""

from __future__ import annotations

import json

import pytest

from ai_trend.registry import (
    DEFAULT_CONFIG_DIR,
    ConferenceRegistry,
    RegistryError,
)


def test_load_real_config_has_five_conferences():
    reg = ConferenceRegistry.load(DEFAULT_CONFIG_DIR)
    assert set(reg.labels) == {"ICLR", "CVPR", "ICCV", "ICML", "NIPS"}


def test_token_to_label_lowercases_and_includes_aliases():
    reg = ConferenceRegistry.load(DEFAULT_CONFIG_DIR)
    mapping = reg.token_to_label
    assert mapping["iclr"] == "ICLR"
    assert mapping["nips"] == "NIPS"
    assert mapping["neurips"] == "NIPS"  # alias token


def test_load_missing_file_falls_back_to_default(tmp_path):
    reg = ConferenceRegistry.load(tmp_path)  # no conferences.json here
    assert "ICLR" in reg.labels


def test_from_dicts_rejects_entry_without_tokens():
    with pytest.raises(RegistryError):
        ConferenceRegistry.from_dicts([{"key": "x", "label": "X", "tokens": []}])


def test_from_dicts_rejects_malformed_entry():
    with pytest.raises(RegistryError):
        ConferenceRegistry.from_dicts([{"key": "x"}])  # missing label/tokens


def test_custom_registry_drives_token_mapping(tmp_path):
    (tmp_path / "conferences.json").write_text(
        json.dumps(
            {"conferences": [{"key": "acl", "label": "ACL", "tokens": ["acl", "ACL"]}]}
        ),
        encoding="utf-8",
    )
    reg = ConferenceRegistry.load(tmp_path)
    assert reg.labels == ["ACL"]
    assert reg.token_to_label["acl"] == "ACL"


def test_registry_drives_trends_discovery(tmp_path):
    """Adding a conference via config makes discovery recognise its files."""
    import pandas as pd

    from ai_trend.trends import discover_conference_years

    (tmp_path / "2024").mkdir()
    pd.DataFrame({"topic": ["x"]}).to_csv(
        tmp_path / "2024" / "9_acl.csv_topics.csv", index=False
    )
    reg = ConferenceRegistry.from_dicts(
        [{"key": "acl", "label": "ACL", "tokens": ["acl"]}]
    )
    index = discover_conference_years(tmp_path, reg.token_to_label)
    assert "ACL" in index and 2024 in index["ACL"]
