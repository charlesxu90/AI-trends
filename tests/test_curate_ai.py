"""Tests for headless AI curation (parsing + decision via a fake client)."""

from __future__ import annotations

import json

import pytest

from ai_trend.curate_ai import decide, parse_response_text


class _Block:
    def __init__(self, text):
        self.text = text


class _Resp:
    def __init__(self, text):
        self.content = [_Block(text)]


class _FakeMessages:
    def __init__(self, text):
        self._text = text
        self.last_kwargs = None

    def create(self, **kwargs):
        self.last_kwargs = kwargs
        return _Resp(self._text)


class _FakeClient:
    def __init__(self, text):
        self.messages = _FakeMessages(text)


def test_parse_response_text_plain_json():
    assert parse_response_text('{"decisions": []}') == {"decisions": []}


def test_parse_response_text_strips_prose_and_fences():
    raw = "Here you go:\n```json\n{\"decisions\": [{\"keyword\": \"x\", \"action\": \"noise\"}]}\n```"
    out = parse_response_text(raw)
    assert out["decisions"][0]["keyword"] == "x"


def test_parse_response_text_raises_without_json():
    with pytest.raises(ValueError):
        parse_response_text("no json here")


def test_curate_with_ai_skips_api_when_no_candidates(tmp_path, monkeypatch):
    import json as _json

    import pandas as pd

    from ai_trend import curate_ai

    config = tmp_path / "config"
    config.mkdir()
    (config / "taxonomy.json").write_text(_json.dumps({"graph": ["graph"]}), encoding="utf-8")
    (config / "useless_keywords.json").write_text("[]", encoding="utf-8")
    csv = tmp_path / "p.csv"
    pd.DataFrame({"title": ["a paper"]}).to_csv(csv, index=False)

    # no candidates above threshold -> must not call the API
    monkeypatch.setattr("ai_trend.candidates.candidate_keywords", lambda *a, **k: [])
    client = _FakeClient('{"decisions": []}')

    result = curate_ai.curate_with_ai(csv, client, config_dir=config)
    assert client.messages.last_kwargs is None  # API never invoked
    assert result.other_keywords == []
    assert sum(result.summary.values()) == 0  # no decisions applied


def test_decide_calls_client_and_returns_parsed():
    payload = {"existing_topics": ["graph"], "candidates": [{"keyword": "gnn", "count": 9, "examples": []}]}
    client = _FakeClient('{"decisions": [{"keyword": "gnn", "action": "existing", "topic": "graph"}]}')
    out = decide(payload, client, model="m", max_tokens=100)
    assert out["decisions"][0]["action"] == "existing"
    # payload was sent as the user message
    sent = client.messages.last_kwargs
    assert sent["model"] == "m"
    assert json.loads(sent["messages"][0]["content"])["candidates"][0]["keyword"] == "gnn"
