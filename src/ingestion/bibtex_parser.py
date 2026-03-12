"""BibTeX parser — converts .bib text to Paper objects."""

from __future__ import annotations

import re
from typing import List

from src.storage.models import Paper


def parse_bibtex(text: str) -> List[Paper]:
    """Parse BibTeX entries into Paper objects."""
    papers: list[Paper] = []
    entries = re.split(r"@\w+\s*\{", text)

    for entry in entries[1:]:  # skip text before first @
        fields = _extract_fields(entry)
        if not fields.get("title"):
            continue

        title = _clean(fields.get("title", ""))
        year_str = fields.get("year", "")
        year = int(year_str) if year_str.isdigit() else None
        authors_raw = fields.get("author", "")
        authors = _parse_authors(authors_raw)
        doi = fields.get("doi", "")
        abstract = _clean(fields.get("abstract", ""))
        venue = _clean(
            fields.get("journal", "")
            or fields.get("booktitle", "")
            or fields.get("publisher", "")
        )
        url = fields.get("url", "")

        paper = Paper(
            id=Paper.make_id(doi=doi or None, title=title, year=year),
            title=title,
            year=year,
            venue=venue or None,
            abstract=abstract or None,
            doi=doi or None,
            url=url or None,
        )
        paper.set_authors(authors)
        paper.set_sources(["local_bibtex"])
        papers.append(paper)

    return papers


def _extract_fields(entry_body: str) -> dict[str, str]:
    """Extract key=value pairs from a BibTeX entry body."""
    fields: dict[str, str] = {}
    # Match key = {value} or key = "value" or key = number
    for m in re.finditer(
        r"(\w+)\s*=\s*(?:\{([^}]*)\}|\"([^\"]*)\"|(\d+))", entry_body, re.DOTALL
    ):
        key = m.group(1).lower()
        val = m.group(2) or m.group(3) or m.group(4) or ""
        fields[key] = val.strip()
    return fields


def _parse_authors(raw: str) -> list[str]:
    """Split 'Last, First and Last, First' into a list."""
    if not raw:
        return []
    parts = re.split(r"\s+and\s+", raw)
    return [_clean(a) for a in parts if a.strip()]


def _clean(text: str) -> str:
    """Remove BibTeX braces and excess whitespace."""
    text = text.replace("{", "").replace("}", "")
    return re.sub(r"\s+", " ", text).strip()
