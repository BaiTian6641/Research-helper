"""Ingestion service — unified entry point for local file parsing."""

from __future__ import annotations

from typing import List

from src.storage.models import Paper


class IngestionService:
    """Parses uploaded text (BibTeX, RIS, CSV) into Paper objects."""

    _PARSERS = {
        "bib": "_parse_bibtex",
        "ris": "_parse_ris",
        "csv": "_parse_csv",
    }

    def parse_text(self, text: str, fmt: str) -> List[Paper]:
        """Parse raw text in the given format and return Paper objects."""
        method_name = self._PARSERS.get(fmt)
        if method_name is None:
            return []
        return getattr(self, method_name)(text)

    @staticmethod
    def _parse_bibtex(text: str) -> List[Paper]:
        from src.ingestion.bibtex_parser import parse_bibtex
        return parse_bibtex(text)

    @staticmethod
    def _parse_ris(text: str) -> List[Paper]:
        from src.ingestion.ris_parser import parse_ris
        return parse_ris(text)

    @staticmethod
    def _parse_csv(text: str) -> List[Paper]:
        from src.ingestion.csv_parser import parse_csv
        return parse_csv(text)
