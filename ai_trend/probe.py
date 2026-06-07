"""Check whether a conference-year's accepted papers are published yet.

Used by the conference-watch flow: once a conference is within the tracking window,
probe its expected source URL to see if papers are live before ingesting.

- OpenReview venues (ICLR/ICML/NeurIPS): query api2 by ``content.venueid`` and read
  the result count.
- CVF venues (CVPR/ICCV): fetch the ``?day=all`` listing and count entries.
- ACL: fetch the Anthology ``<year>.acl.xml`` and count main-conference papers.
- AAAI: query OpenAlex for the proceedings source + year and read the count.

Deterministic (constructs the known URL patterns); the *date* discovery for
upcoming conferences is the web-search step in the ``track-conferences`` skill.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

from ai_trend.registry import Conference, ConferenceRegistry

if TYPE_CHECKING:  # pragma: no cover - typing only
    import requests

API2_BASE = "https://api2.openreview.net"
CVF_BASE = "https://openaccess.thecvf.com"
OPENALEX_WORKS = "https://api.openalex.org/works"


@dataclass
class ProbeResult:
    conference: str
    year: int
    source: str
    url: str
    available: bool
    count: int


def candidate(conference: Conference, year: int) -> tuple[str, str]:
    """Return ``(ingest_url, source)`` for a conference-year's expected source."""
    if conference.source == "cvf":
        return (f"{CVF_BASE}/{conference.label}{year}?day=all", "cvf")
    if conference.source == "acl":
        return (f"https://aclanthology.org/events/acl-{year}/", "acl")
    if conference.source == "aaai":
        return (f"aaai {year}", "aaai")  # bare spec; OpenAlex-backed (no listing URL)
    group = conference.openreview_group or f"{conference.label}.cc"
    return (f"https://openreview.net/group?id={group}/{year}/Conference", "openreview")


def probe(
    conference: Conference, year: int, *, session: "requests.Session | None" = None
) -> ProbeResult:
    """Probe the source and report whether papers are published (count > 0)."""
    import requests

    sess = session or requests.Session()
    url, source = candidate(conference, year)
    count = 0
    try:
        if source == "openreview":
            group = conference.openreview_group or f"{conference.label}.cc"
            api = f"{API2_BASE}/notes?content.venueid={group}/{year}/Conference&limit=1"
            count = int(sess.get(api, headers={"User-Agent": "ai-trend/0.1"}, timeout=30).json().get("count", 0))
        elif source == "acl":
            from ai_trend.acl import fetch_acl

            count = len(fetch_acl(year, session=sess))
        elif source == "aaai":
            from ai_trend.aaai import AAAI_SOURCE_ID

            api = (f"{OPENALEX_WORKS}?filter=publication_year:{year},"
                   f"primary_location.source.id:{AAAI_SOURCE_ID}&per-page=1")
            count = int((sess.get(api, headers={"User-Agent": "ai-trend/0.1"}, timeout=30)
                         .json().get("meta", {}) or {}).get("count", 0))
        else:  # cvf
            from ai_trend.cvf import parse_listing

            html = sess.get(url, headers={"User-Agent": "ai-trend/0.1"}, timeout=120).text
            count = len(parse_listing(html, conference.label, year))
    except Exception:
        count = 0
    return ProbeResult(conference.label, year, source, url, available=count > 0, count=count)


def probe_label(label_or_token: str, year: int, registry: ConferenceRegistry | None = None,
                *, session: "requests.Session | None" = None) -> ProbeResult:
    registry = registry or ConferenceRegistry.load()
    conf = registry.conference_for_token(label_or_token.lower())
    if conf is None:
        raise ValueError(f"unknown conference {label_or_token!r}")
    return probe(conf, year, session=session)
