"""arXiv API fetcher — uses Atom XML feed."""

from __future__ import annotations

import json
from datetime import datetime
from urllib.parse import quote

import feedparser
import httpx

from src.searcher.base import AbstractFetcher
from src.storage.models import Paper


class ArxivFetcher(AbstractFetcher):
    name = "arxiv"
    BASE_URL = "https://export.arxiv.org/api/query"

    def __init__(self, timeout: int = 30):
        self._timeout = timeout

    async def search(
        self,
        query: str,
        max_results: int = 200,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[dict]:
        search_query = f"all:{quote(query)}"
        params = {
            "search_query": search_query,
            "start": 0,
            "max_results": min(max_results, 2000),
            "sortBy": "relevance",
            "sortOrder": "descending",
        }
        async with httpx.AsyncClient(timeout=self._timeout, follow_redirects=True) as client:
            resp = await client.get(self.BASE_URL, params=params)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        results: list[dict] = []
        for entry in feed.entries:
            year = None
            if hasattr(entry, "published"):
                try:
                    year = int(entry.published[:4])
                except (ValueError, TypeError):
                    pass
            if year_start and year and year < year_start:
                continue
            if year_end and year and year > year_end:
                continue
            results.append({
                "title": entry.get("title", "").replace("\n", " ").strip(),
                "authors": [a.get("name", "") for a in entry.get("authors", [])],
                "year": year,
                "abstract": entry.get("summary", "").replace("\n", " ").strip(),
                "url": entry.get("link", ""),
                "arxiv_id": entry.get("id", "").split("/abs/")[-1] if "/abs/" in entry.get("id", "") else entry.get("id", ""),
                "categories": [t.get("term", "") for t in entry.get("tags", [])],
                "published": entry.get("published", ""),
            })
        return results

    def normalise(self, raw: dict) -> Paper:
        paper_id = Paper.make_id(title=raw.get("title", ""), year=raw.get("year"))
        return Paper(
            id=paper_id,
            doi=None,
            arxiv_id=raw.get("arxiv_id"),
            pmid=None,
            title=raw.get("title", ""),
            authors=json.dumps(raw.get("authors", [])),
            year=raw.get("year"),
            venue="arXiv",
            venue_type="preprint",
            abstract=raw.get("abstract"),
            keywords=json.dumps(raw.get("categories", [])),
            citations=None,
            citation_velocity=None,
            influential_citations=None,
            sources=json.dumps(["arxiv"]),
            url=raw.get("url"),
            fetched_at=datetime.utcnow(),
            is_local=False,
        )
