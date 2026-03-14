"""Semantic Scholar API fetcher.

Uses three strategies in order:
1. **Bulk API** (``/graph/v1/paper/search/bulk``) — works without an API key,
   returns up to 1 000 results per request with a continuation token.
2. **Standard API** (``/graph/v1/paper/search``) — requires ``S2_API_KEY``
   env-var for reliable access (free tier available at
   https://www.semanticscholar.org/product/api).
3. If both fail the fetcher returns an empty list (web scraping no longer
   works because S2 uses client-side rendering exclusively).
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
from datetime import datetime

import httpx

from src.searcher.base import AbstractFetcher
from src.storage.models import Paper

logger = logging.getLogger(__name__)


class SemanticScholarFetcher(AbstractFetcher):
    name = "semantic_scholar"
    BASE_URL = "https://api.semanticscholar.org/graph/v1/paper/search"
    BULK_URL = "https://api.semanticscholar.org/graph/v1/paper/search/bulk"
    FIELDS = (
        "paperId,externalIds,title,authors,year,venue,abstract,"
        "citationCount,influentialCitationCount,url"
    )

    def __init__(self, timeout: int = 30):
        self._timeout = timeout
        self._api_key = os.environ.get("S2_API_KEY", "")

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    async def search(
        self,
        query: str,
        max_results: int = 200,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[dict]:
        # Strategy 1: Bulk API (no key required, 1000/page)
        try:
            results = await self._search_bulk(
                query, max_results, year_start, year_end,
            )
            if results:
                return results
            logger.info("S2 bulk API returned 0 results, trying standard API")
        except Exception as exc:
            logger.warning("S2 bulk API failed (%s), trying standard API", exc)

        # Strategy 2: Standard API (needs API key for reliable access)
        try:
            results = await self._search_api(
                query, max_results, year_start, year_end,
            )
            if results:
                return results
        except Exception as exc:
            logger.warning("S2 standard API also failed: %s", exc)

        return []

    # ------------------------------------------------------------------
    # Bulk API path (no API key needed)
    # ------------------------------------------------------------------

    async def _search_bulk(
        self,
        query: str,
        max_results: int,
        year_start: int | None,
        year_end: int | None,
    ) -> list[dict]:
        results: list[dict] = []
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        async with httpx.AsyncClient(
            timeout=self._timeout, headers=headers,
        ) as client:
            token: str | None = None
            while len(results) < max_results:
                params: dict[str, str] = {
                    "query": query,
                    "fields": self.FIELDS,
                }
                if year_start and year_end:
                    params["year"] = f"{year_start}-{year_end}"
                elif year_start:
                    params["year"] = f"{year_start}-"
                elif year_end:
                    params["year"] = f"-{year_end}"
                if token:
                    params["token"] = token

                resp = await self._request_with_retry(
                    client, "GET", self.BULK_URL, params=params,
                )
                if resp.status_code == 429:
                    logger.warning("S2 bulk API rate-limited after retries")
                    break
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("data", [])
                if not batch:
                    break
                results.extend(batch)
                token = data.get("token")
                if not token:
                    break  # no more pages
                # Delay between pages to stay within rate limits
                await asyncio.sleep(1.5)

        return results[:max_results]

    # ------------------------------------------------------------------
    # Standard API path (higher precision, but needs API key)
    # ------------------------------------------------------------------

    async def _search_api(
        self,
        query: str,
        max_results: int,
        year_start: int | None,
        year_end: int | None,
    ) -> list[dict]:
        results: list[dict] = []
        offset = 0
        batch_size = min(max_results, 100)
        headers: dict[str, str] = {}
        if self._api_key:
            headers["x-api-key"] = self._api_key

        async with httpx.AsyncClient(
            timeout=self._timeout, headers=headers,
        ) as client:
            while len(results) < max_results:
                params: dict[str, str | int] = {
                    "query": query,
                    "offset": offset,
                    "limit": batch_size,
                    "fields": self.FIELDS,
                }
                if year_start and year_end:
                    params["year"] = f"{year_start}-{year_end}"
                elif year_start:
                    params["year"] = f"{year_start}-"
                elif year_end:
                    params["year"] = f"-{year_end}"

                resp = await self._request_with_retry(
                    client, "GET", self.BASE_URL, params=params,
                )
                if resp.status_code == 429:
                    break
                resp.raise_for_status()
                data = resp.json()
                batch = data.get("data", [])
                if not batch:
                    break
                results.extend(batch)
                offset += len(batch)
                if offset >= data.get("total", 0):
                    break
                await asyncio.sleep(1.0)

        return results[:max_results]

    # ------------------------------------------------------------------
    # Normalise (shared by both API and web paths)
    # ------------------------------------------------------------------

    def normalise(self, raw: dict) -> Paper:
        ext_ids = raw.get("externalIds") or {}
        doi = ext_ids.get("DOI")
        arxiv_id = ext_ids.get("ArXiv")
        pmid = ext_ids.get("PubMed")

        paper_id = Paper.make_id(doi=doi, title=raw.get("title", ""), year=raw.get("year"))

        authors = [a.get("name", "") for a in raw.get("authors", []) if a.get("name")]

        return Paper(
            id=paper_id,
            doi=doi,
            arxiv_id=arxiv_id,
            pmid=pmid,
            title=raw.get("title", ""),
            authors=json.dumps(authors),
            year=raw.get("year"),
            venue=raw.get("venue") or None,
            venue_type=None,
            abstract=raw.get("abstract"),
            keywords=json.dumps([]),
            citations=raw.get("citationCount"),
            citation_velocity=None,
            influential_citations=raw.get("influentialCitationCount"),
            sources=json.dumps(["semantic_scholar"]),
            url=raw.get("url"),
            fetched_at=datetime.utcnow(),
            is_local=False,
            peer_reviewed=bool(raw.get("venue")),
            confidence_tier="high" if raw.get("venue") else "medium",
        )
