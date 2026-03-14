"""Bing News Search via RSS — free, no API key required."""

from __future__ import annotations

import json
import re
from datetime import datetime
from urllib.parse import quote

import feedparser
import httpx

from src.searcher.base import AbstractFetcher
from src.storage.models import Paper


class BingNewsFetcher(AbstractFetcher):
    name = "bing_news"
    BASE_URL = "https://www.bing.com/news/search"

    def __init__(self, timeout: int = 30):
        self._timeout = timeout

    async def search(
        self,
        query: str,
        max_results: int = 100,
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> list[dict]:
        params = {"q": query, "format": "rss", "count": str(min(max_results, 100))}
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; ResearchTool/1.0)"
        }
        async with httpx.AsyncClient(
            timeout=self._timeout, follow_redirects=True
        ) as client:
            resp = await client.get(self.BASE_URL, params=params, headers=headers)
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
                    m = re.search(r"(\d{4})", pub_date)
                    if m:
                        year = int(m.group(1))

            if year_start and year and year < year_start:
                continue
            if year_end and year and year > year_end:
                continue

            results.append({
                "title": entry.get("title", "").strip(),
                "source_name": entry.get("source", {}).get("title", "News") if isinstance(entry.get("source"), dict) else "News",
                "year": year,
                "published": pub_date,
                "url": entry.get("link", ""),
                "summary": _strip_html(entry.get("summary", "")),
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
            sources=json.dumps(["bing_news"]),
            url=raw.get("url", ""),
            peer_reviewed=False,
            confidence_tier="low",
        )


def _strip_html(text: str) -> str:
    """Remove HTML tags from text."""
    return re.sub(r"<[^>]+>", "", text).strip()
