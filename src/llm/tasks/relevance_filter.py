"""LLM task: post-processing relevance filter.

Scores each paper's relevance to the search query and filters out
unrelated articles. Papers are tracked by their database ID throughout.
Falls back to a keyword-overlap heuristic when the LLM is unavailable.
"""

from __future__ import annotations

import logging
import re
from collections import Counter

from src.llm.client import LLMClient
from src.llm.prompts import RELEVANCE_FILTER_PROMPT
from src.storage.models import Paper

logger = logging.getLogger(__name__)

# Papers with relevance_score below this are considered unrelated
RELEVANCE_THRESHOLD = 0.4


async def filter_irrelevant_papers(
    papers: list[Paper],
    query: str,
    llm_client: LLMClient | None = None,
    threshold: float = RELEVANCE_THRESHOLD,
    batch_size: int = 12,
    token_callback=None,
) -> tuple[list[Paper], list[dict]]:
    """Score and filter papers by relevance to the query.

    Returns:
        (relevant_papers, filter_log)
        filter_log is a list of dicts:
          {"id": str, "title": str, "relevance_score": float, "kept": bool}
    """
    if not papers:
        return [], []

    if llm_client:
        scored = await _score_with_llm(
            papers, query, llm_client, batch_size, token_callback,
        )
    else:
        scored = _score_heuristic(papers, query)

    relevant: list[Paper] = []
    filter_log: list[dict] = []

    for paper, score in scored:
        kept = score >= threshold
        paper.relevance_score = round(score, 3)
        paper.relevance_label = (
            "high" if score >= 0.7 else "medium" if score >= threshold else "low"
        )
        filter_log.append({
            "id": paper.id,
            "title": paper.title or "",
            "relevance_score": round(score, 3),
            "kept": kept,
        })
        if kept:
            relevant.append(paper)

    removed = len(papers) - len(relevant)
    if removed:
        logger.info(
            "Relevance filter: kept %d/%d papers (removed %d unrelated)",
            len(relevant), len(papers), removed,
        )
    return relevant, filter_log


# ------------------------------------------------------------------
# LLM scoring
# ------------------------------------------------------------------

async def _score_with_llm(
    papers: list[Paper],
    query: str,
    llm_client: LLMClient,
    batch_size: int,
    token_callback,
) -> list[tuple[Paper, float]]:
    """Use LLM to score relevance of each paper to the query."""
    from src.llm.safety import sanitise_abstract

    results: list[tuple[Paper, float]] = []
    # Build ID-indexed list for batch processing
    indexed: list[tuple[int, Paper]] = list(enumerate(papers))

    for batch_start in range(0, len(indexed), batch_size):
        batch = indexed[batch_start: batch_start + batch_size]

        # Format papers for prompt: [idx] Title | Abstract snippet
        parts: list[str] = []
        for idx, paper in batch:
            title = paper.title or "(untitled)"
            abstract = sanitise_abstract(paper.abstract or "")[:300]
            parts.append(f"[{idx}] {title}\n    {abstract}")
        papers_text = "\n\n".join(parts)

        prompt = RELEVANCE_FILTER_PROMPT.format(
            query=query, papers_text=papers_text,
        )

        try:
            result = await llm_client.complete_json(
                prompt, max_tokens=4096, token_callback=token_callback,
            )
            scores_list = result.get("scores", [])
            # Build a lookup: index → score
            score_map: dict[int, float] = {}
            for entry in scores_list:
                if isinstance(entry, dict):
                    idx = entry.get("index")
                    sc = entry.get("relevance", 0.5)
                    if idx is not None:
                        score_map[int(idx)] = max(0.0, min(1.0, float(sc)))

            for idx, paper in batch:
                score = score_map.get(idx, 0.5)  # default to medium if missing
                results.append((paper, score))
        except Exception as e:
            logger.warning("Relevance scoring batch failed: %s", e)
            # Fall back to heuristic for this batch
            for idx, paper in batch:
                score = _heuristic_score(paper, query)
                results.append((paper, score))

    return results


# ------------------------------------------------------------------
# Heuristic fallback
# ------------------------------------------------------------------

def _score_heuristic(
    papers: list[Paper], query: str,
) -> list[tuple[Paper, float]]:
    """Keyword-overlap heuristic when LLM is unavailable."""
    return [(p, _heuristic_score(p, query)) for p in papers]


def _heuristic_score(paper: Paper, query: str) -> float:
    """Score a single paper by keyword overlap with the query."""
    query_terms = _tokenise(query)
    if not query_terms:
        return 0.5

    title_terms = _tokenise(paper.title or "")
    abstract_terms = _tokenise(paper.abstract or "")
    keyword_terms = _tokenise(" ".join(paper.get_keywords()))

    # Weighted overlap: title matches matter most
    title_overlap = len(query_terms & title_terms) / len(query_terms)
    abstract_overlap = len(query_terms & abstract_terms) / len(query_terms)
    keyword_overlap = len(query_terms & keyword_terms) / len(query_terms)

    score = (
        0.50 * title_overlap
        + 0.35 * abstract_overlap
        + 0.15 * keyword_overlap
    )
    return min(score, 1.0)


_WORD_RE = re.compile(r"[a-z0-9]+(?:[-'][a-z0-9]+)*")


def _tokenise(text: str) -> set[str]:
    """Extract lowercase word tokens, dropping very short ones."""
    return {w for w in _WORD_RE.findall(text.lower()) if len(w) > 2}
