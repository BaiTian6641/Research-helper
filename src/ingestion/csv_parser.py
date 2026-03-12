"""CSV parser — converts .csv text to Paper objects.

Expects a header row with at least 'title'. Other recognised columns:
authors, year, doi, abstract, venue, url, citations, keywords.
"""

from __future__ import annotations

import csv
import io
from typing import List

from src.storage.models import Paper


_TITLE_ALIASES = {"title", "paper_title", "paper title", "name"}
_AUTHOR_ALIASES = {"authors", "author", "author(s)"}
_YEAR_ALIASES = {"year", "publication_year", "pub_year"}
_DOI_ALIASES = {"doi"}
_ABSTRACT_ALIASES = {"abstract", "summary"}
_VENUE_ALIASES = {"venue", "journal", "source", "booktitle"}
_URL_ALIASES = {"url", "link"}
_CITATION_ALIASES = {"citations", "citation_count", "cited_by"}


def parse_csv(text: str) -> List[Paper]:
    """Parse CSV text into Paper objects."""
    reader = csv.DictReader(io.StringIO(text))
    if reader.fieldnames is None:
        return []

    col_map = _build_column_map(reader.fieldnames)
    if "title" not in col_map:
        return []

    papers: list[Paper] = []
    for row in reader:
        title = row.get(col_map["title"], "").strip()
        if not title:
            continue

        year_str = row.get(col_map.get("year", ""), "").strip()
        year = int(year_str) if year_str.isdigit() else None
        doi = row.get(col_map.get("doi", ""), "").strip() or None
        abstract = row.get(col_map.get("abstract", ""), "").strip() or None
        venue = row.get(col_map.get("venue", ""), "").strip() or None
        url = row.get(col_map.get("url", ""), "").strip() or None
        authors_raw = row.get(col_map.get("authors", ""), "").strip()
        authors = [a.strip() for a in authors_raw.split(";") if a.strip()] if authors_raw else []
        cit_str = row.get(col_map.get("citations", ""), "").strip()
        citations = int(cit_str) if cit_str.isdigit() else None

        paper = Paper(
            id=Paper.make_id(doi=doi, title=title, year=year),
            title=title,
            year=year,
            venue=venue,
            abstract=abstract,
            doi=doi,
            url=url,
            citations=citations,
        )
        paper.set_authors(authors)
        paper.set_sources(["local_csv"])
        papers.append(paper)

    return papers


def _build_column_map(fieldnames: list[str]) -> dict[str, str]:
    """Map our canonical field names to actual CSV column names."""
    lower_map = {f.lower().strip(): f for f in fieldnames}
    result: dict[str, str] = {}

    for canon, aliases in [
        ("title", _TITLE_ALIASES),
        ("authors", _AUTHOR_ALIASES),
        ("year", _YEAR_ALIASES),
        ("doi", _DOI_ALIASES),
        ("abstract", _ABSTRACT_ALIASES),
        ("venue", _VENUE_ALIASES),
        ("url", _URL_ALIASES),
        ("citations", _CITATION_ALIASES),
    ]:
        for alias in aliases:
            if alias in lower_map:
                result[canon] = lower_map[alias]
                break
    return result
