"""Page 5: Settings — system configuration and status."""

from __future__ import annotations

import streamlit as st

from src.ui.api_client import APIClient


def render(client: APIClient) -> None:
    st.header("⚙️ Settings & Status")

    # System status
    st.subheader("System Status")
    try:
        status = client.get_status()
        col1, col2, col3 = st.columns(3)
        with col1:
            llm_ok = status.get("llm_available", False)
            st.metric("LLM Status", "✅ Online" if llm_ok else "❌ Offline")
            if llm_ok:
                st.caption(f"Model: {status.get('model_name', 'N/A')}")
        with col2:
            st.metric("Papers in DB", status.get("paper_count", 0))
        with col3:
            st.metric("Library Papers", status.get("library_count", 0))

        # Hardware info
        hw = status.get("hardware")
        if hw:
            st.subheader("Hardware Detection")
            hcol1, hcol2, hcol3 = st.columns(3)
            with hcol1:
                st.metric("System RAM", f"{hw.get('ram_gb', 0):.1f} GB")
            with hcol2:
                gpus = hw.get("gpus", [])
                if gpus:
                    best = max(gpus, key=lambda g: g.get("vram_gb", 0))
                    st.metric("GPU VRAM", f"{best.get('vram_gb', 0):.1f} GB")
                    st.caption(best.get("name", "Unknown GPU"))
                else:
                    st.metric("GPU VRAM", "N/A")
                    st.caption("No GPU detected")
            with hcol3:
                capable = hw.get("llm_capable", False)
                st.metric("LLM Capable", "✅ Yes" if capable else "❌ No")
            st.caption(hw.get("reason", ""))

        # Available models
        models = status.get("models_available", [])
        if models:
            st.subheader("Installed Ollama Models")
            for m in models:
                st.write(f"- `{m}`")
        elif llm_ok:
            st.info("No models detected.")
    except Exception as e:
        st.error(f"Cannot connect to backend: {e}")
        st.info(
            "Make sure the FastAPI backend is running:\n\n"
            "```\npython -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000\n```"
        )

    st.divider()

    # Configuration info
    st.subheader("Configuration")
    st.markdown(
        """
        **Backend URL:** `http://localhost:8000`

        **Config file:** `config.yaml` (project root)

        **Environment:** `.env` file for API keys

        **LLM Setup:**
        1. Install [Ollama](https://ollama.com)
        2. Pull the default model:
           ```
           ollama pull qwen3.5-reasoning
           ```
        3. Or use any compatible model from the fallback list

        **API Keys (optional, for Tier 2 sources):**
        - `IEEE_API_KEY` — IEEE Xplore
        - `SPRINGER_API_KEY` — Springer Nature
        """
    )
