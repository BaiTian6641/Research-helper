"""CSV export — writes papers to CSV matching the schema in requirements.md."""

from __future__ import annotations

import csv
import io
from pathlib import Path

from src.storage.models import Paper


CSV_COLUMNS = [
    "id", "doi", "arxiv_id", "pmid",
    "title", "authors", "year", "venue", "venue_type",
    "abstract", "keywords",
    "citations", "citation_velocity", "influential_citations",
    "sources", "url", "fetched_at", "is_local",
    "themes", "motivation_sentences", "confidence_label",
    "industry_affiliated", "funder_names",
]


def export_papers_to_csv(papers: list[Paper], path: str | Path) -> Path:
    """Write papers to a CSV file. Returns the path written."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        for paper in papers:
            row = paper.to_dict()
            # Flatten list fields to semicolon-separated strings
            for key in ("authors", "keywords", "sources", "themes",
                        "motivation_sentences", "funder_names"):
                val = row.get(key)
                if isinstance(val, list):
                    row[key] = "; ".join(str(v) for v in val)
            writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
    return path


def papers_to_csv_string(papers: list[Paper]) -> str:
    """Return CSV as a string (for download in the UI)."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_COLUMNS)
    writer.writeheader()
    for paper in papers:
        row = paper.to_dict()
        for key in ("authors", "keywords", "sources", "themes",
                     "motivation_sentences", "funder_names"):
            val = row.get(key)
            if isinstance(val, list):
                row[key] = "; ".join(str(v) for v in val)
        writer.writerow({k: row.get(k, "") for k in CSV_COLUMNS})
    return buf.getvalue()
