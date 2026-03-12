"""Score card component — renders all dimension scores + sentiment."""

from __future__ import annotations

import streamlit as st


def render_score_cards(stats: dict) -> None:
    """Render the comprehensive score prominently, then dimension scores."""

    # --- Comprehensive score banner ---
    comprehensive = stats.get("comprehensive_score", 0)
    colour = _score_colour(comprehensive)
    st.markdown(
        f"### 🏆 Comprehensive Score: **{comprehensive:.0f}/100** {colour}"
    )
    st.progress(comprehensive / 100)
    st.divider()

    # --- Individual dimension scores (3+3 layout) ---
    row1 = st.columns(3)
    row2 = st.columns(3)

    scores_row1 = [
        ("Interest", stats.get("interest_score", 0), "Publication volume & growth"),
        ("Motivation", stats.get("motivation_score", 0), "Problem-statement prevalence"),
        ("Confidence", stats.get("confidence_score", 0), "Claim strength + public trust"),
    ]
    scores_row2 = [
        ("Market", stats.get("market_score", 0), "Industry, funding & news buzz"),
        ("Public Sentiment", stats.get("public_sentiment_score", 0), "Attitude from news & web (50=neutral)"),
        ("News Articles", stats.get("news_article_count", 0), "Number of news/web articles found"),
    ]

    for col, (label, value, help_text) in zip(row1, scores_row1):
        with col:
            st.metric(label=label, value=f"{value:.0f}/100", help=help_text)
            st.progress(value / 100)
            st.caption(_score_colour(value))

    for col, (label, value, help_text) in zip(row2, scores_row2):
        with col:
            if label == "News Articles":
                st.metric(label=label, value=str(int(value)), help=help_text)
            else:
                st.metric(label=label, value=f"{value:.0f}/100", help=help_text)
                st.progress(value / 100)
                st.caption(_score_colour(value))


def render_sentiment_details(stats: dict) -> None:
    """Render positive / negative sentiment breakdown."""
    pos_ratio = stats.get("sentiment_positive_ratio", 0)
    neg_ratio = stats.get("sentiment_negative_ratio", 0)
    neutral_ratio = max(0, 1.0 - pos_ratio - neg_ratio)

    st.subheader("💬 Sentiment Breakdown")
    c1, c2, c3 = st.columns(3)
    c1.metric("👍 Positive", f"{pos_ratio:.0%}")
    c2.metric("😐 Neutral", f"{neutral_ratio:.0%}")
    c3.metric("👎 Negative", f"{neg_ratio:.0%}")

    # Sample sentences
    pos_samples = stats.get("sentiment_positive_samples", [])
    neg_samples = stats.get("sentiment_negative_samples", [])

    if pos_samples:
        with st.expander("🟢 Positive sentiment samples", expanded=False):
            for s in pos_samples[:5]:
                st.markdown(f"- {s}")
    if neg_samples:
        with st.expander("🔴 Negative sentiment samples", expanded=False):
            for s in neg_samples[:5]:
                st.markdown(f"- {s}")


def _score_colour(value: float) -> str:
    if value >= 75:
        return "🟢 High"
    elif value >= 50:
        return "🟡 Moderate"
    elif value >= 25:
        return "🟠 Low"
    else:
        return "🔴 Very Low"
