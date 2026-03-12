"""LLM task: extract research themes from abstracts."""

from __future__ import annotations

import logging

from src.llm.client import LLMClient
from src.llm.prompts import THEME_EXTRACTION_PROMPT, format_abstracts_batch
from src.storage.models import Paper

logger = logging.getLogger(__name__)


async def extract_themes(
    papers: list[Paper],
    llm_client: LLMClient,
    batch_size: int = 8,
    max_papers: int = 500,
) -> list[str]:
    """Extract top research themes from paper abstracts via LLM.

    Returns a deduplicated list of theme strings.
    """
    abstracts = [
        (i, p.abstract)
        for i, p in enumerate(papers[:max_papers])
        if p.abstract
    ]
    if not abstracts:
        return []

    all_themes: list[str] = []
    for batch_start in range(0, len(abstracts), batch_size):
        batch = abstracts[batch_start : batch_start + batch_size]
        abstracts_text = format_abstracts_batch(batch)
        prompt = THEME_EXTRACTION_PROMPT.format(abstracts_text=abstracts_text)

        try:
            result = await llm_client.complete_json(prompt)
            themes = result.get("themes", [])
            if isinstance(themes, list):
                all_themes.extend(str(t) for t in themes)
        except Exception as e:
            logger.warning("Theme extraction batch failed: %s", e)
            continue

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique: list[str] = []
    for t in all_themes:
        t_lower = t.lower().strip()
        if t_lower and t_lower not in seen:
            seen.add(t_lower)
            unique.append(t.strip())
    return unique[:15]
