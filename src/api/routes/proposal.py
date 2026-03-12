"""POST /api/v1/proposal — proposal novelty & gap analysis."""

from __future__ import annotations

import json
import logging

from fastapi import APIRouter, HTTPException

from src.api import schemas
import src.api.main as _main

router = APIRouter()
logger = logging.getLogger(__name__)


@router.post("/proposal", response_model=schemas.ProposalAnalysisResponse)
async def analyze_proposal(req: schemas.ProposalRequest):
    """Analyse a research proposal against the existing literature."""
    store = _main.store
    pipeline = _main.pipeline
    llm_client = _main.llm_client
    if store is None or pipeline is None:
        raise HTTPException(503, "Service not ready")

    if llm_client is None:
        raise HTTPException(
            503,
            "LLM is required for proposal analysis but is not available.",
        )

    llm_ok = await llm_client.health_check()
    if not llm_ok:
        raise HTTPException(503, "LLM is not reachable. Start Ollama first.")

    # Get papers to compare against
    papers = store.get_papers_by_query(req.reference_query) if req.reference_query else store.get_all_papers()
    if not papers:
        raise HTTPException(
            404,
            "No reference papers found. Run a search first so there is literature to compare against.",
        )

    from src.analytics.proposal_analysis import ProposalAnalyzer

    analyzer = ProposalAnalyzer(llm_client)
    result = await analyzer.analyze(
        proposal_text=req.proposal_text,
        papers=papers,
    )

    # persist
    store.save_proposal_analysis(result)

    # Parse stored JSON fields for response
    overlapping = json.loads(result.top_overlapping_papers or "[]")
    gap_clusters = json.loads(result.gap_clusters or "[]")
    recommended = json.loads(result.recommended_citations or "[]")

    return schemas.ProposalAnalysisResponse(
        novelty_score=result.novelty_score or 0.0,
        overlapping_papers=overlapping,
        gap_clusters=gap_clusters,
        recommended_citations=recommended,
        narrative=result.llm_narrative,
    )
