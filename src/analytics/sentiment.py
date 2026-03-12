"""Sentiment analysis — detects positive/negative/neutral attitude from text.

Tier 1: Heuristic (keyword + pattern based) — always available.
Tier 2: LLM-based — used when Ollama is running.

Both tiers return the same SentimentResult dict format.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from src.analytics.nlp_fast import split_sentences
from src.storage.models import Paper

# ---------------------------------------------------------------------------
# Sentiment patterns for heuristic analysis
# ---------------------------------------------------------------------------

POSITIVE_PATTERNS = re.compile(
    r"\b("
    r"breakthrough|promising|revolutionary|significant\s+advance|remarkable"
    r"|exciting|impressive|innovative|transformative|groundbreaking"
    r"|success(?:ful(?:ly)?)?|improv(?:e[sd]?|ing|ement)|enhanc(?:e[sd]?|ing)"
    r"|effective(?:ly)?|powerful|robust|efficient(?:ly)?|superior"
    r"|outperform[sed]*|state.of.the.art|novel|cutting.edge"
    r"|milestone|game.changer|paradigm.shift|tremendous|flourish"
    r"|boost(?:s|ed|ing)?|thrive[sd]?|thriving|surge[sd]?"
    r"|grow(?:s|ing|th)?|expand(?:s|ed|ing)?|opportunit(?:y|ies)"
    r"|potential|benefit[sed]*|advantage[sd]?|optimistic"
    r")\b",
    re.IGNORECASE,
)

NEGATIVE_PATTERNS = re.compile(
    r"\b("
    r"concern[sed]*|risk[sed]*|danger(?:ous)?|threat[sed]*|alarming"
    r"|fail(?:ed|s|ure|ing)?|decline[sd]?|declining|worsen(?:s|ed|ing)?"
    r"|harm(?:ful|s|ed|ing)?|damage[sd]?|damaging|devastating"
    r"|controversial|criticism|skeptic(?:al|ism)?|doubt[sd]?"
    r"|limitation[sd]?|drawback[sd]?|shortcoming[sd]?"
    r"|negative|adverse(?:ly)?|detrimental|problematic"
    r"|obstacle[sd]?|impediment[sd]?|barrier[sd]?|challenge[sd]?"
    r"|stagnant|stagnation|decline|setback[sd]?"
    r"|ethical\s+concern|privacy\s+(?:concern|risk|issue)"
    r"|bias(?:ed|es)?|inequit(?:y|able)|unfair(?:ness)?"
    r"|unsafe|insecure|vulnerab(?:le|ility|ilities)"
    r"|ban(?:ned|s)?|restrict(?:ed|ion[sd]?)?|regulat(?:e[sd]?|ion[sd]?|ory)"
    r")\b",
    re.IGNORECASE,
)

NEUTRAL_SIGNAL = re.compile(
    r"\b("
    r"report[sed]*|stud(?:y|ied|ies)|examin[sed]*|investigat[sed]*"
    r"|analys[sed]*|analyz[sed]*|found|observed|noted"
    r"|according to|data shows?|research\s+indicates?"
    r")\b",
    re.IGNORECASE,
)


def analyze_sentiment_heuristic(
    papers: list[Paper], max_items: int = 500
) -> dict:
    """Keyword-based sentiment analysis on paper/article text.

    Returns a dict with sentiment counts, ratios, and sample sentences.
    """
    positive_sents: list[dict] = []
    negative_sents: list[dict] = []
    neutral_count = 0
    total_sentences = 0

    for paper in papers[:max_items]:
        text = paper.abstract or ""
        if not text:
            continue
        sentences = split_sentences(text)
        total_sentences += len(sentences)

        for sent in sentences:
            pos_hits = len(POSITIVE_PATTERNS.findall(sent))
            neg_hits = len(NEGATIVE_PATTERNS.findall(sent))

            if pos_hits > neg_hits:
                positive_sents.append({
                    "sentence": sent,
                    "title": paper.title,
                    "source_type": paper.venue_type or "unknown",
                })
            elif neg_hits > pos_hits:
                negative_sents.append({
                    "sentence": sent,
                    "title": paper.title,
                    "source_type": paper.venue_type or "unknown",
                })
            else:
                neutral_count += 1

    total_opinionated = len(positive_sents) + len(negative_sents) + neutral_count
    if total_opinionated == 0:
        total_opinionated = 1

    return {
        "positive_count": len(positive_sents),
        "negative_count": len(negative_sents),
        "neutral_count": neutral_count,
        "total_sentences": total_sentences,
        "positive_ratio": len(positive_sents) / total_opinionated,
        "negative_ratio": len(negative_sents) / total_opinionated,
        "neutral_ratio": neutral_count / total_opinionated,
        "sentiment_score": _compute_sentiment_score(
            len(positive_sents), len(negative_sents), neutral_count
        ),
        "positive_samples": positive_sents[:20],
        "negative_samples": negative_sents[:20],
    }


def analyze_sentiment_by_source_type(
    papers: list[Paper], max_items: int = 500
) -> dict:
    """Separate sentiment analysis for academic vs news/web articles."""
    academic = [p for p in papers if (p.venue_type or "") not in ("news", "web", "blog")]
    news = [p for p in papers if (p.venue_type or "") in ("news", "web", "blog")]

    return {
        "academic": analyze_sentiment_heuristic(academic, max_items),
        "news": analyze_sentiment_heuristic(news, max_items),
        "combined": analyze_sentiment_heuristic(papers, max_items),
    }


def compute_sentiment_by_year(papers: list[Paper]) -> dict:
    """Group papers by publication year and compute sentiment for each year.

    Returns {year_str: {positive_count, negative_count, neutral_count,
                        positive_ratio, negative_ratio, neutral_ratio}}.
    """
    from collections import defaultdict
    by_year: dict[int, list] = defaultdict(list)
    for p in papers:
        if p.year:
            by_year[p.year].append(p)
    result: dict = {}
    for year in sorted(by_year.keys()):
        sent = analyze_sentiment_heuristic(by_year[year])
        result[str(year)] = {
            "positive_count": sent["positive_count"],
            "negative_count": sent["negative_count"],
            "neutral_count": sent["neutral_count"],
            "positive_ratio": round(sent["positive_ratio"], 3),
            "negative_ratio": round(sent["negative_ratio"], 3),
            "neutral_ratio": round(sent["neutral_ratio"], 3),
        }
    return result


def _compute_sentiment_score(positive: int, negative: int, neutral: int) -> float:
    """Compute a sentiment score from -100 (all negative) to +100 (all positive).

    0 = perfectly balanced or no data.
    """
    total = positive + negative + neutral
    if total == 0:
        return 0.0
    # Weighted: positive = +1, neutral = 0, negative = -1
    raw = (positive - negative) / total
    return round(raw * 100, 1)
