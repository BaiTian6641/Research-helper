"""Nature / Nature Communications fetcher — API-first with web fallback.

Uses the Springer Nature API when SPRINGER_API_KEY is available.
Falls back to scraping nature.com search results when the API is
unavailable or returns errors.
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
from datetime import datetime

import httpx

from src.searcher.base import AbstractFetcher
from src.storage.models import Paper

logger = logging.getLogger(__name__)

# Nature-branded journal names for the Springer API ``journal:`` filter.
_NATURE_JOURNALS = [
    "Nature",
    "Nature Communications",
    "Nature Medicine",
    "Nature Biotechnology",
    "Nature Methods",
    "Nature Machine Intelligence",
]

# Journal slugs accepted by nature.com web search ``journal`` parameter.
_WEB_JOURNAL_SLUGS = "nature,ncomms,nm,nbt,nmeth,natmachintell"


class NatureFetcher(AbstractFetcher):
    """Fetcher for Nature-family journals (API-first, web fallback)."""

    name = "nature"
    API_URL = "https://api.springernature.com/meta/v2/json"
    WEB_URL = "https://www.nature.com/search"

    def __init__(self, timeout: int = 30):
        self._timeout = timeout
        self._api_key = os.environ.get("SPRINGER_API_KEY", "")

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
        # Try Springer Nature API first (requires key)
        if self._api_key:
            try:
                results = await self._search_api(
                    query, max_results, year_start, year_end,
                )
                if results:
                    return results
                logger.info(
                    "Nature API returned 0 results, falling back to web",
                )
            except Exception as exc:
                logger.warning(
                    "Nature API failed (%s), falling back to web", exc,
                )

        # Web-scraping fallback (no key needed)
        try:
            return await self._search_web(
                query, max_results, year_start, year_end,
            )
        except Exception as exc:
            logger.warning("Nature web scraping also failed: %s", exc)
            return []

    # ------------------------------------------------------------------
    # Springer Nature API path
    # ------------------------------------------------------------------

    async def _search_api(
        self,
        query: str,
        max_results: int,
        year_start: int | None,
        year_end: int | None,
    ) -> list[dict]:
        journal_clause = " OR ".join(
            f'journal:"{j}"' for j in _NATURE_JOURNALS
        )
        q = f'keyword:"{query}" AND ({journal_clause})'
        if year_start and year_end:
            q += (
                f" AND onlinedatefrom:{year_start}-01-01"
                f" AND onlinedateto:{year_end}-12-31"
            )
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
                    client, "GET", self.API_URL, params=params,
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

    # ------------------------------------------------------------------
    # Web-scraping fallback
    # ------------------------------------------------------------------

    async def _search_web(
        self,
        query: str,
        max_results: int,
        year_start: int | None,
        year_end: int | None,
    ) -> list[dict]:
        results: list[dict] = []
        pages_to_fetch = min((max_results + 49) // 50, 8)

        async with httpx.AsyncClient(
            timeout=self._timeout,
            follow_redirects=True,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/126.0.0.0 Safari/537.36"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9",
            },
        ) as client:
            for page in range(1, pages_to_fetch + 1):
                params: dict[str, str | int] = {
                    "q": query,
                    "journal": _WEB_JOURNAL_SLUGS,
                    "order": "relevance",
                    "page": page,
                }
                if year_start and year_end:
                    params["date_range"] = f"{year_start}-{year_end}"
                elif year_start:
                    params["date_range"] = f"{year_start}-2099"
                elif year_end:
                    params["date_range"] = f"1900-{year_end}"

                resp = await self._request_with_retry(
                    client, "GET", self.WEB_URL, params=params,
                )
                if resp.status_code != 200:
                    break
                batch = self._parse_web_results(resp.text)
                if not batch:
                    break
                results.extend(batch)
                if len(results) >= max_results:
                    break
                await asyncio.sleep(1.5)

        return results[:max_results]

    @staticmethod
    def _parse_web_results(html: str) -> list[dict]:
        """Extract article metadata from nature.com search HTML."""
        try:
            from bs4 import BeautifulSoup

            return NatureFetcher._parse_with_bs4(html)
        except ImportError:
            return NatureFetcher._parse_with_regex(html)

    @staticmethod
    def _parse_with_bs4(html: str) -> list[dict]:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html, "html.parser")
        results: list[dict] = []

        for article in soup.select("article"):
            title_el = article.select_one(
                "h3 a, h2 a, .c-card__title a, "
                "[data-test='title'] a, a[data-track-action='search result']"
            )
            if not title_el:
                continue
            title = title_el.get_text(strip=True)
            if not title or len(title) < 5:
                continue

            link = title_el.get("href", "")
            if link and not link.startswith("http"):
                link = f"https://www.nature.com{link}"

            doi = None
            doi_match = re.search(r"/(10\.\d{4,}/[^\s?#]+)", link)
            if doi_match:
                doi = doi_match.group(1)

            journal_el = article.select_one(
                "[data-test='journal-title'], .c-card__journal, "
                "[data-test='publication']"
            )
            journal = journal_el.get_text(strip=True) if journal_el else "Nature"

            date_el = article.select_one("time, [datetime]")
            pub_date = ""
            if date_el:
                pub_date = (
                    date_el.get("datetime", "")
                    or date_el.get_text(strip=True)
                )

            abstract_el = article.select_one(
                ".c-card__summary, p.c-card__summary, "
                "[data-test='summary']"
            )
            abstract = abstract_el.get_text(strip=True) if abstract_el else ""

            author_els = article.select(
                "[data-test='author-link'], .c-author-list__item, "
                "li[itemprop='author']"
            )
            authors = [a.get_text(strip=True) for a in author_els]

            results.append({
                "title": title,
                "doi": doi,
                "publicationName": journal,
                "publicationDate": pub_date,
                "abstract": abstract,
                "creators": [{"creator": a} for a in authors],
                "url": [{"value": link}] if link else [],
                "_source": "web",
            })

        return results

    @staticmethod
    def _parse_with_regex(html: str) -> list[dict]:
        """Minimal regex fallback when bs4 is unavailable."""
        results: list[dict] = []
        for m in re.finditer(
            r'<article[^>]*>.*?<a\s+[^>]*href="(/articles/[^"]+)"[^>]*>'
            r"(.*?)</a>",
            html,
            re.DOTALL | re.IGNORECASE,
        ):
            link_path, raw_title = m.group(1), m.group(2)
            title = re.sub(r"<[^>]+>", "", raw_title).strip()
            if not title or len(title) < 5:
                continue

            link = f"https://www.nature.com{link_path}"
            doi = None
            doi_m = re.search(r"/(10\.\d{4,}/[^\s?#\"]+)", link_path)
            if doi_m:
                doi = doi_m.group(1)

            results.append({
                "title": title,
                "doi": doi,
                "publicationName": "Nature",
                "publicationDate": "",
                "abstract": "",
                "creators": [],
                "url": [{"value": link}],
                "_source": "web",
            })

        return results

    # ------------------------------------------------------------------
    # Normalise (shared by both API and web paths)
    # ------------------------------------------------------------------

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
        authors = [
            c.get("creator", "")
            for c in raw.get("creators", [])
            if c.get("creator")
        ]
        abstract = raw.get("abstract", "")
        venue = raw.get("publicationName", "Nature")

        return Paper(
            id=paper_id,
            doi=doi,
            arxiv_id=None,
            pmid=None,
            title=title,
            authors=json.dumps(authors),
            year=year,
            venue=venue,
            venue_type="journal",
            abstract=abstract if abstract else None,
            keywords=json.dumps([]),
            citations=None,
            citation_velocity=None,
            influential_citations=None,
            sources=json.dumps(["nature"]),
            url=(
                raw.get("url", [{}])[0].get("value")
                if isinstance(raw.get("url"), list) and raw.get("url")
                else None
            ),
            fetched_at=datetime.utcnow(),
            is_local=False,
            peer_reviewed=True,
            confidence_tier="high",
        )
