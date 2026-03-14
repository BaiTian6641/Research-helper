"""Search orchestrator — runs fetchers in parallel and deduplicates results.

Two-phase strategy to maximise paper yield:
 1. **Full-range fetch** — every fetcher gets the entire year range with the
    full ``max_results_per_source`` limit.  This is the primary collection
    phase (most APIs already support native date-range filtering).
 2. **Year-balanced supplement** — for academic fetchers, run per-year
    queries (capped at a modest ``supplement_per_year``) to backfill years
    that may be under-represented in the relevance-sorted first pass.

News fetchers always query once (RSS feeds are date-agnostic).
Priority keywords trigger additional focused queries on the first two
academic fetchers.
"""

from __future__ import annotations

import asyncio
import json
import logging
import math
import re
from typing import AsyncIterator, Callable

from rapidfuzz import fuzz

from src.searcher.base import AbstractFetcher
from src.searcher.arxiv import ArxivFetcher
from src.searcher.semantic_scholar import SemanticScholarFetcher
from src.searcher.openalex import OpenAlexFetcher
from src.searcher.pubmed import PubMedFetcher
from src.searcher.crossref import CrossrefFetcher
from src.searcher.springer import SpringerFetcher
from src.searcher.nature import NatureFetcher
from src.searcher.ieee import IEEEFetcher
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
    "springer": SpringerFetcher,
    "nature": NatureFetcher,
    "ieee": IEEEFetcher,
    "google_news": GoogleNewsFetcher,
    "bing_news": BingNewsFetcher,
}

# News/web fetchers don't benefit from per-year iteration
NEWS_FETCHERS = {"google_news", "bing_news"}


class SearchOrchestrator:
    def __init__(
        self,
        sources: list[str] | None = None,
        max_results_per_source: int = 200,
        timeout: int = 30,
        title_similarity_threshold: float = 0.92,
        priority_keywords: list[str] | None = None,
    ):
        self._source_names = sources or list(FETCHER_MAP.keys())
        self._max_results = max_results_per_source
        self._timeout = timeout
        self._sim_threshold = title_similarity_threshold
        self._priority_keywords = [kw.strip().lower() for kw in (priority_keywords or []) if kw.strip()]

    async def search(
        self,
        query: str,
        year_start: int | None = None,
        year_end: int | None = None,
        progress_callback: Callable[[str, int], None] | None = None,
    ) -> list[Paper]:
        """Run all fetchers concurrently, deduplicate, return merged papers.

        Phase 1: full-range fetch with the entire ``max_results`` per fetcher.
        Phase 2: year-balanced supplement for academic fetchers to ensure
                 underrepresented years are covered.
        Phase 3: priority keyword boost queries.
        """
        fetchers = self._build_fetchers()
        all_papers: list[Paper] = []

        # ── Phase 1: full-range fetch ──
        tasks = []
        for fetcher in fetchers:
            tasks.append(
                self._fetch_one(fetcher, query, year_start, year_end, progress_callback)
            )

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

        # ── Phase 2: year-balanced supplement ──
        # Only for academic fetchers when a year range is given and wide enough.
        if year_start and year_end and (year_end - year_start) >= 3:
            academic_fetchers = [
                f for f in fetchers if f.name not in NEWS_FETCHERS
            ]
            if academic_fetchers:
                if progress_callback:
                    progress_callback("Supplementing year coverage...", 0)
                supplement_tasks = []
                for fetcher in academic_fetchers:
                    supplement_tasks.append(
                        self._supplement_years(
                            fetcher, query, year_start, year_end,
                            all_papers, progress_callback,
                        )
                    )
                supp_results = await asyncio.gather(
                    *supplement_tasks, return_exceptions=True,
                )
                for sr in supp_results:
                    if not isinstance(sr, Exception):
                        all_papers.extend(sr)

        # ── Phase 3: priority keyword boost ──
        if self._priority_keywords:
            academic_fetchers = [f for f in fetchers if f.name not in NEWS_FETCHERS][:2]
            if academic_fetchers and progress_callback:
                progress_callback("Boosting priority keywords...", 0)
            boost_tasks = []
            for kw in self._priority_keywords:
                for fetcher in academic_fetchers:
                    boost_tasks.append(
                        self._fetch_one(fetcher, kw, year_start, year_end, None)
                    )
            if boost_tasks:
                boost_results = await asyncio.gather(*boost_tasks, return_exceptions=True)
                for br in boost_results:
                    if not isinstance(br, Exception):
                        all_papers.extend(br)

        # Deduplicate
        deduped = self._deduplicate(all_papers)

        # Tag papers that match priority keywords
        if self._priority_keywords:
            _tag_priority_matches(deduped, self._priority_keywords)

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

    async def _supplement_years(
        self,
        fetcher: AbstractFetcher,
        query: str,
        year_start: int,
        year_end: int,
        existing_papers: list[Paper],
        progress_callback: Callable[[str, int], None] | None,
    ) -> list[Paper]:
        """Fill in years that are under-represented in the full-range fetch.

        Counts existing papers per year, then queries individual gap years
        to ensure balanced temporal coverage.
        """
        year_counts: dict[int, int] = {}
        for p in existing_papers:
            if p.year:
                year_counts[p.year] = year_counts.get(p.year, 0) + 1

        num_years = year_end - year_start + 1
        avg = max(len(existing_papers) // max(num_years, 1), 1)
        gap_threshold = max(avg // 3, 3)

        gap_years = [
            y for y in range(year_start, year_end + 1)
            if year_counts.get(y, 0) < gap_threshold
        ]
        if not gap_years:
            return []

        if progress_callback:
            progress_callback(
                f"{fetcher.name}: filling {len(gap_years)} gap years...", 0,
            )

        supplement_per_year = 30
        all_papers: list[Paper] = []

        for idx, year in enumerate(gap_years):
            if idx > 0:
                await asyncio.sleep(1.5)
            try:
                batch = await fetcher.fetch_and_normalise(
                    query, supplement_per_year, year, year,
                )
                all_papers.extend(batch)
                if progress_callback:
                    progress_callback(
                        f"{fetcher.name}: supplement {year} (+{len(batch)})",
                        len(batch),
                    )
            except Exception as e:
                logger.warning(
                    "Fetcher %s supplement year %d failed: %s",
                    fetcher.name, year, e,
                )

        logger.info(
            "Fetcher %s supplement: %d papers for %d gap years",
            fetcher.name, len(all_papers), len(gap_years),
        )
        return all_papers

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

        # Merge quality flags — prefer higher-confidence values
        if source.peer_reviewed and not target.peer_reviewed:
            target.peer_reviewed = True
        _TIER_RANK = {"high": 3, "medium": 2, "low": 1}
        src_rank = _TIER_RANK.get(source.confidence_tier or "", 0)
        tgt_rank = _TIER_RANK.get(target.confidence_tier or "", 0)
        if src_rank > tgt_rank:
            target.confidence_tier = source.confidence_tier


def _tag_priority_matches(papers: list[Paper], priority_keywords: list[str]) -> None:
    """Mark papers whose title/abstract matches a priority keyword.

    Stores the result in paper.keywords JSON list (appends a
    ``__priority__`` tag) so downstream analytics can detect it cheaply.
    """
    if not priority_keywords:
        return
    patterns = [re.compile(re.escape(kw), re.IGNORECASE) for kw in priority_keywords]
    for p in papers:
        text = f"{p.title or ''} {p.abstract or ''}"
        if any(pat.search(text) for pat in patterns):
            kws = json.loads(p.keywords or "[]")
            if "__priority__" not in kws:
                kws.append("__priority__")
                p.keywords = json.dumps(kws)
