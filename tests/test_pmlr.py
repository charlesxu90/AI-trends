"""Tests for the PMLR proceedings source (offline fixtures, fake session)."""

from __future__ import annotations

import pytest

from ai_trend.pmlr import fetch_pmlr, parse_config, parse_post, volume_from_url

POST = """---
title: 'TUR-DPO: Topology- and Uncertainty-Aware Direct Preference Optimization'
openreview: YDztzMJynP
abstract: Aligning large language models with human preferences is commonly
  done via RLHF.
layout: inproceedings
id: abas26a
author:
- given: Abdulhady
  family: Abas
- given: Fatemeh
  family: Daneshfar
pdf: https://raw.githubusercontent.com/mlresearch/v306/main/assets/abas26a/abas26a.pdf
---
"""

CONFIG = """---
booktitle: Proceedings of the 43rd International Conference on Machine Learning
shortname: ICML
volume: '306'
year: '2026'
---
"""


def test_parse_post_maps_front_matter_to_record():
    rec = parse_post(POST, "ICML", 2026)
    assert rec["title"] == "TUR-DPO: Topology- and Uncertainty-Aware Direct Preference Optimization"
    assert rec["authors"] == "'Abdulhady Abas', 'Fatemeh Daneshfar'"
    assert rec["abstract"] == "Aligning large language models with human preferences is commonly done via RLHF."
    assert rec["pdf_link"].endswith("abas26a.pdf")
    assert rec["source"] == "ICML" and rec["year"] == 2026
    assert rec["class"] == "" and rec["keywords"] == ""  # PMLR does not record oral/poster


def test_parse_post_skips_entries_without_a_title():
    assert parse_post("---\nabstract: x\n---\n", "ICML", 2026) is None
    assert parse_post("no front matter", "ICML", 2026) is None


def test_parse_config_reads_shortname_and_year():
    assert parse_config(CONFIG) == ("ICML", 2026)


@pytest.mark.parametrize("url", [
    "https://proceedings.mlr.press/v306/",
    "https://proceedings.mlr.press/v306",
    "http://proceedings.mlr.press/v306/abas26a.html",
])
def test_volume_from_url(url):
    assert volume_from_url(url) == "306"


def test_volume_from_url_rejects_non_volume_paths():
    with pytest.raises(ValueError, match="volume"):
        volume_from_url("https://proceedings.mlr.press/")


class _Resp:
    def __init__(self, status=200, text="", payload=None):
        self.status_code, self.text, self._payload = status, text, payload

    def json(self):
        return self._payload

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")


class _Session:
    """Serves the git tree API and raw post files; the first post fetch is throttled once."""

    def __init__(self):
        self.calls: list[str] = []
        self.throttled = False

    def get(self, url, **_):
        self.calls.append(url)
        if url.endswith("/git/trees/gh-pages"):
            return _Resp(payload={"tree": [{"path": "_posts", "type": "tree", "sha": "abc"}]})
        if url.endswith("/git/trees/abc"):
            return _Resp(payload={"tree": [{"path": "2026-a.md"}, {"path": "2026-b.md"}, {"path": "README"}]})
        if url.endswith("2026-a.md"):
            if not self.throttled:
                self.throttled = True
                return _Resp(status=429)
            return _Resp(text=POST)
        if url.endswith("2026-b.md"):
            return _Resp(text=POST.replace("TUR-DPO", "Other"))
        return _Resp(status=404)


def test_fetch_pmlr_lists_posts_retries_throttling_and_parses(monkeypatch):
    monkeypatch.setattr("ai_trend.pmlr.time.sleep", lambda _s: None)
    session = _Session()

    records = fetch_pmlr("306", "ICML", 2026, session=session, workers=1)

    assert sorted(r["title"].split(":")[0] for r in records) == ["Other", "TUR-DPO"]
    assert not any(u.endswith("README") for u in session.calls)  # only .md posts
    assert session.throttled  # the 429 was retried, not dropped


def test_parse_config_accepts_leading_comments():
    assert parse_config("# Site settings\n# more\n" + CONFIG) == ("ICML", 2026)
