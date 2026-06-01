"""I/O glue between candidate extraction and the ``curate-topics`` skill.

The skill (Claude as the reasoning core) reads a *curation payload* -- candidate
keywords with counts and example titles, plus the existing taxonomy to anchor on --
and emits a *decision*: for each keyword, whether it is noise, belongs to an
existing topic, seeds a new topic, or should be parked in the ``other`` bucket.

This module builds the payload and validates + applies the decision. Keeping it
pure (no spaCy, no Anthropic SDK) makes the reasoning seam fully unit-testable;
the actual reasoning is exercised by running the skill.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from ai_trend.taxonomy import Taxonomy

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_trend.candidates import Candidate

# What the skill may decide for each candidate keyword.
ACTION_EXISTING = "existing"  # map keyword to an already-defined topic
ACTION_NEW = "new"  # seed a new topic with this keyword
ACTION_NOISE = "noise"  # generic / meaningless -> blocklist
ACTION_OTHER = "other"  # real but not worth a topic yet -> parked, not assigned
VALID_ACTIONS = frozenset({ACTION_EXISTING, ACTION_NEW, ACTION_NOISE, ACTION_OTHER})

PAYLOAD_VERSION = 1


class DecisionError(ValueError):
    """Raised when a curation decision is malformed."""


@dataclass
class Decision:
    keyword: str
    action: str
    topic: str | None = None


@dataclass
class ApplyResult:
    """Outcome of merging a decision into the taxonomy."""

    taxonomy: Taxonomy
    other_keywords: list[str]
    summary: dict[str, int] = field(default_factory=dict)


def build_curation_payload(
    candidates: "list[Candidate]",
    taxonomy: Taxonomy,
    *,
    conference: str | None = None,
    year: str | int | None = None,
) -> dict:
    """Assemble the JSON payload the ``curate-topics`` skill consumes."""
    return {
        "version": PAYLOAD_VERSION,
        "conference": conference,
        "year": str(year) if year is not None else None,
        "existing_topics": taxonomy.topics,
        "candidates": [
            {"keyword": c.keyword, "count": c.count, "examples": list(c.examples)}
            for c in candidates
        ],
    }


def parse_decision(raw: dict) -> list[Decision]:
    """Validate the skill's raw decision dict into ``Decision`` objects.

    Fails fast (never silently drops entries) on: missing ``decisions`` list,
    unknown actions, missing topic for existing/new, duplicate keywords, or blanks.
    """
    if not isinstance(raw, dict) or "decisions" not in raw:
        raise DecisionError("decision must be an object with a 'decisions' list")
    entries = raw["decisions"]
    if not isinstance(entries, list):
        raise DecisionError("'decisions' must be a list")

    decisions: list[Decision] = []
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise DecisionError(f"decision[{index}] must be an object")
        keyword = entry.get("keyword")
        action = entry.get("action")
        topic = entry.get("topic")

        if not isinstance(keyword, str) or not keyword.strip():
            raise DecisionError(f"decision[{index}] has an invalid 'keyword'")
        if action not in VALID_ACTIONS:
            raise DecisionError(
                f"decision[{index}] keyword={keyword!r} has invalid action "
                f"{action!r}; expected one of {sorted(VALID_ACTIONS)}"
            )
        if action in (ACTION_EXISTING, ACTION_NEW):
            if not isinstance(topic, str) or not topic.strip():
                raise DecisionError(
                    f"decision[{index}] action={action!r} requires a non-empty 'topic'"
                )
        if keyword in seen:
            raise DecisionError(f"duplicate decision for keyword {keyword!r}")
        seen.add(keyword)
        decisions.append(Decision(keyword=keyword, action=action, topic=topic))
    return decisions


def apply_decision(taxonomy: Taxonomy, decisions: list[Decision]) -> ApplyResult:
    """Merge decisions into a *new* taxonomy (the input is never mutated).

    ``existing`` requires the topic to already exist; ``new`` creates it (and is
    idempotent if it happens to exist). ``other`` keywords are returned for the
    caller to park in the ledger, not assigned.
    """
    result = taxonomy
    other: list[str] = []
    summary = {action: 0 for action in VALID_ACTIONS}

    for decision in decisions:
        if decision.action == ACTION_EXISTING:
            if decision.topic not in result.topic2keywords:
                raise DecisionError(
                    f"keyword {decision.keyword!r} maps to unknown existing topic "
                    f"{decision.topic!r}"
                )
            result = result.add_keywords(decision.topic, [decision.keyword])
        elif decision.action == ACTION_NEW:
            result = result.add_keywords(decision.topic, [decision.keyword])
        elif decision.action == ACTION_NOISE:
            result = result.add_noise([decision.keyword])
        else:  # ACTION_OTHER
            other.append(decision.keyword)
        summary[decision.action] += 1

    result.validate()
    return ApplyResult(taxonomy=result, other_keywords=other, summary=summary)
