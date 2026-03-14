"""Google News RSS fetcher — free, no API key required."""

from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import quote

import feedparser
import httpx

from src.searcher.base import AbstractFetcher
from src.storage.models import Paper


class GoogleNewsFetcher(AbstractFetcher):
    name = "google_news"
    BASE_URL = "https://news.google.com/rss/search"

    def __init__(self, timeout: int = 30):
        self._timeout = timeout

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[dict]:
        params = {"q": query, "hl": "en", "gl": "US", "ceid": "US:en"}
        async with httpx.AsyncClient(
            timeout=self._timeout, follow_redirects=True
        ) as client:
            resp = await client.get(self.BASE_URL, params=params)
            resp.raise_for_status()

        feed = feedparser.parse(resp.text)
        results: list[dict] = []

        for entry in feed.entries[:max_results]:
            year = None
            pub_date = entry.get("published", "")
            if pub_date:
                try:
                    from email.utils import parsedate_to_datetime
                    dt = parsedate_to_datetime(pub_date)
                    year = dt.year
                except Exception:
                    # Try extracting year from date string
                    m = re.search(r"(\d{4})", pub_date)
                    if m:
                        year = int(m.group(1))

            if year_start and year and year < year_start:
                continue
            if year_end and year and year > year_end:
                continue

            # Google News titles often include " - SourceName" at the end
            raw_title = entry.get("title", "")
            source_name = ""
            if " - " in raw_title:
                parts = raw_title.rsplit(" - ", 1)
                raw_title = parts[0].strip()
                source_name = parts[1].strip() if len(parts) > 1 else ""

            results.append({
                "title": raw_title,
                "source_name": source_name,
                "year": year,
                "published": pub_date,
                "url": entry.get("link", ""),
                "summary": entry.get("summary", ""),
            })
        return results

    def normalise(self, raw: dict) -> Paper:
        paper_id = Paper.make_id(title=raw.get("title", ""), year=raw.get("year"))
        return Paper(
            id=paper_id,
            title=raw.get("title", ""),
            authors=json.dumps([raw.get("source_name", "")]) if raw.get("source_name") else "[]",
            year=raw.get("year"),
            venue=raw.get("source_name", "News"),
            venue_type="news",
            abstract=raw.get("summary", ""),
            sources=json.dumps(["google_news"]),
            url=raw.get("url", ""),
            peer_reviewed=False,
            confidence_tier="low",
        )
