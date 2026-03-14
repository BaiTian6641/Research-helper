"""LLM task: author background analysis.

Profiles the top authors in a research field based on their publication
record, affiliations (inferred from paper metadata), and domain of
expertise.  Gives the user a quick picture of *who* the key contributors
are and whether they come from academia or industry.
"""

from __future__ import annotations

import json
import logging

from src.llm.client import LLMClient
from src.llm.prompts import AUTHOR_PROFILE_PROMPT
from src.storage.models import Paper

logger = logging.getLogger(__name__)


async def profile_top_authors(
    papers: list[Paper],
    most_cited_authors: list[dict],
    llm_client: LLMClient,
    max_authors: int = 10,
    token_callback=None,
) -> list[dict]:
    """Generate background profiles for the most-cited authors.

    Returns a list of dicts:
        [{"name": str, "affiliation_type": "academia"|"industry"|"government"|"unknown",
          "domain": str, "notable_work": str}]
    """
    if not most_cited_authors:
        return []

    # Build a concise evidence block for each author from their papers
    author_papers: dict[str, list[str]] = {}
    for p in papers:
        if p.citations is None:
            continue
        for author in p.get_authors():
            name = author.strip()
            if not name:
                continue
            if name not in author_papers:
                author_papers[name] = []
            if len(author_papers[name]) < 3:
                venue_info = f" [{p.venue}]" if p.venue else ""
                author_papers[name].append(
                    f"({p.year or '?'}{venue_info}) {p.title}"
                )

    # Format the top authors with their publication evidence
    author_blocks: list[str] = []
    for a in most_cited_authors[:max_authors]:
        name = a["author"]
        total = a["total_citations"]
        count = a["paper_count"]
        pubs = author_papers.get(name, [])
        pub_str = "; ".join(pubs) if pubs else "N/A"
        author_blocks.append(
            f"- {name} ({total} citations, {count} papers): {pub_str}"
        )

    if not author_blocks:
        return []

    authors_text = "\n".join(author_blocks)
    prompt = AUTHOR_PROFILE_PROMPT.format(authors_text=authors_text)

    try:
        result = await llm_client.complete_json(
            prompt, max_tokens=8192, token_callback=token_callback,
        )
        profiles = result.get("profiles", [])
        if isinstance(profiles, list):
            return [
                {
                    "name": p.get("name", ""),
                    "affiliation_type": p.get("affiliation_type", "unknown"),
                    "domain": p.get("domain", ""),
                    "notable_work": p.get("notable_work", ""),
                }
                for p in profiles
                if isinstance(p, dict) and p.get("name")
            ]
    except Exception as e:
        logger.warning("Author profiling failed: %s", e)

    return []
