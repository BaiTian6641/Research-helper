"""Search orchestrator — runs fetchers in parallel and deduplicates results."""

from __future__ import annotations

import asyncio
import json
import logging
from typing import AsyncIterator, Callable

from rapidfuzz import fuzz

from src.searcher.base import AbstractFetcher
from src.searcher.arxiv import ArxivFetcher
from src.searcher.semantic_scholar import SemanticScholarFetcher
from src.searcher.openalex import OpenAlexFetcher
from src.searcher.pubmed import PubMedFetcher
from src.searcher.crossref import CrossrefFetcher
from src.searcher.news_google import GoogleNewsFetcher
from src.searcher.news_bing import BingNewsFetcher
from src.storage.models import Paper

logger = logging.getLogger(__name__)

FETCHER_MAP: dict[str, type[AbstractFetcher]] = {
    "arxiv": ArxivFetcher,
    "semantic_scholar": SemanticScholarFetcher,
    "openalex": OpenAlexFetcher,
    "pubmed": PubMedFetcher,
    "crossref": CrossrefFetcher,
    "google_news": GoogleNewsFetcher,
    "bing_news": BingNewsFetcher,
}


class SearchOrchestrator:
    def __init__(
        self,
        sources: list[str] | None = None,
        max_results_per_source: int = 200,
        timeout: int = 30,
        title_similarity_threshold: float = 0.92,
    ):
        self._source_names = sources or list(FETCHER_MAP.keys())
        self._max_results = max_results_per_source
        self._timeout = timeout
        self._sim_threshold = title_similarity_threshold

    async def search(
        self,
        query: str,
        year_start: int | None = None,
        year_end: int | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> list[Paper]:
        """Run all fetchers concurrently, deduplicate, return merged papers."""
        fetchers = self._build_fetchers()
        all_papers: list[Paper] = []

        tasks = [
            self._fetch_one(fetcher, query, year_start, year_end, progress_callback)
            for fetcher in fetchers
        ]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        for fetcher, result in zip(fetchers, results):
            if isinstance(result, Exception):
                logger.warning("Fetcher %s failed: %s", fetcher.name, result)
                if progress_callback:
                    progress_callback(f"{fetcher.name}: error", 0)
            else:
                all_papers.extend(result)
                if progress_callback:
                    progress_callback(f"{fetcher.name}: done", len(result))

        # Deduplicate
        deduped = self._deduplicate(all_papers)
        logger.info(
            "Orchestrator: %d raw → %d deduped", len(all_papers), len(deduped)
        )
        return deduped

    def _build_fetchers(self) -> list[AbstractFetcher]:
        fetchers: list[AbstractFetcher] = []
        for name in self._source_names:
            cls = FETCHER_MAP.get(name)
            if cls:
                fetchers.append(cls(timeout=self._timeout))
        return fetchers

    async def _fetch_one(
        self,
        fetcher: AbstractFetcher,
        query: str,
        year_start: int | None,
        year_end: int | None,
        progress_callback: Callable[[str, int], None] | None,
    ) -> list[Paper]:
        if progress_callback:
            progress_callback(f"{fetcher.name}: searching...", 0)
        return await fetcher.fetch_and_normalise(
            query, self._max_results, year_start, year_end
        )

    def _deduplicate(self, papers: list[Paper]) -> list[Paper]:
        """Remove duplicates using DOI match then fuzzy title matching."""
        seen_dois: dict[str, Paper] = {}
        seen_arxiv: dict[str, Paper] = {}
        unique: list[Paper] = []

        for paper in papers:
            # 1. Exact DOI match
            if paper.doi:
                doi_key = paper.doi.lower().strip()
                if doi_key in seen_dois:
                    self._merge_paper(seen_dois[doi_key], paper)
                    continue
                seen_dois[doi_key] = paper

            # 2. arXiv ID match
            if paper.arxiv_id:
                aid = paper.arxiv_id.strip()
                if aid in seen_arxiv:
                    self._merge_paper(seen_arxiv[aid], paper)
                    continue
                seen_arxiv[aid] = paper

            # 3. Fuzzy title + year match
            is_dup = False
            for existing in unique:
                if paper.year and existing.year and paper.year != existing.year:
                    continue
                ratio = fuzz.ratio(
                    paper.title.lower().strip(),
                    existing.title.lower().strip(),
                ) / 100.0
                if ratio >= self._sim_threshold:
                    self._merge_paper(existing, paper)
                    is_dup = True
                    break

            if not is_dup:
                unique.append(paper)

        return unique

    @staticmethod
    def _merge_paper(target: Paper, source: Paper) -> None:
        """Merge richer data from source into target."""
        if source.abstract and not target.abstract:
            target.abstract = source.abstract
        if source.doi and not target.doi:
            target.doi = source.doi
        if source.arxiv_id and not target.arxiv_id:
            target.arxiv_id = source.arxiv_id
        if source.pmid and not target.pmid:
            target.pmid = source.pmid
        if source.citations is not None:
            if target.citations is None or source.citations > target.citations:
                target.citations = source.citations
        if source.influential_citations is not None and target.influential_citations is None:
            target.influential_citations = source.influential_citations
        if source.funder_names and not target.funder_names:
            target.funder_names = source.funder_names

        # Merge source lists
        t_src = set(json.loads(target.sources or "[]"))
        s_src = set(json.loads(source.sources or "[]"))
        target.sources = json.dumps(sorted(t_src | s_src))
