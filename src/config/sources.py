"""Data source registry — enumerates available academic APIs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class SourceInfo:
    name: str
    display_name: str
    tier: int  # 1=free, 2=api-key, 3=unofficial
    base_url: str
    requires_key: bool = False
    key_env_var: str | None = None


SOURCES: dict[str, SourceInfo] = {
    "arxiv": SourceInfo(
        name="arxiv",
        display_name="arXiv",
        tier=1,
        base_url="http://export.arxiv.org/api/query",
    ),
    "semantic_scholar": SourceInfo(
        name="semantic_scholar",
        display_name="Semantic Scholar",
        tier=1,
        base_url="https://api.semanticscholar.org/graph/v1",
    ),
    "openalex": SourceInfo(
        name="openalex",
        display_name="OpenAlex",
        tier=1,
        base_url="https://api.openalex.org",
    ),
    "pubmed": SourceInfo(
        name="pubmed",
        display_name="PubMed",
        tier=1,
        base_url="https://eutils.ncbi.nlm.nih.gov/entrez/eutils",
    ),
    "crossref": SourceInfo(
        name="crossref",
        display_name="Crossref",
        tier=1,
        base_url="https://api.crossref.org/works",
    ),
    "ieee": SourceInfo(
        name="ieee",
        display_name="IEEE Xplore",
        tier=2,
        base_url="https://ieeexploreapi.ieee.org/api/v1/search/articles",
        requires_key=True,
        key_env_var="IEEE_API_KEY",
    ),
    "springer": SourceInfo(
        name="springer",
        display_name="Springer Nature",
        tier=2,
        base_url="https://api.springernature.com/meta/v2/json",
        requires_key=True,
        key_env_var="SPRINGER_API_KEY",
    ),
    "nature": SourceInfo(
        name="nature",
        display_name="Nature / Nature Communications",
        tier=2,
        base_url="https://api.springernature.com/meta/v2/json",
        requires_key=True,
        key_env_var="SPRINGER_API_KEY",
    ),
    "google_news": SourceInfo(
        name="google_news",
        display_name="Google News",
        tier=1,
        base_url="https://news.google.com/rss/search",
    ),
    "bing_news": SourceInfo(
        name="bing_news",
        display_name="Bing News",
        tier=1,
        base_url="https://www.bing.com/news/search",
    ),
}


def get_available_sources(include_tier2: bool = False) -> list[SourceInfo]:
    """Return sources that can be queried (Tier 1 always, Tier 2 if keys set)."""
    import os

    result: list[SourceInfo] = []
    for src in SOURCES.values():
        if src.tier == 1:
            result.append(src)
        elif include_tier2 and src.requires_key:
            key = os.environ.get(src.key_env_var or "", "")
            if key:
                result.append(src)
    return result
