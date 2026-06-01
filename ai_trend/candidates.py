"""Candidate-keyword extraction via scispaCy NER.

Ported from ``obtain_cadidate_keywords`` / ``count_keywords`` /
``get_keyword_by_spacy`` in ``1.assign_topics.ipynb``. Given a list of (lowercased)
paper titles, extract named entities, drop ones already known to the taxonomy or on
the noise blocklist, and keep those occurring more than ``threshold`` times.

The result feeds the ``curate-topics`` skill: each candidate carries its count and
a few example titles so the AI can decide noise vs. existing-topic vs. new-topic.

Improvements over the notebook (behaviour-preserving): the model is loaded once
(not per call) and ``max_length`` is raised so large conferences don't trip
spaCy's input-length guard.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    from spacy.language import Language

    from ai_trend.taxonomy import Taxonomy

DEFAULT_MODEL_PATH = (
    Path(__file__).resolve().parent.parent / "data" / "spacy-en_core_sci_lg-0.5.1"
)
DEFAULT_THRESHOLD = 5
DEFAULT_EXAMPLES = 3
# Headroom over the largest expected concatenated-title blob.
_MAX_DOC_CHARS = 5_000_000


@dataclass
class Candidate:
    """A candidate keyword awaiting AI curation."""

    keyword: str
    count: int
    examples: list[str]


def load_model(model_path: Path | str = DEFAULT_MODEL_PATH) -> "Language":
    import spacy

    model_path = Path(model_path)
    if not model_path.exists():
        raise FileNotFoundError(f"spaCy model not found: {model_path}")
    nlp = spacy.load(str(model_path))
    nlp.max_length = max(nlp.max_length, _MAX_DOC_CHARS)
    return nlp


def extract_entities(text: str, nlp: "Language") -> list[str]:
    return [ent.text for ent in nlp(text).ents]


def count_occurrences(titles: list[str], keyword: str) -> int:
    return sum(1 for title in titles if keyword in title)


def _examples_for(keyword: str, titles: list[str], limit: int) -> list[str]:
    out: list[str] = []
    for title in titles:
        if keyword in title:
            out.append(title)
            if len(out) >= limit:
                break
    return out


def candidate_keywords(
    titles: list[str],
    taxonomy: "Taxonomy",
    *,
    model_path: Path | str = DEFAULT_MODEL_PATH,
    threshold: int = DEFAULT_THRESHOLD,
    examples: int = DEFAULT_EXAMPLES,
    nlp: "Language | None" = None,
) -> list[Candidate]:
    """Return candidate keywords (count > ``threshold``), most frequent first.

    ``titles`` should be lowercased (matching the notebook), so entities and
    substring counts are computed consistently.
    """
    if nlp is None:
        nlp = load_model(model_path)

    blob = ". ".join(titles)
    entities = set(extract_entities(blob, nlp))

    known = taxonomy.known_keywords()
    blocked = taxonomy.useless_kw
    fresh = [kw for kw in entities if kw not in known and kw not in blocked]

    candidates = [
        Candidate(
            keyword=kw,
            count=count_occurrences(titles, kw),
            examples=_examples_for(kw, titles, examples),
        )
        for kw in fresh
    ]
    candidates = [c for c in candidates if c.count > threshold]
    candidates.sort(key=lambda c: c.count, reverse=True)
    return candidates


def candidates_to_dicts(candidates: list[Candidate]) -> list[dict]:
    return [asdict(c) for c in candidates]
