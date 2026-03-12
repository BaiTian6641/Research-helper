"""LLM task: generate narrative field summary."""

from __future__ import annotations

import logging
import random

from src.llm.client import LLMClient
from src.llm.prompts import NARRATIVE_SUMMARY_PROMPT
from src.storage.models import FieldStats, Paper

logger = logging.getLogger(__name__)


async def generate_narrative(
    papers: list[Paper],
    stats: FieldStats,
    llm_client: LLMClient,
    sample_size: int = 10,
) -> dict:
    """Generate a 3-5 paragraph field overview.

    Returns:
        {
            "narrative": str,
            "maturity_label": str,
            "open_questions": list[str],
        }
    """
    # Sample representative abstracts
    papers_with_abs = [p for p in papers if p.abstract]
    if not papers_with_abs:
        return _empty()

    sample = random.sample(papers_with_abs, min(sample_size, len(papers_with_abs)))
    sample_text = "\n\n".join(
        f"[{i}] {p.title}\n{p.abstract[:400]}"
        for i, p in enumerate(sample)
    )

    top_venues_str = ", ".join(v for v, _ in stats.top_venues[:5]) if stats.top_venues else "N/A"
    top_themes_str = ", ".join(stats.top_themes[:8]) if stats.top_themes else "N/A"

    prompt = NARRATIVE_SUMMARY_PROMPT.format(
        query=stats.query,
        total_papers=stats.total_papers,
        year_start=stats.year_range[0],
        year_end=stats.year_range[1],
        growth_rate=stats.growth_rate_pct,
        top_venues=top_venues_str,
        top_themes=top_themes_str,
        sample_abstracts=sample_text,
    )

    try:
        result = await llm_client.complete_json(prompt, temperature=0.7)
        return {
            "narrative": result.get("narrative", ""),
            "maturity_label": result.get("maturity_label", "Unknown"),
            "open_questions": result.get("open_questions", []),
        }
    except Exception as e:
        logger.error("Narrative generation failed: %s", e)
        return _empty()


def _empty() -> dict:
    return {
        "narrative": "",
        "maturity_label": "Unknown",
        "open_questions": [],
    }
