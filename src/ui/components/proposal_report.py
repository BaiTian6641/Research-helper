"""Proposal report component — renders proposal analysis results."""

from __future__ import annotations

import streamlit as st


def render_proposal_report(result: dict) -> None:
    """Render the full proposal analysis report."""
    novelty = result.get("novelty_score", 0)

    # Header with novelty score
    st.subheader("Proposal Analysis Results")
    col1, col2 = st.columns([1, 3])
    with col1:
        st.metric("Novelty Score", f"{novelty:.0f}/100")
        st.progress(novelty / 100)
    with col2:
        label = _novelty_label(novelty)
        st.markdown(f"**Assessment:** {label}")

    st.divider()

    # Narrative
    narrative = result.get("narrative")
    if narrative:
        st.markdown(narrative)
        st.divider()

    # Overlapping papers
    overlaps = result.get("overlapping_papers", [])
    if overlaps:
        st.subheader(f"Overlapping Work ({len(overlaps)})")
        for o in overlaps:
            with st.expander(o.get("claim", "Claim")[:80]):
                similar = o.get("similar_papers", [])
                st.write(f"**Similar papers:** {', '.join(similar[:5])}")
                st.write(f"**Note:** {o.get('similarity_note', 'N/A')}")

    # Gap clusters
    gaps = result.get("gap_clusters", [])
    if gaps:
        st.subheader(f"Novel Contributions / Gaps ({len(gaps)})")
        for g in gaps:
            st.markdown(f"- {g}")

    # Recommended citations
    recs = result.get("recommended_citations", [])
    if recs:
        st.subheader(f"Recommended Citations ({len(recs)})")
        for r in recs:
            st.markdown(f"- {r}")


def _novelty_label(score: float) -> str:
    if score >= 80:
        return "🟢 Highly novel — limited overlap with existing literature"
    elif score >= 60:
        return "🟡 Moderately novel — some overlap but unique contributions"
    elif score >= 40:
        return "🟠 Moderate overlap — consider differentiating more clearly"
    else:
        return "🔴 Significant overlap — substantial related work exists"
