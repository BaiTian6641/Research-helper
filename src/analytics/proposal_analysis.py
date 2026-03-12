"""Proposal analyser — compares a research proposal against the literature."""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime
from typing import List

from src.llm.client import LLMClient
from src.llm.prompts import (
    GAP_ANALYSIS_PROMPT,
    PROPOSAL_CLAIM_EXTRACTION_PROMPT,
    format_abstracts_batch,
)
from src.storage.models import Paper, ProposalAnalysis

logger = logging.getLogger(__name__)


class ProposalAnalyzer:
    """End-to-end proposal novelty & gap analysis using LLM."""

    def __init__(self, llm_client: LLMClient):
        self.llm = llm_client

    async def analyze(
        self,
        proposal_text: str,
        papers: List[Paper],
    ) -> ProposalAnalysis:
        """Run full analysis: claim extraction → gap analysis → scoring."""

        # 1. Extract claims from the proposal
        claims = await self._extract_claims(proposal_text)

        # 2. Build papers context for gap analysis
        papers_text = self._build_papers_text(papers, max_papers=50)
        claims_text = "\n".join(
            f"- [{c['type']}] {c['text']}" for c in claims
        )

        # 3. Gap analysis
        gap_result = await self._run_gap_analysis(claims_text, papers_text)

        # 4. Compute novelty score
        overlapping = gap_result.get("overlaps", [])
        gaps = gap_result.get("gaps", [])
        recommended = gap_result.get("recommended_citations", [])

        novelty_score = self._compute_novelty_score(
            claims, overlapping, gaps
        )

        # 5. Build narrative
        narrative = self._build_narrative(
            claims, overlapping, gaps, recommended, novelty_score
        )

        # 6. Build result
        result = ProposalAnalysis(
            id=uuid.uuid4().hex[:16],
            proposal_text=proposal_text[:5000],  # truncate for storage
            run_at=datetime.utcnow(),
            novelty_score=novelty_score,
            top_overlapping_papers=json.dumps(overlapping),
            gap_clusters=json.dumps(gaps),
            recommended_citations=json.dumps(recommended),
            llm_narrative=narrative,
        )
        return result

    async def _extract_claims(self, proposal_text: str) -> list[dict]:
        """Use LLM to extract claims from the proposal."""
        prompt = PROPOSAL_CLAIM_EXTRACTION_PROMPT.format(
            proposal_text=proposal_text[:4000]
        )
        result = await self.llm.complete_json(prompt)
        if result and "claims" in result:
            return result["claims"]
        return [{"text": proposal_text[:500], "type": "objective"}]

    async def _run_gap_analysis(
        self, claims_text: str, papers_text: str
    ) -> dict:
        """Use LLM to compare claims against existing papers."""
        prompt = GAP_ANALYSIS_PROMPT.format(
            claims_text=claims_text,
            papers_text=papers_text,
        )
        result = await self.llm.complete_json(prompt)
        if result:
            return result
        return {"overlaps": [], "gaps": [], "recommended_citations": []}

    @staticmethod
    def _build_papers_text(papers: list[Paper], max_papers: int = 50) -> str:
        """Build a compact text of paper titles+abstracts for context."""
        lines: list[str] = []
        for i, p in enumerate(papers[:max_papers]):
            abstract_snippet = (p.abstract or "")[:200]
            lines.append(f"[{i}] {p.title} ({p.year}): {abstract_snippet}")
        return "\n".join(lines)

    @staticmethod
    def _compute_novelty_score(
        claims: list[dict],
        overlaps: list[dict],
        gaps: list[str],
    ) -> float:
        """Simple novelty score: ratio of gaps to total claims (0-100)."""
        total_claims = max(len(claims), 1)
        overlap_claims = len(overlaps)
        gap_count = len(gaps)

        if total_claims == 0:
            return 50.0

        # Higher = more novel
        overlap_ratio = overlap_claims / total_claims
        gap_ratio = gap_count / max(gap_count + overlap_claims, 1)

        score = (1 - overlap_ratio * 0.6) * 50 + gap_ratio * 50
        return round(min(max(score, 0), 100), 1)

    @staticmethod
    def _build_narrative(
        claims: list[dict],
        overlaps: list[dict],
        gaps: list[str],
        recommended: list[str],
        novelty_score: float,
    ) -> str:
        """Build a human-readable narrative from the analysis results."""
        parts: list[str] = []

        parts.append(
            f"**Novelty Assessment (Score: {novelty_score}/100)**\n"
        )

        if overlaps:
            parts.append(
                f"The proposal has {len(overlaps)} claim(s) that overlap "
                f"with existing literature:\n"
            )
            for o in overlaps[:5]:
                similar = ", ".join(o.get("similar_papers", [])[:3])
                parts.append(
                    f"- *{o.get('claim', 'N/A')}* — similar to: {similar}. "
                    f"{o.get('similarity_note', '')}"
                )
            parts.append("")

        if gaps:
            parts.append(
                f"The proposal identifies {len(gaps)} potential gap(s) "
                f"or novel contribution(s):\n"
            )
            for g in gaps[:5]:
                parts.append(f"- {g}")
            parts.append("")

        if recommended:
            parts.append("**Recommended Citations:**\n")
            for r in recommended[:10]:
                parts.append(f"- {r}")

        return "\n".join(parts)
