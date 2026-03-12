"""Page 4: Proposal Analyzer — novelty & gap analysis."""

from __future__ import annotations

import streamlit as st

from src.ui.api_client import APIClient
from src.ui.components.proposal_report import render_proposal_report


def render(client: APIClient) -> None:
    st.header("📝 Proposal Analyzer")
    st.caption(
        "Paste your research proposal to analyse its novelty against "
        "the existing literature. Requires LLM (Ollama)."
    )

    # Check LLM status
    try:
        status = client.get_status()
        if not status.get("llm_available"):
            st.warning(
                "⚠️ LLM is not available. Start Ollama to enable proposal analysis."
            )
    except Exception:
        pass

    with st.form("proposal_form"):
        proposal_text = st.text_area(
            "Proposal text",
            height=300,
            placeholder="Paste your research proposal abstract or full text here...",
        )
        ref_query = st.text_input(
            "Reference query (optional)",
            placeholder="Filter comparison papers by keyword",
            help="If blank, all papers in the database will be used for comparison.",
        )
        submitted = st.form_submit_button(
            "🔬 Analyse Proposal", use_container_width=True
        )

    if submitted:
        if not proposal_text.strip():
            st.error("Please paste your proposal text.")
            return

        with st.spinner("Analysing proposal... This may take a few minutes."):
            try:
                result = client.analyze_proposal(
                    proposal_text=proposal_text,
                    reference_query=ref_query if ref_query else None,
                )
                st.session_state["proposal_result"] = result
            except Exception as e:
                st.error(f"Analysis failed: {e}")
                return

    # Display results
    result = st.session_state.get("proposal_result")
    if result:
        st.divider()
        render_proposal_report(result)
