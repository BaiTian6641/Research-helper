"""Trend analytics — papers/year, growth rate, CAGR."""

from __future__ import annotations

import math
from collections import Counter

from src.storage.models import Paper


def compute_papers_per_year(papers: list[Paper]) -> dict[int, int]:
    """Returns {year: count} dict sorted by year."""
    years = [p.year for p in papers if p.year]
    counts = Counter(years)
    return dict(sorted(counts.items()))


def compute_growth_rate(papers_per_year: dict[int, int]) -> float:
    """YoY growth: (last 2yr count - prev 2yr count) / prev 2yr count * 100."""
    if len(papers_per_year) < 4:
        return 0.0
    years = sorted(papers_per_year.keys())
    last_2 = sum(papers_per_year.get(y, 0) for y in years[-2:])
    prev_2 = sum(papers_per_year.get(y, 0) for y in years[-4:-2])
    if prev_2 == 0:
        return 0.0
    return ((last_2 - prev_2) / prev_2) * 100.0


def compute_cagr(papers_per_year: dict[int, int]) -> float:
    """Compound annual growth rate across full date range."""
    if len(papers_per_year) < 2:
        return 0.0
    years = sorted(papers_per_year.keys())
    first_count = papers_per_year[years[0]]
    last_count = papers_per_year[years[-1]]
    n_years = years[-1] - years[0]
    if n_years <= 0 or first_count <= 0:
        return 0.0
    return (math.pow(last_count / first_count, 1.0 / n_years) - 1.0) * 100.0


def count_review_papers(papers: list[Paper]) -> int:
    """Count papers whose title suggests review / survey / meta-analysis."""
    review_patterns = ("review", "survey", "systematic review", "meta-analysis", "meta analysis")
    count = 0
    for p in papers:
        t = p.title.lower()
        if any(pat in t for pat in review_patterns):
            count += 1
    return count


def compute_trend_stats(papers: list[Paper]) -> dict:
    """Convenience: compute all trend statistics at once."""
    ppy = compute_papers_per_year(papers)
    return {
        "papers_per_year": ppy,
        "growth_rate_pct": compute_growth_rate(ppy),
        "cagr_pct": compute_cagr(ppy),
        "total_papers": len(papers),
        "review_papers": count_review_papers(papers),
    }
