"""Venue, author, and country analytics."""

from __future__ import annotations

import json
from collections import Counter

from src.storage.models import Paper

# Seed list of known industry affiliations
INDUSTRY_KEYWORDS = {
    "google", "meta", "facebook", "microsoft", "amazon", "apple", "nvidia",
    "ibm", "samsung", "huawei", "baidu", "tencent", "bytedance", "intel",
    "qualcomm", "openai", "deepmind", "tesla", "bosch", "siemens",
    "alibaba", "jd.com", "uber", "lyft", "salesforce", "adobe",
    "oracle", "sap", "netflix", "spotify", "twitter", "x corp",
}


def compute_top_venues(papers: list[Paper], top_n: int = 10) -> list[tuple[str, int]]:
    venues = [p.venue for p in papers if p.venue]
    counts = Counter(venues).most_common(top_n)
    return counts


def compute_top_authors(papers: list[Paper], top_n: int = 20) -> list[tuple[str, int]]:
    author_counter: Counter = Counter()
    for p in papers:
        for author in p.get_authors():
            if author.strip():
                author_counter[author.strip()] += 1
    return author_counter.most_common(top_n)


def compute_country_distribution(papers: list[Paper]) -> dict[str, int]:
    """Placeholder — requires institution-to-country mapping.
    OpenAlex provides this; others don't, so we return what we can parse."""
    # A real implementation would use OpenAlex institution country codes.
    # For now, return empty if not available.
    return {}


def compute_industry_ratio(papers: list[Paper]) -> float:
    """Fraction of papers with at least one industry-affiliated author."""
    if not papers:
        return 0.0
    industry_count = 0
    for p in papers:
        authors_str = " ".join(p.get_authors()).lower()
        # Check if any industry keyword appears in author affiliations
        # (In OpenAlex, affiliations are embedded in the author data)
        if any(kw in authors_str for kw in INDUSTRY_KEYWORDS):
            industry_count += 1
            continue
        # Also check venue / abstract for industry signals
        if p.industry_affiliated:
            industry_count += 1
    return industry_count / len(papers)


def compute_venue_stats(papers: list[Paper]) -> dict:
    """Compute all venue/author/structure metrics."""
    return {
        "top_venues": compute_top_venues(papers),
        "top_authors": compute_top_authors(papers),
        "country_distribution": compute_country_distribution(papers),
        "industry_ratio": round(compute_industry_ratio(papers), 4),
    }
