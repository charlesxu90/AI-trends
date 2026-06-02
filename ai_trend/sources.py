"""URL -> source dispatch for the natural-language ingest flow.

Detects whether a conference URL points at OpenReview or thecvf (CVF open-access)
and extracts the conference label + year, so a single pasted URL can drive the
whole pipeline. The matched conference is resolved against the registry.

Examples
--------
- https://openreview.net/group?id=ICLR.cc/2025/Conference   -> openreview, ICLR 2025
- https://api2.openreview.net/notes?content.venueid=ICML.cc/2025/Conference -> openreview, ICML 2025
- https://openaccess.thecvf.com/CVPR2024?day=all            -> cvf, CVPR 2024
- https://openaccess.thecvf.com/ICCV2023                    -> cvf, ICCV 2023
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

from ai_trend.registry import ConferenceRegistry

# OpenReview group/venue id like "ICLR.cc/2025/Conference"
_OR_VENUEID = re.compile(r"([A-Za-z]+)\.cc/(\d{4})/", re.IGNORECASE)
# thecvf path like "/CVPR2024" or "/content/ICCV2023/..."
_CVF_SLUG = re.compile(r"/([A-Za-z]+)(\d{4})", re.IGNORECASE)


class SourceError(ValueError):
    """Raised when a URL cannot be mapped to a known conference-year."""


@dataclass(frozen=True)
class SourceSpec:
    source: str  # "openreview" | "cvf"
    label: str  # canonical conference label, e.g. "ICLR"
    token: str  # filename token, e.g. "iclr"
    year: int
    venueid: str | None = None  # OpenReview content.venueid (e.g. ICLR.cc/2025/Conference)


def _resolve(label_guess: str, year: int, registry: ConferenceRegistry):
    conf = registry.conference_for_token(label_guess.lower())
    if conf is None:
        raise SourceError(
            f"unknown conference {label_guess!r}; add it to config/conferences.json"
        )
    return conf, year


def detect_source(url: str, registry: ConferenceRegistry | None = None) -> SourceSpec:
    """Map a conference URL to a :class:`SourceSpec`."""
    registry = registry or ConferenceRegistry.load()
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()

    if "openreview.net" in host:
        venueid = _openreview_venueid(parsed)
        if not venueid:
            raise SourceError(
                "could not find a venue id (e.g. ICLR.cc/2025/Conference) in the OpenReview URL"
            )
        m = _OR_VENUEID.search(venueid + "/")
        conf, year = _resolve(m.group(1), int(m.group(2)), registry)
        return SourceSpec("openreview", conf.label, conf.primary_token, year, venueid=venueid)

    if "thecvf.com" in host:
        m = _CVF_SLUG.search(parsed.path)
        if not m:
            raise SourceError("could not find a CONF+YEAR slug (e.g. /CVPR2024) in the thecvf URL")
        conf, year = _resolve(m.group(1), int(m.group(2)), registry)
        return SourceSpec("cvf", conf.label, conf.primary_token, year)

    raise SourceError(f"unsupported host {host!r}; expected openreview.net or thecvf.com")


def _openreview_venueid(parsed) -> str | None:
    """Pull the venue id from query params or the path of an OpenReview URL."""
    qs = parse_qs(parsed.query)
    for key in ("content.venueid", "id", "group"):
        if key in qs and _OR_VENUEID.search(qs[key][0] + "/"):
            return qs[key][0]
    m = _OR_VENUEID.search(parsed.path + "/")
    if m:
        # reconstruct the canonical "<X>.cc/<year>/Conference" form
        return f"{m.group(1)}.cc/{m.group(2)}/Conference"
    return None
