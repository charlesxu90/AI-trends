"""Configurable conference registry.

The set of tracked conferences lives in ``config/conferences.json`` so adding a
venue is a config edit, not a code change. Each conference declares the canonical
label shown in outputs and the filename ``tokens`` used to recognise its data
files (e.g. ``5_iclr.csv_topics.csv`` -> token ``iclr`` -> label ``ICLR``).

A built-in default is used if the config file is absent, so the pipeline still
runs on a fresh checkout.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from ai_trend.taxonomy import DEFAULT_CONFIG_DIR

CONFERENCES_FILENAME = "conferences.json"

# Fallback used when config/conferences.json is missing. ``month`` sets the output
# CSV filename prefix (``<month>_<key>.csv``), matching the historical convention.
DEFAULT_CONFERENCES = [
    {"key": "iclr", "label": "ICLR", "name": "International Conference on Learning Representations", "tokens": ["iclr"], "month": 5, "source": "openreview", "openreview_group": "ICLR.cc"},
    {"key": "cvpr", "label": "CVPR", "name": "Conference on Computer Vision and Pattern Recognition", "tokens": ["cvpr"], "month": 6, "source": "cvf"},
    {"key": "iccv", "label": "ICCV", "name": "International Conference on Computer Vision", "tokens": ["iccv"], "month": 10, "source": "cvf"},
    {"key": "icml", "label": "ICML", "name": "International Conference on Machine Learning", "tokens": ["icml"], "month": 7, "source": "openreview", "openreview_group": "ICML.cc"},
    {"key": "nips", "label": "NIPS", "name": "Conference on Neural Information Processing Systems", "tokens": ["nips", "neurips"], "month": 12, "source": "openreview", "openreview_group": "NeurIPS.cc"},
    {"key": "aaai", "label": "AAAI", "name": "AAAI Conference on Artificial Intelligence", "tokens": ["aaai"], "month": 2, "source": "aaai"},
    {"key": "acl", "label": "ACL", "name": "Annual Meeting of the Association for Computational Linguistics", "tokens": ["acl"], "month": 8, "source": "acl"},
]


class RegistryError(ValueError):
    """Raised when conference registry data is invalid."""


@dataclass(frozen=True)
class Conference:
    key: str
    label: str
    name: str
    tokens: tuple[str, ...]
    month: int = 1  # output CSV filename prefix: <month>_<key>.csv
    source: str = "openreview"  # download source: "openreview" | "cvf"
    openreview_group: str | None = None  # api2 group base, e.g. "NeurIPS.cc" (NIPS!)

    @property
    def primary_token(self) -> str:
        return self.tokens[0]


@dataclass
class ConferenceRegistry:
    conferences: list[Conference]

    @classmethod
    def from_dicts(cls, raw: list[dict]) -> "ConferenceRegistry":
        conferences: list[Conference] = []
        for entry in raw:
            try:
                key = entry["key"]
                label = entry["label"]
                tokens = entry["tokens"]
            except (KeyError, TypeError) as exc:
                raise RegistryError(f"Invalid conference entry: {entry!r}") from exc
            if not tokens:
                raise RegistryError(f"Conference {key!r} must declare at least one token")
            conferences.append(
                Conference(
                    key=key,
                    label=label,
                    name=entry.get("name", label),
                    tokens=tuple(t.lower() for t in tokens),
                    month=int(entry.get("month", 1)),
                    source=entry.get("source", "openreview"),
                    openreview_group=entry.get("openreview_group"),
                )
            )
        return cls(conferences=conferences)

    @classmethod
    def load(cls, config_dir: Path | str = DEFAULT_CONFIG_DIR) -> "ConferenceRegistry":
        path = Path(config_dir) / CONFERENCES_FILENAME
        if not path.exists():
            return cls.from_dicts(DEFAULT_CONFERENCES)
        data = json.loads(path.read_text(encoding="utf-8"))
        conferences = data.get("conferences") if isinstance(data, dict) else None
        if not isinstance(conferences, list):
            raise RegistryError(f"{path} must contain a 'conferences' list")
        return cls.from_dicts(conferences)

    @property
    def token_to_label(self) -> dict[str, str]:
        """Lowercased filename token -> canonical label."""
        return {token: c.label for c in self.conferences for token in c.tokens}

    @property
    def labels(self) -> list[str]:
        return [c.label for c in self.conferences]

    def conference_for_token(self, token: str) -> Conference | None:
        token = token.lower()
        for c in self.conferences:
            if token in c.tokens:
                return c
        return None
