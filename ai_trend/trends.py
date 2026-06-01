"""Topic-frequency trends: top / emerging / fading per conference-year.

Ported from ``calculate_topic_frequency_ratio`` and the per-conference trend cells
in ``1.assign_topics.ipynb``. Definitions, preserved exactly (verified to reproduce
the committed README tables):

* **count** -- number of papers carrying a topic (a paper may carry several; the
  ``topic`` column is ``;``-joined).
* **top** -- the ``top_n`` topics by current-year count.
* **change ratio** -- ``(current - previous) / previous`` for the same conference
  one year earlier. A brand-new topic (previous count 0, current > 0) has an
  infinite ratio; a topic absent both years (0 -> 0) is undefined (NaN) and
  excluded from the emerging/fading lists.
* **emerging / fading** -- the ``top_n`` topics by highest / lowest change ratio.

Conference-year identity comes from the **file location** (folder = year, filename
prefix = conference), matching the notebook. The in-file ``source`` / ``year``
columns are NOT trusted: some are mislabeled (e.g. ``10_ICCV`` rows carry
``source=CVPR``) or mix years. Ties are broken by taxonomy insertion order via
Python's stable sort.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Iterable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ai_trend.taxonomy import Taxonomy

DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DEFAULT_TOP_N = 5
# Conference identity (filename token -> label) comes from the conference registry
# (config/conferences.json). See ai_trend.registry.
# A topic must have at least this many papers in the *previous* year to be eligible
# for emerging/fading. This excludes the undefined "0 -> n" case, whose infinite
# ratio otherwise lets a topic that merely first appears (often a back-labeling
# coincidence in older years) dominate "emerging". Calibrated against real data:
# every genuine emerger has prev >= 2, every anachronistic artifact has prev = 0.
DEFAULT_MIN_PREV = 1
# A topic must have at least this many papers in the *current* year to count as
# emerging -- a growing topic should have real volume, not a handful of keyword
# coincidences. Calibrated: genuine emergers have current count >= ~29 while
# back-labeling noise tops out at ~5. Applied to emerging only: fading topics are
# declining (often to near zero), so a current floor would wrongly exclude them.
DEFAULT_MIN_COUNT = 10
TOPICS_GLOB = "*.csv_topics.csv"
_YEAR_DIR = re.compile(r"^\d{4}$")


@dataclass
class Trend:
    """Trend lists for one conference-year (relative to the previous year)."""

    conference: str
    year: int
    previous_year: int | None
    top: list[str] = field(default_factory=list)
    emerging: list[str] = field(default_factory=list)
    fading: list[str] = field(default_factory=list)
    counts: dict[str, int] = field(default_factory=dict)


def parse_conference(filename: str, token_to_label: dict[str, str] | None = None) -> str | None:
    """Map a ``*_topics.csv`` filename to a canonical conference label.

    ``5_iclr.csv_topics.csv`` -> ``ICLR``; ``10_ICCV.csv_topics.csv`` -> ``ICCV``.
    ``token_to_label`` comes from the conference registry; if omitted it is loaded
    from the default config. Returns ``None`` if the token is not recognised.
    """
    if token_to_label is None:
        from ai_trend.registry import ConferenceRegistry

        token_to_label = ConferenceRegistry.load().token_to_label
    stem = filename.split(".csv", 1)[0]  # '5_iclr' from '5_iclr.csv_topics.csv'
    _, _, token = stem.partition("_")
    return token_to_label.get(token.lower())


def topic_counts(topics: Iterable[str], taxonomy: "Taxonomy") -> dict[str, int]:
    """Count papers per topic, initialising every taxonomy topic to 0.

    Initialising from the taxonomy guarantees zero-count topics are present, which
    matters for change ratios where the previous year had a topic the current year
    dropped.
    """
    counts = {topic: 0 for topic in taxonomy.topics}
    for cell in topics:
        for topic in str(cell).split(";"):
            if topic == "" or topic == "nan":
                break
            counts[topic] = counts.get(topic, 0) + 1
    return counts


def count_file(path: Path | str, taxonomy: "Taxonomy") -> dict[str, int]:
    import pandas as pd

    df = pd.read_csv(path)
    if "topic" not in df.columns:
        raise ValueError(f"{path} has no 'topic' column")
    return topic_counts(df["topic"], taxonomy)


def _change_ratio(current: int, previous: int) -> float:
    if previous == 0:
        return math.inf if current > 0 else math.nan
    return (current - previous) / previous


def compute_trends(
    conference: str,
    year: int,
    current: dict[str, int],
    previous: dict[str, int] | None,
    *,
    previous_year: int | None = None,
    top_n: int = DEFAULT_TOP_N,
    min_prev: int = DEFAULT_MIN_PREV,
    min_count: int = DEFAULT_MIN_COUNT,
) -> Trend:
    """Build the top/emerging/fading lists for one conference-year.

    With no previous year, only ``top`` is populated (emerging/fading need a
    baseline), mirroring the notebook and the README (e.g. 2023 ICCV).

    Eligibility (see ``DEFAULT_MIN_PREV`` / ``DEFAULT_MIN_COUNT``):

    * emerging -- ``previous >= min_prev`` (defined, finite ratio) AND
      ``current >= min_count`` (real current volume, not coincidental matches).
    * fading -- ``previous >= min_prev``. No current floor: a fading topic is by
      definition shrinking, often to near zero.
    """
    ordered = list(current)  # taxonomy order -> stable tie-breaking
    top = sorted(ordered, key=lambda t: current[t], reverse=True)[:top_n]

    emerging: list[str] = []
    fading: list[str] = []
    if previous is not None:
        with_baseline = [t for t in ordered if previous.get(t, 0) >= min_prev]
        ratios = {t: _change_ratio(current[t], previous.get(t, 0)) for t in with_baseline}
        emerging_eligible = [t for t in with_baseline if current[t] >= min_count]
        emerging = sorted(emerging_eligible, key=lambda t: ratios[t], reverse=True)[:top_n]
        fading = sorted(with_baseline, key=lambda t: ratios[t])[:top_n]

    return Trend(
        conference=conference,
        year=year,
        previous_year=previous_year if previous is not None else None,
        top=top,
        emerging=emerging,
        fading=fading,
        counts=current,
    )


def discover_conference_years(
    data_dir: Path | str = DEFAULT_DATA_DIR,
    token_to_label: dict[str, str] | None = None,
) -> dict[str, dict[int, Path]]:
    """Index ``{conference: {year: topics_csv_path}}`` from ``data/<year>/``."""
    if token_to_label is None:
        from ai_trend.registry import ConferenceRegistry

        token_to_label = ConferenceRegistry.load().token_to_label
    data_dir = Path(data_dir)
    index: dict[str, dict[int, Path]] = {}
    for year_dir in sorted(data_dir.iterdir()):
        if not year_dir.is_dir() or not _YEAR_DIR.match(year_dir.name):
            continue
        year = int(year_dir.name)
        for path in sorted(year_dir.glob(TOPICS_GLOB)):
            conference = parse_conference(path.name, token_to_label)
            if conference is None:
                continue
            index.setdefault(conference, {})[year] = path
    return index


def compute_all_trends(
    taxonomy: "Taxonomy",
    data_dir: Path | str = DEFAULT_DATA_DIR,
    *,
    top_n: int = DEFAULT_TOP_N,
    min_prev: int = DEFAULT_MIN_PREV,
    min_count: int = DEFAULT_MIN_COUNT,
) -> list[Trend]:
    """Compute trends for every conference-year, comparing to the prior year."""
    index = discover_conference_years(data_dir)
    counts_cache: dict[Path, dict[str, int]] = {}

    def counts_for(path: Path) -> dict[str, int]:
        if path not in counts_cache:
            counts_cache[path] = count_file(path, taxonomy)
        return counts_cache[path]

    results: list[Trend] = []
    for conference in sorted(index):
        years = index[conference]
        for year in sorted(years):
            previous = years.get(year - 1)
            results.append(
                compute_trends(
                    conference,
                    year,
                    counts_for(years[year]),
                    counts_for(previous) if previous else None,
                    previous_year=year - 1 if previous else None,
                    top_n=top_n,
                    min_prev=min_prev,
                    min_count=min_count,
                )
            )
    return results


def _quote_topics(topics: list[str]) -> str:
    return ", ".join(f"'{t}'" for t in topics)


def render_markdown(trends: list[Trend]) -> str:
    """Render README-style trend tables, newest year first."""
    lines: list[str] = []
    by_year: dict[int, list[Trend]] = {}
    for trend in trends:
        by_year.setdefault(trend.year, []).append(trend)

    for year in sorted(by_year, reverse=True):
        lines.append(f"# {year}\n")
        for trend in sorted(by_year[year], key=lambda t: t.conference):
            lines.append(f"## {year} {trend.conference}")
            lines.append("| **Type**            | Topics |")
            lines.append("|---------------------|--------|")
            lines.append(f"| **Top 5 topics**    | {_quote_topics(trend.top)} |")
            if trend.emerging:
                lines.append(f"| **Emerging topics** | {_quote_topics(trend.emerging)} |")
            if trend.fading:
                lines.append(f"| **Fading topics**   | {_quote_topics(trend.fading)} |")
            lines.append("")
    return "\n".join(lines)


def trend_to_dict(trend: Trend, *, include_counts: bool = False) -> dict:
    data = {
        "conference": trend.conference,
        "year": trend.year,
        "previous_year": trend.previous_year,
        "top": trend.top,
        "emerging": trend.emerging,
        "fading": trend.fading,
    }
    if include_counts:
        # Drop zero-count topics to keep the payload lean.
        data["counts"] = {t: c for t, c in trend.counts.items() if c > 0}
    return data
