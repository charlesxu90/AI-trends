"""The curated topic taxonomy and noise blocklist.

Single source of truth lives in ``config/taxonomy.json`` (topic -> keyword list)
and ``config/useless_keywords.json`` (noise keyword list), migrated out of the
original notebook by ``scripts/migrate_notebook_taxonomy.py``.

Design notes faithful to the original notebook:

* A keyword may appear under more than one topic -- that is intentional
  multi-label behaviour (e.g. ``graph representation learning`` implies both
  ``graph`` and ``representation``). We do NOT enforce cross-topic uniqueness.
* Topic insertion order is significant: it determines the order topics appear in
  the ``;``-joined ``topic`` column, so we preserve JSON order on load and save.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

TAXONOMY_FILENAME = "taxonomy.json"
BLOCKLIST_FILENAME = "useless_keywords.json"

# Resolve the repo's default config dir relative to this file.
DEFAULT_CONFIG_DIR = Path(__file__).resolve().parent.parent / "config"


class TaxonomyError(ValueError):
    """Raised when taxonomy data is structurally invalid."""


def _dedupe_preserve_order(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            out.append(value)
    return out


@dataclass
class Taxonomy:
    """Curated topic->keywords map plus the noise-keyword blocklist."""

    topic2keywords: dict[str, list[str]] = field(default_factory=dict)
    useless_kw: set[str] = field(default_factory=set)

    # ---- construction -------------------------------------------------------
    @classmethod
    def load(cls, config_dir: Path | str = DEFAULT_CONFIG_DIR) -> "Taxonomy":
        config_dir = Path(config_dir)
        taxonomy_path = config_dir / TAXONOMY_FILENAME
        blocklist_path = config_dir / BLOCKLIST_FILENAME
        if not taxonomy_path.exists():
            raise FileNotFoundError(f"Taxonomy file not found: {taxonomy_path}")
        if not blocklist_path.exists():
            raise FileNotFoundError(f"Blocklist file not found: {blocklist_path}")

        topic2keywords = json.loads(taxonomy_path.read_text(encoding="utf-8"))
        blocklist = json.loads(blocklist_path.read_text(encoding="utf-8"))
        taxonomy = cls(topic2keywords=topic2keywords, useless_kw=set(blocklist))
        taxonomy.validate()
        return taxonomy

    def save(self, config_dir: Path | str = DEFAULT_CONFIG_DIR) -> None:
        config_dir = Path(config_dir)
        config_dir.mkdir(parents=True, exist_ok=True)
        (config_dir / TAXONOMY_FILENAME).write_text(
            json.dumps(self.topic2keywords, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        (config_dir / BLOCKLIST_FILENAME).write_text(
            json.dumps(sorted(self.useless_kw), indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )

    # ---- validation ---------------------------------------------------------
    def validate(self) -> None:
        if not isinstance(self.topic2keywords, dict):
            raise TaxonomyError("topic2keywords must be a mapping")
        for topic, keywords in self.topic2keywords.items():
            if not isinstance(topic, str) or not topic.strip():
                raise TaxonomyError(f"Invalid topic name: {topic!r}")
            if not isinstance(keywords, list) or not keywords:
                raise TaxonomyError(f"Topic {topic!r} must map to a non-empty list")
            for kw in keywords:
                if not isinstance(kw, str) or not kw.strip():
                    raise TaxonomyError(f"Topic {topic!r} has an invalid keyword: {kw!r}")
        if not all(isinstance(kw, str) and kw.strip() for kw in self.useless_kw):
            raise TaxonomyError("useless_kw must contain only non-empty strings")

    # ---- queries ------------------------------------------------------------
    def known_keywords(self) -> set[str]:
        """Every keyword already mapped to some topic."""
        return {kw for keywords in self.topic2keywords.values() for kw in keywords}

    @property
    def topics(self) -> list[str]:
        return list(self.topic2keywords)

    # ---- mutation (returns new objects; never mutates in place) -------------
    def add_keywords(self, topic: str, keywords: list[str]) -> "Taxonomy":
        """Return a copy with ``keywords`` added to ``topic`` (created if absent)."""
        if not topic or not topic.strip():
            raise TaxonomyError("topic name must be non-empty")
        new_map = {t: list(kws) for t, kws in self.topic2keywords.items()}
        existing = new_map.get(topic, [])
        new_map[topic] = _dedupe_preserve_order([*existing, *keywords])
        return Taxonomy(topic2keywords=new_map, useless_kw=set(self.useless_kw))

    def add_noise(self, keywords: list[str]) -> "Taxonomy":
        """Return a copy with ``keywords`` added to the noise blocklist."""
        return Taxonomy(
            topic2keywords={t: list(kws) for t, kws in self.topic2keywords.items()},
            useless_kw=self.useless_kw | set(keywords),
        )
