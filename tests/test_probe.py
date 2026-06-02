"""Tests for conference-availability probing (offline)."""

from __future__ import annotations

import pytest

from ai_trend.probe import candidate, probe, probe_label
from ai_trend.registry import ConferenceRegistry

REG = ConferenceRegistry.load()


def _conf(token):
    return REG.conference_for_token(token)


def test_candidate_cvf_url():
    url, src = candidate(_conf("cvpr"), 2025)
    assert src == "cvf"
    assert url == "https://openaccess.thecvf.com/CVPR2025?day=all"


def test_candidate_openreview_uses_neurips_group():
    url, src = candidate(_conf("nips"), 2025)  # NIPS label -> NeurIPS.cc group
    assert src == "openreview"
    assert "id=NeurIPS.cc/2025/Conference" in url


class _Resp:
    def __init__(self, payload=None, text=""):
        self._payload = payload or {}
        self.text = text

    def json(self):
        return self._payload


class _Sess:
    def __init__(self, resp):
        self._resp = resp

    def get(self, *a, **k):
        return self._resp


def test_probe_openreview_available():
    r = probe(_conf("iclr"), 2025, session=_Sess(_Resp(payload={"count": 3703})))
    assert r.available and r.count == 3703 and r.source == "openreview"


def test_probe_openreview_not_yet():
    r = probe(_conf("iclr"), 2026, session=_Sess(_Resp(payload={"count": 0})))
    assert not r.available and r.count == 0


def test_probe_cvf_counts_listing():
    html = (
        '<dt class="ptitle"><a href="/x">A</a></dt><dd></dd><dd></dd>'
        '<dt class="ptitle"><a href="/y">B</a></dt><dd></dd><dd></dd>'
    )
    r = probe(_conf("cvpr"), 2024, session=_Sess(_Resp(text=html)))
    assert r.count == 2 and r.available and r.source == "cvf"


def test_probe_label_unknown_raises():
    with pytest.raises(ValueError):
        probe_label("WACV", 2024, REG)
