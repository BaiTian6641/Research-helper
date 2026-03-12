# 🔬 Research Field Intelligence Tool

A local-first tool that searches academic databases, gathers papers with abstracts, and analyses a research field's **interest**, **motivation**, **confidence**, and **market** dimensions — powered by local LLM (Ollama) for data privacy.

## Features

- **Multi-source search** — Parallel fetching from arXiv, Semantic Scholar, OpenAlex, PubMed, Crossref (+ IEEE/Springer with API keys)
- **Smart deduplication** — 3-stage dedup (DOI → arXiv ID → fuzzy title matching)
- **4-dimension scoring** — Interest (0-100), Motivation (0-100), Confidence (0-100), Market (0-100)
- **LLM-powered analytics** — Theme extraction, motivation classification, confidence detection, market signal extraction, field narrative generation
- **Heuristic fallback** — Works without LLM using regex/NLP when Ollama is unavailable
- **Proposal analyser** — Compare your research proposal against existing literature for novelty/gap analysis
- **Local library** — Import BibTeX, RIS, or CSV files for your own paper collection
- **Interactive dashboard** — Streamlit UI with charts, tables, and drill-down views
- **Export** — CSV, HTML, and PDF report generation

## Architecture

```
┌──────────────┐     ┌──────────────────┐     ┌─────────────┐
│  Streamlit   │────▶│  FastAPI Backend  │────▶│  Ollama LLM │
│  (port 8501) │     │  (port 8000)      │     │  (port 11434)│
└──────────────┘     └──────────────────┘     └─────────────┘
                            │
                     ┌──────┴──────┐
                     │   SQLite    │
                     │  papers.db  │
                     └─────────────┘
```

## Quick Start

### Prerequisites

- Python 3.11+
- [Ollama](https://ollama.com) (recommended, for LLM features)

### 1. Install dependencies

```bash
python -m venv .venv
# Windows
.venv\Scripts\activate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
```

### 2. Setup LLM (recommended)

```bash
# Install Ollama from https://ollama.com
# Pull the default model (17GB, Q4_K_M):
ollama pull jackrong/qwen3.5-27b-claude-4.6-opus-reasoning-distilled

# Or use a smaller fallback:
ollama pull qwq:32b
# or
ollama pull mistral:7b
```

### 3. Run

**One-click launcher:**
```bash
# Windows
start.bat

# Linux/macOS
chmod +x start.sh
./start.sh
```

**Manual:**
```bash
# Terminal 1 — Backend
python -m uvicorn src.api.main:app --host 0.0.0.0 --port 8000

# Terminal 2 — UI
streamlit run src/ui/app.py --server.port 8501
```

### 4. Open

- **UI:** http://localhost:8501
- **API docs:** http://localhost:8000/docs

## Configuration

Edit `config.yaml` or use environment variables (`.env` file):

```yaml
llm:
  default_model: "qwen3.5-reasoning"
  ollama_base_url: "http://localhost:11434"

search:
  timeout_seconds: 60
  max_results_per_source: 200

storage:
  db_path: "papers.db"
  library_db_path: "local_library.db"
```

**API Keys** (optional, for Tier 2 sources):
```
IEEE_API_KEY=your_key_here
SPRINGER_API_KEY=your_key_here
```

## API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/v1/search` | POST | Search databases + run analytics |
| `/api/v1/analyze` | POST | Re-run analytics on stored papers |
| `/api/v1/library` | GET | List/search local library |
| `/api/v1/library/upload` | POST | Upload BibTeX/RIS/CSV |
| `/api/v1/library/{id}` | DELETE | Remove paper from library |
| `/api/v1/proposal` | POST | Analyse research proposal |
| `/api/v1/status` | GET | System health & LLM status |

## Scoring Dimensions

| Dimension | What it measures | Key signals |
|---|---|---|
| **Interest** | Field activity & growth | Paper volume, growth rate, CAGR |
| **Motivation** | Problem urgency | Gap/problem language prevalence in abstracts |
| **Confidence** | Result strength | Strong vs. hedged claims in abstracts |
| **Market** | Industry relevance | Company mentions, funding, patents |

## Project Structure

```
src/
├── api/                  # FastAPI backend
│   ├── main.py           # App entry point
│   ├── schemas.py        # Pydantic models
│   └── routes/           # Route handlers
├── analytics/            # Statistical + LLM analytics
│   ├── pipeline.py       # Unified orchestrator
│   ├── trend.py          # Volume/growth stats
│   ├── citations.py      # Citation metrics
│   ├── venues.py         # Venue/author analysis
│   ├── nlp_fast.py       # TF-IDF & NLP
│   ├── heuristics.py     # Regex fallbacks
│   ├── scores.py         # Dimension score formulas
│   └── proposal_analysis.py
├── config/               # Settings + source registry
├── ingestion/            # BibTeX/RIS/CSV parsers
├── llm/                  # Ollama client + task modules
│   ├── client.py
│   ├── model_registry.py
│   ├── prompts.py
│   └── tasks/
├── reports/              # HTML/PDF/chart exporters
├── searcher/             # Academic database fetchers
│   ├── orchestrator.py
│   ├── arxiv.py
│   ├── semantic_scholar.py
│   ├── openalex.py
│   ├── pubmed.py
│   ├── crossref.py
│   ├── ieee.py
│   └── springer.py
├── storage/              # SQLite CRUD + cache
└── ui/                   # Streamlit app
    ├── app.py
    ├── api_client.py
    ├── components/
    └── pages/
```

## License

MIT
