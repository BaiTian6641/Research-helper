"""Citation analytics — h-index, velocity, top-cited papers."""

from __future__ import annotations

import statistics
from datetime import datetime

from src.storage.models import Paper

CURRENT_YEAR = datetime.now().year


def compute_citation_velocity(paper: Paper) -> float:
    """Citations per year since publication."""
    if not paper.citations or not paper.year:
        return 0.0
    age = max(CURRENT_YEAR - paper.year + 1, 1)
    return paper.citations / age


def compute_h_index(papers: list[Paper]) -> int:
    """Virtual h-index for the paper set."""
    cites = sorted(
        (p.citations for p in papers if p.citations is not None),
        reverse=True,
    )
    h = 0
    for i, c in enumerate(cites, start=1):
        if c >= i:
            h = i
        else:
            break
    return h


def compute_citation_stats(papers: list[Paper]) -> dict:
    """Compute all citation metrics."""
    cites_list = [p.citations for p in papers if p.citations is not None]
    velocities = [compute_citation_velocity(p) for p in papers if p.citations is not None and p.year]

    cumulative = sum(cites_list) if cites_list else 0
    median = statistics.median(cites_list) if cites_list else 0.0
    avg_velocity = statistics.mean(velocities) if velocities else 0.0
    h_index = compute_h_index(papers)

    # Top cited
    papers_with_cites = [(p.title, p.citations or 0) for p in papers if p.citations is not None]
    papers_with_cites.sort(key=lambda x: x[1], reverse=True)
    top_cited = papers_with_cites[:10]

    return {
        "cumulative_citations": cumulative,
        "median_citations": median,
        "avg_citation_velocity": round(avg_velocity, 2),
        "h_index_estimate": h_index,
        "top_cited_papers": top_cited,
    }
