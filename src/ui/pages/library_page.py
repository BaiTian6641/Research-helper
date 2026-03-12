"""Page 3: Library — manage local paper collection."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from src.ui.api_client import APIClient


def render(client: APIClient) -> None:
    st.header("📚 Local Library")

    # Upload section
    st.subheader("Upload Papers")
    uploaded = st.file_uploader(
        "Upload BibTeX (.bib), RIS (.ris), or CSV (.csv)",
        type=["bib", "ris", "csv"],
    )
    if uploaded:
        if st.button("📤 Import", use_container_width=True):
            with st.spinner("Parsing and importing..."):
                try:
                    result = client.upload_to_library(
                        uploaded.name, uploaded.getvalue()
                    )
                    st.success(f"Imported {result['added']} papers from {result['filename']}")
                    st.rerun()
                except Exception as e:
                    st.error(f"Import failed: {e}")

    st.divider()

    # Search / Browse
    search_term = st.text_input("🔍 Search library", placeholder="Filter by title keyword...")

    try:
        papers = client.get_library(search=search_term if search_term else None)
    except Exception as e:
        st.error(f"Could not load library: {e}")
        return

    if not papers:
        st.info("Library is empty. Upload papers above.")
        return

    st.caption(f"{len(papers)} papers in library")

    # Table
    df = pd.DataFrame(papers)
    display_cols = ["title", "authors", "year", "venue", "doi"]
    available = [c for c in display_cols if c in df.columns]
    st.dataframe(df[available], use_container_width=True, hide_index=True)

    # Delete single paper
    with st.expander("🗑️ Delete a paper"):
        paper_ids = {p.get("title", p["id"])[:60]: p["id"] for p in papers}
        selected = st.selectbox("Select paper to delete", list(paper_ids.keys()))
        if st.button("Delete", type="secondary"):
            try:
                client.delete_from_library(paper_ids[selected])
                st.success("Deleted.")
                st.rerun()
            except Exception as e:
                st.error(f"Delete failed: {e}")
