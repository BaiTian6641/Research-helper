"""Unified analytics pipeline — orchestrates statistical + LLM analytics.

Design: every analysis function has signature run(papers, llm_client=None).
When llm_client is provided → uses LLM. When None → heuristic fallback.
Both tiers return the same output types.

The pipeline separates academic papers from news/web articles and combines
signals from both for comprehensive scoring.
"""

from __future__ import annotations

import logging
from datetime import datetime

from src.analytics.trend import compute_trend_stats
from src.analytics.citations import compute_citation_stats
from src.analytics.venues import compute_venue_stats
from src.analytics.nlp_fast import compute_nlp_stats
from src.analytics.sentiment import (
    analyze_sentiment_heuristic,
    analyze_sentiment_by_source_type,
    compute_sentiment_by_year,
)
from src.analytics.scores import (
    compute_comprehensive_score,
    compute_confidence_score,
    compute_interest_score,
    compute_market_score,
    compute_motivation_score,
    compute_public_sentiment_score,
)
from src.analytics.heuristics import (
    heuristic_confidence,
    heuristic_market,
    heuristic_motivation,
)
from src.llm.client import LLMClient
from src.storage.models import FieldStats, Paper

logger = logging.getLogger(__name__)

NEWS_VENUE_TYPES = {"news", "web", "blog"}


class AnalyticsPipeline:
    """Runs the full analytics pipeline on a set of papers."""

    def __init__(self, llm_client: LLMClient | None = None):
        self.llm_client = llm_client
        self._llm_available = False

    async def check_llm(self) -> bool:
        """Check if the LLM is available."""
        if self.llm_client is None:
            self._llm_available = False
            return False
        self._llm_available = await self.llm_client.health_check()
        if self._llm_available:
            self._llm_available = await self.llm_client.is_model_available()
        return self._llm_available

    async def run(
        self,
        papers: list[Paper],
        query: str = "",
        year_start: int | None = None,
        year_end: int | None = None,
    ) -> FieldStats:
        """Run the full analytics pipeline.

        Splits input into academic papers and news/web articles.
        Runs statistical analytics on academic, sentiment on news,
        and combines both for comprehensive scoring.
        """
        if not papers:
            return FieldStats(query=query)

        # Split into academic vs news/web
        academic_papers = [
            p for p in papers if (p.venue_type or "") not in NEWS_VENUE_TYPES
        ]
        news_articles = [
            p for p in papers if (p.venue_type or "") in NEWS_VENUE_TYPES
        ]

        logger.info(
            "Pipeline input: %d total (%d academic, %d news/web)",
            len(papers), len(academic_papers), len(news_articles),
        )

        # Determine year range from academic papers
        years = [p.year for p in academic_papers if p.year]
        if not years:
            years = [p.year for p in papers if p.year]
        if not year_start:
            year_start = min(years) if years else datetime.now().year
        if not year_end:
            year_end = max(years) if years else datetime.now().year

        logger.info(
            "Running analytics (%d–%d), LLM=%s",
            year_start, year_end, self._llm_available,
        )

        # ── Part A: Statistical analytics on ACADEMIC papers ──
        analysis_papers = academic_papers if academic_papers else papers
        trend = compute_trend_stats(analysis_papers)
        citation = compute_citation_stats(analysis_papers)
        venue = compute_venue_stats(analysis_papers)
        nlp = compute_nlp_stats(analysis_papers)

        # ── Part B: Sentiment analysis on ALL articles ──
        sentiment_by_type = analyze_sentiment_by_source_type(papers)
        news_sentiment = sentiment_by_type["news"]
        combined_sentiment = sentiment_by_type["combined"]
        sentiment_by_year = compute_sentiment_by_year(papers)

        # ── Part C: LLM or heuristic for motivation, confidence, market ──
        if self._llm_available and self.llm_client:
            motivation, confidence, market, themes, narrative = await self._run_llm(
                analysis_papers, query, year_start, year_end, trend, venue
            )
            # Supplement: LLM-classified paper sentiment gives richer sample sentences
            from src.llm.tasks.sentiment_analyzer import analyze_sentiment_llm
            llm_sent = await analyze_sentiment_llm(analysis_papers, self.llm_client)
            if llm_sent["positive_samples"] or llm_sent["negative_samples"]:
                combined_sentiment = {
                    **combined_sentiment,
                    "positive_samples": llm_sent["positive_samples"],
                    "negative_samples": llm_sent["negative_samples"],
                }
        else:
            motivation, confidence, market, themes, narrative = self._run_heuristic(
                analysis_papers
            )

        # ── Part D: Compute scores (academic + public blended) ──
        news_count = len(news_articles)

        # Public sentiment score (0–100, 50=neutral)
        public_sentiment = compute_public_sentiment_score(
            positive_ratio=news_sentiment["positive_ratio"],
            negative_ratio=news_sentiment["negative_ratio"],
            total_articles=news_count,
        )

        # Sentiment score from combined text (-100 to +100)
        combined_sentiment_score = combined_sentiment["sentiment_score"]

        interest = compute_interest_score(
            total_papers=trend["total_papers"],
            growth_rate_pct=trend["growth_rate_pct"],
            cumulative_citations=citation["cumulative_citations"],
            avg_citation_velocity=citation["avg_citation_velocity"],
            news_article_count=news_count,
        )

        motivation_score = compute_motivation_score(
            problem_sentence_count=motivation["problem_sentence_count"],
            total_abstract_sentences=motivation["total_abstract_sentences"],
        )

        confidence_score = compute_confidence_score(
            strong_count=confidence["strong_count"],
            moderate_count=confidence["moderate_count"],
            hedged_count=confidence["hedged_count"],
            negative_count=confidence["negative_count"],
            total_result_sentences=confidence["total_result_sentences"],
            public_sentiment_score=combined_sentiment_score,
        )

        # Market: compute ratios
        total_p = len(analysis_papers) or 1
        funding_ratio = len(market.get("funders", [])) / max(total_p, 1)
        patent_ratio = market.get("patent_paper_count", 0) / max(total_p, 1)
        market_sc = compute_market_score(
            industry_ratio=venue["industry_ratio"],
            funding_ratio=min(funding_ratio, 1.0),
            patent_ratio=min(patent_ratio, 1.0),
            news_positive_ratio=news_sentiment["positive_ratio"],
            news_article_count=news_count,
        )

        # Comprehensive score (the new top-level metric)
        comprehensive = compute_comprehensive_score(
            interest=interest,
            motivation=motivation_score,
            confidence=confidence_score,
            market=market_sc,
            public_sentiment=public_sentiment,
        )

        # Assemble FieldStats
        stats = FieldStats(
            query=query,
            year_range=(year_start, year_end),
            total_papers=trend["total_papers"],
            review_papers=trend["review_papers"],
            papers_per_year=trend["papers_per_year"],
            growth_rate_pct=round(trend["growth_rate_pct"], 2),
            cagr_pct=round(trend["cagr_pct"], 2),
            cumulative_citations=citation["cumulative_citations"],
            avg_citation_velocity=citation["avg_citation_velocity"],
            median_citations=citation["median_citations"],
            h_index_estimate=citation["h_index_estimate"],
            top_cited_papers=citation["top_cited_papers"],
            top_venues=venue["top_venues"],
            top_authors=venue["top_authors"],
            country_distribution=venue["country_distribution"],
            industry_ratio=venue["industry_ratio"],
            interest_score=interest,
            motivation_score=motivation_score,
            confidence_score=confidence_score,
            market_score=market_sc,
            public_sentiment_score=public_sentiment,
            comprehensive_score=comprehensive,
            news_article_count=news_count,
            sentiment_positive_ratio=round(combined_sentiment["positive_ratio"], 3),
            sentiment_negative_ratio=round(combined_sentiment["negative_ratio"], 3),
            sentiment_positive_samples=combined_sentiment.get("positive_samples"),
            sentiment_negative_samples=combined_sentiment.get("negative_samples"),
            sentiment_neutral_ratio=round(combined_sentiment.get("neutral_ratio", 0.0), 3),
            sentiment_by_year=sentiment_by_year,
            sentiment_by_source={
                "academic": {
                    "positive_ratio": round(sentiment_by_type["academic"]["positive_ratio"], 3),
                    "negative_ratio": round(sentiment_by_type["academic"]["negative_ratio"], 3),
                    "neutral_ratio": round(sentiment_by_type["academic"].get("neutral_ratio", 0.0), 3),
                    "positive_count": sentiment_by_type["academic"]["positive_count"],
                    "negative_count": sentiment_by_type["academic"]["negative_count"],
                    "neutral_count": sentiment_by_type["academic"]["neutral_count"],
                },
                "news": {
                    "positive_ratio": round(sentiment_by_type["news"]["positive_ratio"], 3),
                    "negative_ratio": round(sentiment_by_type["news"]["negative_ratio"], 3),
                    "neutral_ratio": round(sentiment_by_type["news"].get("neutral_ratio", 0.0), 3),
                    "positive_count": sentiment_by_type["news"]["positive_count"],
                    "negative_count": sentiment_by_type["news"]["negative_count"],
                    "neutral_count": sentiment_by_type["news"]["neutral_count"],
                },
            },
            top_themes=themes,
            top_funders=market.get("funder_counts"),
            field_narrative=narrative.get("narrative") if narrative else None,
            maturity_label=narrative.get("maturity_label") if narrative else None,
        )
        return stats

    async def _run_llm(
        self,
        papers: list[Paper],
        query: str,
        year_start: int,
        year_end: int,
        trend: dict,
        venue: dict,
    ) -> tuple[dict, dict, dict, list[str], dict]:
        """Run LLM-backed analytics tasks."""
        from src.llm.tasks.theme_extractor import extract_themes
        from src.llm.tasks.motivation_classifier import classify_motivation
        from src.llm.tasks.confidence_detector import detect_confidence
        from src.llm.tasks.market_extractor import extract_market_signals
        from src.llm.tasks.narrative import generate_narrative

        assert self.llm_client is not None

        logger.info("Running LLM analytics with model: %s", self.llm_client.model)

        themes = await extract_themes(papers, self.llm_client)
        motivation = await classify_motivation(papers, self.llm_client)
        confidence = await detect_confidence(papers, self.llm_client)
        market = await extract_market_signals(papers, self.llm_client)

        # Build partial FieldStats for narrative generation
        partial_stats = FieldStats(
            query=query,
            year_range=(year_start, year_end),
            total_papers=trend["total_papers"],
            growth_rate_pct=trend["growth_rate_pct"],
            top_venues=venue["top_venues"],
            top_themes=themes,
        )
        narrative = await generate_narrative(papers, partial_stats, self.llm_client)

        return motivation, confidence, market, themes, narrative

    def _run_heuristic(
        self, papers: list[Paper]
    ) -> tuple[dict, dict, dict, list[str], dict | None]:
        """Run heuristic (non-LLM) fallback analytics."""
        logger.info("Running heuristic analytics (no LLM)")
        motivation = heuristic_motivation(papers)
        confidence = heuristic_confidence(papers)
        market = heuristic_market(papers)
        themes: list[str] = []  # no theme extraction without LLM
        narrative = None
        return motivation, confidence, market, themes, narrative
