"""RIS parser — converts .ris text to Paper objects."""

from __future__ import annotations

import re
from typing import List

from src.storage.models import Paper

# Key RIS tags we care about
_TAG = re.compile(r"^([A-Z][A-Z0-9])\s{1,2}-\s(.*)$")


def parse_ris(text: str) -> List[Paper]:
    """Parse RIS entries into Paper objects."""
    papers: list[Paper] = []
    records = _split_records(text)

    for rec in records:
        title = rec.get("TI") or rec.get("T1") or ""
        if not title:
            continue

        year_str = (rec.get("PY") or rec.get("DA") or "")[:4]
        year = int(year_str) if year_str.isdigit() else None
        authors = rec.get("AU", []) if isinstance(rec.get("AU"), list) else []
        doi = rec.get("DO") or rec.get("DOI") or ""
        abstract = rec.get("AB") or rec.get("N2") or ""
        venue = rec.get("JO") or rec.get("JF") or rec.get("T2") or ""
        url = rec.get("UR") or ""

        paper = Paper(
            id=Paper.make_id(doi=doi or None, title=title, year=year),
            title=title.strip(),
            year=year,
            venue=venue.strip() or None,
            abstract=abstract.strip() or None,
            doi=doi.strip() or None,
            url=url.strip() or None,
        )
        paper.set_authors(authors)
        paper.set_sources(["local_ris"])
        papers.append(paper)

    return papers


def _split_records(text: str) -> list[dict]:
    """Split a RIS file into a list of field dicts."""
    records: list[dict] = []
    current: dict = {}
    multi_authors: list[str] = []

    for line in text.splitlines():
        m = _TAG.match(line)
        if m:
            tag, value = m.group(1), m.group(2).strip()
            if tag == "ER":
                # End of record
                if multi_authors:
                    current["AU"] = multi_authors
                if current:
                    records.append(current)
                current = {}
                multi_authors = []
            elif tag == "AU" or tag == "A1":
                multi_authors.append(value)
            else:
                current[tag] = value

    # Handle file ending without ER
    if current:
        if multi_authors:
            current["AU"] = multi_authors
        records.append(current)

    return records
