"""Heuristic fallbacks for motivation, confidence, and market detection.

Used when Ollama / LLM is not available. Returns the same output types as the
corresponding LLM tasks so callers never need to branch.
"""

from __future__ import annotations

import re
from collections import Counter

from src.analytics.nlp_fast import split_sentences
from src.storage.models import Paper

# ---------------------------------------------------------------------------
# Motivation heuristic
# ---------------------------------------------------------------------------
MOTIVATION_PATTERNS = re.compile(
    r"\b("
    r"however|unfortunately|lacks|fails? to|is limited by|challenge|barrier|gap"
    r"|remains unclear|not well understood|little is known|open problem"
    r"|motivated by|inspired by|in response to|to address"
    r"|critical need|urgent|growing demand|essential for"
    r")\b",
    re.IGNORECASE,
)


def heuristic_motivation(papers: list[Paper], max_papers: int = 500) -> dict:
    """Regex-based motivation sentence detection."""
    motivation_sentences: list[str] = []
    total_sentences = 0

    for paper in papers[:max_papers]:
        if not paper.abstract:
            continue
        sentences = split_sentences(paper.abstract)
        total_sentences += len(sentences)
        for sent in sentences:
            if MOTIVATION_PATTERNS.search(sent):
                motivation_sentences.append(sent)

    return {
        "motivation_sentences": motivation_sentences,
        "total_abstract_sentences": max(total_sentences, 1),
        "problem_sentence_count": len(motivation_sentences),
    }


# ---------------------------------------------------------------------------
# Confidence heuristic
# ---------------------------------------------------------------------------
STRONG_PATTERNS = re.compile(
    r"\b(outperforms?|state.of.the.art|significantly improves?|achieves? \d|demonstrates?|superior)\b",
    re.IGNORECASE,
)
MODERATE_PATTERNS = re.compile(
    r"\b(shows? promise|competitive|comparable to|can be used for|effective)\b",
    re.IGNORECASE,
)
HEDGED_PATTERNS = re.compile(
    r"\b(may|might|could potentially|preliminary|suggests?|appears? to|seems?)\b",
    re.IGNORECASE,
)
NEGATIVE_PATTERNS = re.compile(
    r"\b(failed|did not improve|no significant difference|inconclusive|cannot)\b",
    re.IGNORECASE,
)


def heuristic_confidence(papers: list[Paper], max_papers: int = 500) -> dict:
    """Regex-based confidence level detection."""
    counts = {"strong": 0, "moderate": 0, "hedged": 0, "negative": 0}
    claims: list[dict] = []

    for i, paper in enumerate(papers[:max_papers]):
        if not paper.abstract:
            continue
        sentences = split_sentences(paper.abstract)
        for sent in sentences:
            label = None
            if STRONG_PATTERNS.search(sent):
                label = "strong"
            elif MODERATE_PATTERNS.search(sent):
                label = "moderate"
            elif HEDGED_PATTERNS.search(sent):
                label = "hedged"
            elif NEGATIVE_PATTERNS.search(sent):
                label = "negative"
            if label:
                counts[label] += 1
                claims.append({"paper_index": i, "sentence": sent, "label": label})

    total = sum(counts.values())
    return {
        "strong_count": counts["strong"],
        "moderate_count": counts["moderate"],
        "hedged_count": counts["hedged"],
        "negative_count": counts["negative"],
        "total_result_sentences": max(total, 1),
        "claims": claims,
    }


# ---------------------------------------------------------------------------
# Market heuristic
# ---------------------------------------------------------------------------
INDUSTRY_TERMS = {
    "google", "meta", "facebook", "microsoft", "amazon", "apple", "nvidia",
    "ibm", "samsung", "huawei", "baidu", "tencent", "bytedance", "intel",
    "qualcomm", "openai", "deepmind", "tesla", "bosch", "siemens",
    "alibaba", "uber", "salesforce", "adobe", "oracle", "sap",
}

FUNDING_PATTERNS = re.compile(
    r"\b(funded by|supported by|grant|NSF|DARPA|NIH|ERC|Horizon|EPSRC|NSERC)\b",
    re.IGNORECASE,
)

PATENT_PATTERNS = re.compile(
    r"\b(patent|commerciali[sz]ation|industry partner|deployed|production)\b",
    re.IGNORECASE,
)


def heuristic_market(papers: list[Paper], max_papers: int = 500) -> dict:
    """Keyword-based market signal detection."""
    company_counter: Counter = Counter()
    funder_counter: Counter = Counter()
    patent_count = 0

    for paper in papers[:max_papers]:
        text = (paper.abstract or "") + " " + " ".join(paper.get_authors())
        text_lower = text.lower()

        for company in INDUSTRY_TERMS:
            if company in text_lower:
                company_counter[company] += 1

        # Funders from crossref data
        for funder in paper.get_funder_names():
            if funder.strip():
                funder_counter[funder.strip()] += 1

        # Funding patterns in abstract
        if FUNDING_PATTERNS.search(paper.abstract or ""):
            pass  # we already count explicit funder names above

        if PATENT_PATTERNS.search(paper.abstract or ""):
            patent_count += 1

    return {
        "companies": [c for c, _ in company_counter.most_common(20)],
        "funders": [f for f, _ in funder_counter.most_common(20)],
        "funder_counts": funder_counter.most_common(20),
        "patent_paper_count": patent_count,
        "total_papers_analysed": min(len(papers), max_papers),
    }
