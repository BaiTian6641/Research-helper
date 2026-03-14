"""Springer Nature API fetcher with pagination (requires API key)."""

from __future__ import annotations

import asyncio
import json
import os
from datetime import datetime

import httpx

from src.searcher.base import AbstractFetcher
from src.storage.models import Paper


class SpringerFetcher(AbstractFetcher):
    name = "springer"
    BASE_URL = "https://api.springernature.com/meta/v2/json"

    def __init__(self, timeout: int = 30):
        self._timeout = timeout
        self._api_key = os.environ.get("SPRINGER_API_KEY", "")

    async def search(
        self,
        query: str,
        max_results: int = 200,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[dict]:
        if not self._api_key:
            return []

        q = f'keyword:"{query}"'
        if year_start and year_end:
            q += f" AND onlinedatefrom:{year_start}-01-01 AND onlinedateto:{year_end}-12-31"
        elif year_start:
            q += f" AND onlinedatefrom:{year_start}-01-01"
        elif year_end:
            q += f" AND onlinedateto:{year_end}-12-31"

        results: list[dict] = []
        batch_size = 100  # Springer API max per page
        start = 1

        async with httpx.AsyncClient(timeout=self._timeout) as client:
            while len(results) < max_results:
                params = {
                    "q": q,
                    "s": start,
                    "p": min(batch_size, max_results - len(results)),
                    "api_key": self._api_key,
                }
                resp = await self._request_with_retry(
                    client, "GET", self.BASE_URL, params=params,
                )
                if resp.status_code == 429:
                    break
                resp.raise_for_status()
                data = resp.json()
                records = data.get("records", [])
                if not records:
                    break
                results.extend(records)
                start += len(records)
                # Check total
                total = int(
                    data.get("result", [{}])[0].get("total", 0)
                    if data.get("result")
                    else 0
                )
                if total and start > total:
                    break
                if len(records) < batch_size:
                    break
                await asyncio.sleep(1.0)

        return results[:max_results]

    def normalise(self, raw: dict) -> Paper:
        doi = raw.get("doi")
        title = raw.get("title", "")
        year = None
        pub_date = raw.get("publicationDate", "")
        if pub_date:
            try:
                year = int(pub_date[:4])
            except (ValueError, IndexError):
                pass

        paper_id = Paper.make_id(doi=doi, title=title, year=year)
        authors = [c.get("creator", "") for c in raw.get("creators", []) if c.get("creator")]
        abstract = raw.get("abstract", "")

        return Paper(
            id=paper_id,
            doi=doi,
            arxiv_id=None,
            pmid=None,
            title=title,
            authors=json.dumps(authors),
            year=year,
            venue=raw.get("publicationName"),
            venue_type="journal",
            abstract=abstract if abstract else None,
            keywords=json.dumps([]),
            citations=None,
            citation_velocity=None,
            influential_citations=None,
            sources=json.dumps(["springer"]),
            url=raw.get("url", [{}])[0].get("value") if isinstance(raw.get("url"), list) else None,
            fetched_at=datetime.utcnow(),
            is_local=False,
            peer_reviewed=True,
            confidence_tier="high",
        )
