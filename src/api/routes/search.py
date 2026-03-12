"""POST /api/v1/search — full search + analytics pipeline."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from src.api import schemas
import src.api.main as _main
from src.config.settings import get_settings
from src.searcher.orchestrator import SearchOrchestrator
from src.storage.models import FieldStats

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/search", response_model=schemas.SearchResponse)
async def search(req: schemas.SearchRequest):
    """Run a full search across academic databases, then analyse."""
    store = _main.store
    pipeline = _main.pipeline
    if store is None or pipeline is None:
        raise HTTPException(503, "Service not ready")

    settings = get_settings()

    # 1. Search academic sources
    orchestrator = SearchOrchestrator(
        sources=req.sources,
        max_results_per_source=req.max_results_per_source,
        timeout=settings.search.timeout_seconds,
        title_similarity_threshold=settings.dedup.title_similarity_threshold,
    )
    papers = await orchestrator.search(
        query=req.query,
        year_start=req.year_start,
        year_end=req.year_end,
    )

    # 2. Search news/web sources
    web_articles: list = []
    if req.web_sources:
        web_orchestrator = SearchOrchestrator(
            sources=req.web_sources,
            max_results_per_source=min(req.max_results_per_source, 100),
            timeout=settings.search.timeout_seconds,
            title_similarity_threshold=0.85,
        )
        web_articles = await web_orchestrator.search(
            query=req.query,
            year_start=req.year_start,
            year_end=req.year_end,
        )
        logger.info("Web search returned %d news/web articles", len(web_articles))

    all_items = papers + web_articles

    if not all_items:
        raise HTTPException(404, "No papers or articles found for this query")

    # 3. Store academic papers
    if papers:
        store.upsert_papers(papers)

    # 4. Analyse (pipeline splits academic vs news internally)
    stats = await pipeline.run(
        all_items,
        query=req.query,
        year_start=req.year_start,
        year_end=req.year_end,
    )

    # 5. Save session
    session_id = store.save_session(
        query=req.query,
        year_start=req.year_start,
        year_end=req.year_end,
        sources_used=req.sources + req.web_sources,
        total_papers=len(all_items),
        stats=stats,
    )

    # 6. Build response
    paper_responses = [
        schemas.PaperResponse(
            id=p.id,
            title=p.title,
            authors=p.get_authors(),
            year=p.year,
            venue=p.venue,
            abstract=p.abstract,
            citations=p.citations,
            doi=p.doi,
            url=p.url,
            sources=p.get_sources(),
        )
        for p in all_items
    ]

    stats_dict = stats.to_dict()
    # Convert year keys to strings for JSON
    stats_dict["papers_per_year"] = {
        str(k): v for k, v in stats_dict["papers_per_year"].items()
    }
    stats_dict["year_range"] = list(stats_dict["year_range"])

    return schemas.SearchResponse(
        session_id=session_id,
        papers=paper_responses,
        stats=schemas.FieldStatsResponse(**stats_dict),
    )
