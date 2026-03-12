"""POST /api/v1/analyze — re-run analytics on existing papers."""

from __future__ import annotations

import logging

from fastapi import APIRouter, HTTPException

from src.api import schemas
import src.api.main as _main

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/analyze", response_model=schemas.FieldStatsResponse)
async def analyze(req: schemas.AnalyzeRequest):
    """Run the analytics pipeline on papers already in the database."""
    store = _main.store
    pipeline = _main.pipeline
    if store is None or pipeline is None:
        raise HTTPException(503, "Service not ready")

    papers = store.get_papers_by_query(req.query)
    if not papers:
        raise HTTPException(404, "No papers found for this query in the database")

    stats = await pipeline.run(
        papers,
        query=req.query,
        year_start=req.year_start,
        year_end=req.year_end,
    )

    stats_dict = stats.to_dict()
    stats_dict["papers_per_year"] = {
        str(k): v for k, v in stats_dict["papers_per_year"].items()
    }
    stats_dict["year_range"] = list(stats_dict["year_range"])

    return schemas.FieldStatsResponse(**stats_dict)
