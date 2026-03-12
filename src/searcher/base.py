"""Abstract base class for all API fetchers."""

from __future__ import annotations

import abc
from datetime import datetime

from src.storage.models import Paper


class AbstractFetcher(abc.ABC):
    """Every source fetcher must implement search() and normalise()."""

    name: str = "base"

    @abc.abstractmethod
    async def search(
        self,
        query: str,
        max_results: int = 200,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[dict]:
        """Return raw API results as list of dicts."""
        ...

    @abc.abstractmethod
    def normalise(self, raw: dict) -> Paper:
        """Convert a single raw API result dict into a Paper object."""
        ...

    async def fetch_and_normalise(
        self,
        query: str,
        max_results: int = 200,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[Paper]:
        """Run search + normalise. Convenience wrapper."""
        raw_results = await self.search(query, max_results, year_start, year_end)
        papers: list[Paper] = []
        for raw in raw_results:
            try:
                paper = self.normalise(raw)
                papers.append(paper)
            except Exception:
                continue  # skip malformed records
        return papers
