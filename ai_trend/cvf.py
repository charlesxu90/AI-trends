"""Scrape CVPR/ICCV paper metadata from CVF open-access (openaccess.thecvf.com).

CVPR/ICCV are not on OpenReview; their accepted-paper listings live at
``https://openaccess.thecvf.com/<CONF><YEAR>?day=all``. Ported and hardened from
the original CVPR-processing notebook: robust sibling navigation (``find_next_sibling``),
PDF link picked by ``.pdf`` suffix (not "first anchor"), per-paper errors skipped
rather than aborting the run.

The CVF listing has no abstracts (they live on per-paper pages), so ``abstract``,
``keywords``, and ``class`` are left empty — topic assignment for CVPR/ICCV uses
the title, as it already does for the committed data.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

from ai_trend.ingest import RECORD_COLUMNS

if TYPE_CHECKING:  # pragma: no cover - typing only
    import requests

CVF_BASE = "https://openaccess.thecvf.com"


def _format_authors(names: list[str]) -> str:
    # match the OpenReview ``'A', 'B'`` format so site.parse_authors works uniformly
    return ", ".join(f"'{n}'" for n in names if n)


def parse_listing(html: str, label: str, year: int, *, base: str = CVF_BASE) -> list[dict]:
    """Parse a CVF ``?day=all`` listing page into records (RECORD_COLUMNS)."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html, "html.parser")
    records: list[dict] = []
    for dt in soup.find_all("dt", class_="ptitle"):
        anchor = dt.find("a")
        if anchor is None or not anchor.text.strip():
            continue
        title = anchor.text.strip()
        dd_authors = dt.find_next_sibling("dd")
        authors = [a.text.strip() for a in dd_authors.find_all("a")] if dd_authors else []
        dd_links = dd_authors.find_next_sibling("dd") if dd_authors else None
        pdf = ""
        if dd_links:
            for a in dd_links.find_all("a"):
                href = a.get("href", "")
                if href.endswith(".pdf"):
                    pdf = base + href if href.startswith("/") else href
                    break
        records.append({
            "title": title,
            "year": year,
            "source": label,
            "authors": _format_authors(authors),
            "class": "",
            "keywords": "",
            "abstract": "",
            "pdf_link": pdf,
        })
    return records


def scrape_cvf(
    label: str, year: int, *, base: str = CVF_BASE, session: "requests.Session | None" = None
) -> list[dict]:
    """Fetch and parse the CVF listing for ``<label><year>``."""
    import requests

    sess = session or requests.Session()
    url = f"{base}/{label}{year}?day=all"
    resp = sess.get(url, headers={"User-Agent": "ai-trend/0.1"}, timeout=120)
    resp.raise_for_status()
    return parse_listing(resp.text, label, year, base=base)


def scrape_to_csv(label: str, year: int, out_path: Path | str, **kwargs) -> int:
    """Scrape CVF and write a source CSV; returns the row count."""
    import pandas as pd

    records = scrape_cvf(label, year, **kwargs)
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame(records, columns=RECORD_COLUMNS).to_csv(out_path, index=False)
    return len(records)
