"""Headless AI topic curation via the Anthropic API.

The interactive path is the ``curate-topics`` skill (Claude Code). For the
unattended monthly refresh, this module performs the same reasoning through the
Anthropic Messages API so it can run in CI. The decision schema and merge logic
are shared with the skill via :mod:`ai_trend.curate_io`.

The Anthropic client is injected, so the reasoning is unit-testable with a fake
client and the SDK is only imported when a real client is created (keeps the
package importable without ``anthropic`` installed).
"""

from __future__ import annotations

import json
import re
from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

from ai_trend.curate_io import apply_decision, build_curation_payload, parse_decision
from ai_trend.registry import ConferenceRegistry
from ai_trend.taxonomy import DEFAULT_CONFIG_DIR, Taxonomy

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_trend.curate_io import ApplyResult

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_TOKENS = 8000
OTHER_LEDGER_FILENAME = "other_keywords.json"

SYSTEM_PROMPT = """\
You curate candidate keywords into a fixed AI-conference topic taxonomy.

You receive JSON with `existing_topics` (the taxonomy) and `candidates`
(each: keyword, count, example titles). For EVERY candidate choose exactly one:
- "existing": a clear synonym/instance of an existing topic -> set "topic" to one of existing_topics (verbatim).
- "new": a genuinely distinct, substantive theme not covered by any existing topic AND with real volume -> set "topic" to a concise lowercase label.
- "noise": generic ML vocabulary or non-topics (e.g. "method", "framework", "approach").
- "other": a real but niche/uncertain concept not worth its own topic yet.

Rules:
- Prefer "existing" over "new"; only create new topics when nothing fits. Be conservative.
- Never force a bad fit; use "other" when unsure.
- Emit keywords in lowercase.
- Reuse existing topic labels EXACTLY as given.

Respond with ONLY a JSON object, no prose:
{"decisions":[{"keyword":"...","action":"existing|new|noise|other","topic":"... (for existing/new)"}]}
Include an entry for every candidate."""


class MessagesClient(Protocol):  # pragma: no cover - structural type
    def create(self, **kwargs: Any) -> Any: ...


class AnthropicLike(Protocol):  # pragma: no cover - structural type
    messages: MessagesClient


def make_client(api_key: str | None = None) -> "AnthropicLike":
    """Create a real Anthropic client (imported lazily)."""
    from anthropic import Anthropic

    return Anthropic(api_key=api_key) if api_key else Anthropic()


def _extract_text(response: Any) -> str:
    # Anthropic Messages API: response.content is a list of blocks with .text
    blocks = getattr(response, "content", None)
    if isinstance(blocks, list) and blocks:
        text = getattr(blocks[0], "text", None)
        if text is not None:
            return text
    return str(response)


def parse_response_text(text: str) -> dict:
    """Parse the model's reply into a decision dict, tolerating stray prose/fences."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise ValueError("no JSON object found in model response")
    return json.loads(match.group(0))


def decide(
    payload: dict,
    client: "AnthropicLike",
    *,
    model: str = DEFAULT_MODEL,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> dict:
    """Ask the model to curate the candidates; return the raw decision dict."""
    response = client.messages.create(
        model=model,
        max_tokens=max_tokens,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": json.dumps(payload, ensure_ascii=False)}],
    )
    return parse_response_text(_extract_text(response))


def curate_with_ai(
    csv_path: Path | str,
    client: "AnthropicLike",
    *,
    config_dir: Path | str = DEFAULT_CONFIG_DIR,
    taxonomy: Taxonomy | None = None,
    conference: str | None = None,
    year: str | int | None = None,
    threshold: int = 8,
    model: str = DEFAULT_MODEL,
    model_path: str | None = None,
) -> "ApplyResult":
    """Extract candidates, get an AI decision, apply it, and persist config."""
    from ai_trend.candidates import DEFAULT_MODEL_PATH, candidate_keywords

    config_dir = Path(config_dir)
    taxonomy = taxonomy or Taxonomy.load(config_dir)
    ledger = _load_ledger(config_dir)
    working = taxonomy.add_noise(ledger) if ledger else taxonomy

    import pandas as pd

    titles = pd.read_csv(csv_path)["title"].astype(str).str.lower().tolist()
    candidates = candidate_keywords(
        titles, working, model_path=model_path or str(DEFAULT_MODEL_PATH), threshold=threshold
    )
    if not candidates:
        # nothing new above threshold -> no taxonomy change, skip the API call
        return apply_decision(taxonomy, [])
    payload = build_curation_payload(candidates, working, conference=conference, year=year)

    decisions = parse_decision(decide(payload, client, model=model))
    result = apply_decision(taxonomy, decisions)

    result.taxonomy.save(config_dir)
    if result.other_keywords:
        _save_ledger(config_dir, [*ledger, *result.other_keywords])
    return result


def _load_ledger(config_dir: Path) -> list[str]:
    path = config_dir / OTHER_LEDGER_FILENAME
    return json.loads(path.read_text(encoding="utf-8")) if path.exists() else []


def _save_ledger(config_dir: Path, keywords: list[str]) -> None:
    (config_dir / OTHER_LEDGER_FILENAME).write_text(
        json.dumps(sorted(set(keywords)), indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
