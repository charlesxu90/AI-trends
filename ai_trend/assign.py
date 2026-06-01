"""Deterministic topic assignment by substring matching.

Ported verbatim (in semantics) from ``obtain_topic_for_text`` / ``assign_topics``
in ``1.assign_topics.ipynb``. Faithfulness matters: the committed ``*_topics.csv``
files were produced by this exact logic, and Milestone 1 proves the port matches.

Matching rules, preserved exactly from the notebook:

* The search text is ``f"{title_lower} {abstract_lower}"`` where each piece is
  lowercased independently; a missing abstract contributes the literal ``"None"``.
* A keyword is matched as a plain (case-sensitive) substring of that text. Because
  the text is already lowercased, keywords containing uppercase letters never
  match -- this is a known notebook quirk we intentionally reproduce.
* A paper receives every topic with at least one matching keyword, joined by
  ``;`` in taxonomy (insertion) order.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - typing only
    import pandas as pd

    from ai_trend.taxonomy import Taxonomy

TOPIC_COLUMN = "topic"
TITLE_COLUMN = "title"
ABSTRACT_COLUMN = "abstract"


def match_topics(text: str, topic2keywords: dict[str, list[str]]) -> list[str]:
    """Return topics whose keywords appear as substrings of ``text`` (as given).

    ``text`` is matched as-is; callers that want the notebook's behaviour pass an
    already-lowercased string (see :func:`build_search_text`).
    """
    matched: list[str] = []
    for topic, keywords in topic2keywords.items():
        for keyword in keywords:
            if keyword in text:
                matched.append(topic)
                break
    return matched


def build_search_text(title: object, abstract: object) -> str:
    """Reproduce the notebook's ``f'{title.lower()} {abstract.lower()|None}'``."""
    title_part = title.lower() if isinstance(title, str) else str(title).lower()
    abstract_part = abstract.lower() if isinstance(abstract, str) else None
    return f"{title_part} {abstract_part}"


def topics_for_paper(title: object, abstract: object, taxonomy: "Taxonomy") -> str:
    text = build_search_text(title, abstract)
    return ";".join(match_topics(text, taxonomy.topic2keywords))


def assign_dataframe(df: "pd.DataFrame", taxonomy: "Taxonomy") -> "pd.DataFrame":
    """Return a copy of ``df`` with a ``topic`` column appended."""
    for column in (TITLE_COLUMN, ABSTRACT_COLUMN):
        if column not in df.columns:
            raise ValueError(
                f"Input is missing required column {column!r}; got {list(df.columns)}"
            )
    result = df.copy()
    result[TOPIC_COLUMN] = [
        topics_for_paper(title, abstract, taxonomy)
        for title, abstract in zip(df[TITLE_COLUMN], df[ABSTRACT_COLUMN])
    ]
    return result


def assign_csv(in_path: str, out_path: str, taxonomy: "Taxonomy") -> "pd.DataFrame":
    """Read a papers CSV, assign topics, and write ``<out_path>``."""
    import pandas as pd  # local import keeps the deterministic core importable w/o pandas

    df = pd.read_csv(in_path)
    result = assign_dataframe(df, taxonomy)
    result.to_csv(out_path, index=False)
    return result
