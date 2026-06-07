"""Fetch ACL main-conference paper metadata from the ACL Anthology.

ACL is not on OpenReview or CVF. Its authoritative machine-readable record is the
ACL Anthology XML, one file per collection year at
``data/xml/<year>.acl.xml`` in the ``acl-org/acl-anthology`` GitHub repo. Each
file groups ``<paper>`` entries under ``<volume id="long">`` / ``"short"`` /
``"srw"`` / ``"demos"`` / ``"tutorials"``; the *main conference* is long + short.

Titles and abstracts may contain inline markup (e.g. ``<fixed-case>``); we take
the flattened text. PDF links follow ``https://aclanthology.org/<url>.pdf``.
Output matches :data:`ai_trend.ingest.RECORD_COLUMNS` so the rest of the pipeline
(assign -> trends -> site) is unchanged.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET

from ai_trend.ingest import RECORD_COLUMNS

if TYPE_CHECKING:  # pragma: no cover - typing only
    import requests

ANTHOLOGY_BASE = "https://aclanthology.org"
ACL_XML_BASE = "https://raw.githubusercontent.com/acl-org/acl-anthology/master/data/xml"
# Main-conference volumes; excludes findings, student research workshop, demos, tutorials.
MAIN_VOLUMES = ("long", "short")


def _flatten(elem: "ET.Element | None") -> str:
    """Full visible text of an element, stripping inline markup tags."""
    if elem is None:
        return ""
    return "".join(elem.itertext()).strip()


def _format_authors(names: list[str]) -> str:
    # match the OpenReview ``'A', 'B'`` format so site.parse_authors works uniformly
    return ", ".join(f"'{n}'" for n in names if n)


def _author_name(author: "ET.Element") -> str:
    first = _flatten(author.find("first"))
    last = _flatten(author.find("last"))
    return " ".join(part for part in (first, last) if part)


def parse_acl_xml(xml: str, year: int, *, volumes: tuple[str, ...] = MAIN_VOLUMES) -> list[dict]:
    """Parse an Anthology ``<year>.acl.xml`` document into records (RECORD_COLUMNS)."""
    root = ET.fromstring(xml)
    records: list[dict] = []
    for volume in root.findall("volume"):
        vid = volume.get("id", "")
        if vid not in volumes:
            continue
        for paper in volume.findall("paper"):
            title = _flatten(paper.find("title"))
            if not title:
                continue
            authors = [_author_name(a) for a in paper.findall("author")]
            url = _flatten(paper.find("url"))
            pdf = f"{ANTHOLOGY_BASE}/{url}.pdf" if url else ""
            records.append({
                "title": title,
                "year": year,
                "source": "ACL",
                "authors": _format_authors(authors),
                "class": vid,  # "long" / "short"
                "keywords": "",
                "abstract": _flatten(paper.find("abstract")),
                "pdf_link": pdf,
            })
    return records


def fetch_acl(
    year: int,
    *,
    base: str = ACL_XML_BASE,
    volumes: tuple[str, ...] = MAIN_VOLUMES,
    session: "requests.Session | None" = None,
) -> list[dict]:
    """Download and parse the ACL Anthology XML for ``year`` (main volumes)."""
    import requests

    sess = session or requests.Session()
    url = f"{base}/{year}.acl.xml"
    resp = sess.get(url, headers={"User-Agent": "ai-trend/0.1"}, timeout=120)
    resp.raise_for_status()
    return parse_acl_xml(resp.text, year, volumes=volumes)


def fetch_to_csv(year: int, out_path: Path | str, **kwargs) -> int:
    """Fetch ACL papers and write a source CSV; returns the row count."""
    import pandas as pd

    records = fetch_acl(year, **kwargs)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records, columns=RECORD_COLUMNS).to_csv(out_path, index=False)
    return len(records)
