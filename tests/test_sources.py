"""Tests for URL -> source detection."""

from __future__ import annotations

import pytest

from ai_trend.registry import ConferenceRegistry
from ai_trend.sources import SourceError, detect_source

REG = ConferenceRegistry.load()


def test_openreview_group_url():
    s = detect_source("https://openreview.net/group?id=ICML.cc/2025/Conference", REG)
    assert (s.source, s.label, s.token, s.year) == ("openreview", "ICML", "icml", 2025)
    assert s.venueid == "ICML.cc/2025/Conference"


def test_openreview_api_venueid_url():
    s = detect_source(
        "https://api2.openreview.net/notes?content.venueid=ICLR.cc/2024/Conference&limit=10", REG)
    assert s.source == "openreview" and s.label == "ICLR" and s.year == 2024


def test_thecvf_cvpr_url():
    s = detect_source("https://openaccess.thecvf.com/CVPR2024?day=all", REG)
    assert (s.source, s.label, s.year) == ("cvf", "CVPR", 2024)


def test_thecvf_iccv_content_path():
    s = detect_source("https://openaccess.thecvf.com/content/ICCV2023/papers/x.pdf", REG)
    assert s.source == "cvf" and s.label == "ICCV" and s.year == 2023


def test_unsupported_host_raises():
    with pytest.raises(SourceError):
        detect_source("https://example.com/CVPR2024", REG)


def test_unknown_conference_raises():
    with pytest.raises(SourceError):
        detect_source("https://openaccess.thecvf.com/WACV2024", REG)  # not in registry
