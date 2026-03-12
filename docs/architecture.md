# System Architecture (Revised)

> **Revision notes:** Added local LLM analytics engine (privacy-preserving, runs fully offline),
> Streamlit web UI layer, local library ingestion, draft proposal analysis module,
> and a more explicit quantitative output specification.

---

## 1. High-Level Component Diagram

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                           USER INTERFACE LAYER                               ║
║                                                                              ║
║   ┌───────────────────────┐          ┌────────────────────────────────────┐  ║
║   │  Streamlit Web App    │          │  FastAPI REST Backend              │  ║
║   │  (primary UI)         │◄────────►│  /api/v1/search                   │  ║
║   │  - Search panel       │          │  /api/v1/analyze                  │  ║
║   │  - Dashboard charts   │          │  /api/v1/library                  │  ║
║   │  - Library browser    │          │  /api/v1/proposal                 │  ║
║   │  - Proposal upload    │          └────────────────────────────────────┘  ║
║   └───────────────────────┘                                                  ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
        ┌───────────────────┐ ┌──────────────────┐ ┌───────────────────┐
        │  Search           │ │  Local Library   │ │  Proposal         │
        │  Orchestrator     │ │  Ingestion       │ │  Analyzer         │
        │                   │ │                  │ │                   │
        │  Parallel async   │ │  PDF / BibTeX /  │ │  Compares draft  │
        │  fetchers         │ │  RIS / CSV       │ │  vs. field DB    │
        └────────┬──────────┘ └────────┬─────────┘ └────────┬──────────┘
                 │                     │                     │
                 └─────────────────────┼─────────────────────┘
                                       │  normalised Paper records
                                       ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                             STORAGE LAYER                                    ║
║                                                                              ║
║   papers.db (SQLite)    papers.csv    local_library.db    .cache/            ║
╚══════════════════════════════════════════════════════════════════════════════╝
                                       │
                    ┌──────────────────┼──────────────────┐
                    │                  │                  │
                    ▼                  ▼                  ▼
        ┌───────────────────┐ ┌──────────────────┐ ┌────────────────────┐
        │  Statistical      │ │  Local LLM       │ │  Score             │
        │  Analyzer         │ │  Engine          │ │  Calculator        │
        │                   │ │                  │ │                    │
        │  Trend, citation  │ │  Ollama runtime  │ │  Interest          │
        │  venue, author,   │ │  Qwen2.5 / QwQ / │ │  Motivation        │
        │  volume metrics   │ │  DeepSeek-R1 /   │ │  Confidence        │
        │                   │ │  Mistral (local) │ │  Market Interest   │
        └─────────┬─────────┘ └────────┬─────────┘ └────────┬───────────┘
                  │                    │                     │
                  └────────────────────┼─────────────────────┘
                                       │  analytics results
                                       ▼
╔══════════════════════════════════════════════════════════════════════════════╗
║                           REPORT GENERATOR                                   ║
║                                                                              ║
║   StreamlitDashboard    HTMLExport    CSVExport    PDFExport                 ║
╚══════════════════════════════════════════════════════════════════════════════╝
```


---

## 2. Layer Descriptions

### 2.1 User Interface Layer

**Primary UI: Streamlit web app** (runs locally at `http://localhost:8501`)

Pages / tabs:

| Tab | Purpose |
|---|---|
| **Search** | Enter keywords, date range, filters; trigger search across databases |
| **Dashboard** | Interactive charts: paper volume/year, citation heatmap, venue/author tables, 4-dimension score cards |
| **Library** | Browse and search locally ingested papers (your own PDF collections) |
| **Proposal Analyzer** | Upload a draft proposal PDF or paste text; compare against the research field database |
| **Settings** | Configure API keys, local LLM model selection, database paths |

**FastAPI backend** handles all heavy computation and is served separately so the UI
remains responsive. Streamlit calls it via `httpx` async requests.

---

### 2.2 Search Orchestrator

Unchanged in responsibility but reinforced with:
- Circuit-breaker per source (disable after 3 consecutive failures in a session)
- Progress SSE stream back to FastAPI → Streamlit live progress bar
- Configurable source priority order for deduplication trust ranking

---

### 2.3 Local Library Ingestion

Allows the user to point the tool at a local folder of paper files so they can be
analysed alongside (or instead of) API-fetched papers.

Supported input formats:
- **PDF** — extracted via `pdfplumber`; title/authors parsed from first page or embedded metadata
- **BibTeX** (`.bib`) — direct field mapping
- **RIS** (`.ris`) — standard reference format used by Zotero, Mendeley, EndNote
- **CSV** — user-exported spreadsheet from any reference manager
- **Markdown / TXT** — plain abstract text files

All ingested records are stored in `local_library.db` and tagged `source = "local"`.
They participate fully in analytics unless explicitly excluded.

---

### 2.4 Proposal Analyzer

Takes a **draft research proposal** and produces a gap/alignment report against the
current field database.

**Inputs accepted:**
- PDF upload (Streamlit file uploader)
- Pasted plain text
- Markdown / DOCX (via `python-docx`)

**Analysis steps:**

```
1. Extract proposal text (PDF → pdfplumber, DOCX → python-docx)
2. LLM Engine: extract proposed claims, methods, objectives (structured JSON)
3. Embed proposal sentences → compare cosine similarity vs. paper abstracts
4. Identify: overlapping prior work | genuine novelty gaps | missing citations
5. Cross-reference with Interest/Motivation/Confidence scores of the field
6. Generate: similarity heatmap | gap analysis table | recommended citations
```

**Output:**
- Novelty score (0–100): how differentiated the proposal is from existing work
- Overlap table: top-10 most similar existing papers with similarity %
- Gap analysis: research questions in the proposal not addressed by existing literature
- Recommended additions: papers the proposal should cite but doesn't

---

### 2.5 Local LLM Engine

All LLM inference runs **100% locally** via [Ollama](https://ollama.com) to ensure
data privacy — no abstracts, proposals, or user queries leave the machine.

#### Supported Models (Ollama pull names)

| Model | Size (approx.) | Best for | VRAM required |
|---|---|---|---|
| `qwen2.5:14b` | ~9 GB | Balanced reasoning + speed | 10 GB |
| `qwen2.5:32b` | ~20 GB | Highest quality analysis | 24 GB |
| `qwq:32b` | ~20 GB | Chain-of-thought reasoning tasks | 24 GB |
| `deepseek-r1:14b` | ~9 GB | Reasoning / gap analysis | 10 GB |
| `deepseek-r1:32b` | ~20 GB | Deep reasoning, proposal critique | 24 GB |
| `mistral:7b` | ~4.1 GB | Fast summaries, low VRAM | 6 GB |
| `phi4:14b` | ~9 GB | Structured JSON extraction | 10 GB |
| ★ `Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled` | ~17 GB | **Recommended for deep reasoning tasks** | 20 GB |

> **Note on distilled reasoning models:** Models like DeepSeek-R1-Distill-Qwen-32B
> (which distil reasoning capability from larger frontier models into a locally-runnable
> weight) are explicitly supported and recommended for the Proposal Analyzer and
> Motivation/Confidence analysis tasks. Any GGUF-compatible model can be added via
> Ollama's `Modelfile`.

> **★ Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled** — A community
> reasoning-distilled model that merges Qwen3.5-27B weights with reasoning patterns
> distilled from Claude Opus 4.6. It runs locally via Ollama (load the GGUF from
> Hugging Face: `Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled`).
> At ~27B parameters with chain-of-thought capability, it is the **recommended default**
> for the Proposal Analyzer's novelty-gap analysis and for generating the field
> narrative summary. Its reasoning traces also make it straightforward to audit
> *why* a particular gap or overlap was identified — important for research integrity.
> Load into Ollama with a custom `Modelfile` pointing at the downloaded GGUF:
> ```
> FROM ./Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled.Q4_K_M.gguf
> PARAMETER num_ctx 8192
> ```
> Then `ollama create qwen3.5-reasoning -f Modelfile` and select
> `qwen3.5-reasoning` in the Settings tab.

**CPU fallback:** If no GPU is available, `mistral:7b` or `qwen2.5:7b` run acceptably
on modern CPUs (~2–10 min per analysis on 16-core machines).

#### LLM Task Assignments

| Task | Prompt strategy | Model tier |
|---|---|---|
| Abstract theme extraction | Structured JSON output | 7B–14B |
| Motivation sentence classification | Few-shot classification | 7B–14B |
| Confidence / hedging detection | Few-shot classification | 7B–14B |
| Market signal extraction (industry, funder) | NER-style structured output | 14B |
| Proposal claim extraction | Chain-of-thought | 14B–32B |
| Novelty gap analysis | Reasoning + retrieval | 32B / QwQ / DeepSeek-R1 |
| Research trend narrative summary | Open-ended generation | 14B–32B |

#### LLM Interface Module (`llm/`)

```python
class LLMClient:
    """Thin wrapper around the Ollama HTTP API."""
    def __init__(self, model: str, base_url: str = "http://localhost:11434")
    async def complete(self, prompt: str, schema: dict | None = None) -> str
    async def complete_json(self, prompt: str, schema: dict) -> dict
    def list_models(self) -> list[str]
```

`schema` uses JSON Schema to enforce structured output (Ollama's `format` parameter).

---

## 3. Module Breakdown

```
research-stats-tool/
│
├── docs/                          ← planning documents
│
├── src/
│   │
│   ├── ui/                        ← Streamlit frontend
│   │   ├── app.py                 ← entry point: streamlit run ui/app.py
│   │   ├── pages/
│   │   │   ├── 01_search.py
│   │   │   ├── 02_dashboard.py
│   │   │   ├── 03_library.py
│   │   │   └── 04_proposal.py
│   │   ├── components/
│   │   │   ├── score_card.py      ← 4-dimension score card widget
│   │   │   ├── trend_chart.py     ← Plotly time series
│   │   │   ├── venue_table.py
│   │   │   └── proposal_report.py
│   │   └── api_client.py          ← httpx calls to FastAPI backend
│   │
│   ├── api/                       ← FastAPI backend
│   │   ├── main.py                ← FastAPI app, CORS, startup
│   │   ├── routes/
│   │   │   ├── search.py          ← POST /api/v1/search
│   │   │   ├── analyze.py         ← POST /api/v1/analyze
│   │   │   ├── library.py         ← GET/POST /api/v1/library
│   │   │   └── proposal.py        ← POST /api/v1/proposal
│   │   └── schemas.py             ← Pydantic request/response models
│   │
│   ├── searcher/                  ← external API fetchers
│   │   ├── base.py
│   │   ├── arxiv.py
│   │   ├── semantic_scholar.py
│   │   ├── openalex.py
│   │   ├── pubmed.py
│   │   ├── crossref.py
│   │   ├── ieee.py
│   │   ├── springer.py
│   │   └── orchestrator.py
│   │
│   ├── ingestion/                 ← local file ingestion
│   │   ├── pdf_parser.py          ← pdfplumber + metadata extraction
│   │   ├── bibtex_parser.py
│   │   ├── ris_parser.py
│   │   ├── csv_parser.py
│   │   └── ingestion_service.py   ← routes file to correct parser
│   │
│   ├── storage/
│   │   ├── models.py              ← Paper, Session, ProposalAnalysis dataclasses + ORM
│   │   ├── sqlite_store.py
│   │   ├── library_store.py       ← local_library.db CRUD
│   │   ├── csv_exporter.py
│   │   └── cache.py
│   │
│   ├── llm/                       ← local LLM engine
│   │   ├── client.py              ← Ollama HTTP wrapper
│   │   ├── prompts.py             ← all prompt templates
│   │   ├── tasks/
│   │   │   ├── theme_extractor.py
│   │   │   ├── motivation_classifier.py
│   │   │   ├── confidence_detector.py
│   │   │   ├── market_extractor.py
│   │   │   ├── proposal_parser.py
│   │   │   └── gap_analyzer.py
│   │   └── model_registry.py      ← available models + capability tags
│   │
│   ├── analytics/
│   │   ├── trend.py               ← paper count / year, YoY growth rate, CAGR
│   │   ├── citations.py           ← citation velocity, h-index estimate
│   │   ├── venues.py              ← top venues, top authors, country distribution
│   │   ├── nlp_fast.py            ← spaCy pipeline (no LLM; TF-IDF, NER)
│   │   ├── scores.py              ← Interest / Motivation / Confidence / Market
│   │   └── proposal_analysis.py   ← cosine similarity + gap computation
│   │
│   ├── reports/
│   │   ├── html_exporter.py       ← standalone HTML dashboard (Jinja2 + Plotly)
│   │   ├── pdf_exporter.py        ← WeasyPrint PDF
│   │   ├── csv_exporter.py
│   │   └── charts.py              ← Plotly figure builders (shared by UI + export)
│   │
│   └── config/
│       ├── settings.py            ← pydantic-settings, loads .env
│       └── sources.py             ← source registry
│
├── tests/
│   ├── test_searcher/
│   ├── test_ingestion/
│   ├── test_analytics/
│   ├── test_llm/
│   └── test_api/
│
├── .env.example
├── config.yaml                    ← user-editable defaults
├── start.bat                      ← Windows: launches backend + UI together
├── start.sh                       ← Unix: launches backend + UI together
├── requirements.txt
├── requirements-llm.txt           ← optional heavy deps (sentence-transformers)
└── README.md
```

---

## 4. Data Model

```python
@dataclass
class Paper:
    # Identity
    id: str                        # SHA-256 of doi or (title + year)
    doi: str | None
    arxiv_id: str | None
    pmid: str | None

    # Bibliographic
    title: str
    authors: list[str]             # ["Last, First", ...]
    year: int | None
    venue: str | None              # journal or conference
    venue_type: str | None         # "journal" | "conference" | "preprint" | "workshop"

    # Content
    abstract: str | None
    keywords: list[str]

    # Metrics
    citations: int | None
    citation_velocity: float | None  # citations / (current_year - year + 1)
    influential_citations: int | None

    # Source tracking
    sources: list[str]             # ["arxiv", "semantic_scholar", ...]
    url: str | None
    fetched_at: datetime
    is_local: bool                 # True if ingested from local library

    # LLM-derived fields (populated after analytics run)
    themes: list[str] | None
    motivation_sentences: list[str] | None
    confidence_label: str | None   # "strong" | "moderate" | "hedged" | "negative"
    industry_affiliated: bool | None
    funder_names: list[str] | None


@dataclass
class ProposalAnalysis:
    id: str
    proposal_text: str
    run_at: datetime
    novelty_score: float           # 0–100
    top_overlapping_papers: list[tuple[str, float]]  # (paper_id, similarity %)
    gap_clusters: list[str]        # identified research gaps
    recommended_citations: list[str]  # paper_ids
    llm_narrative: str             # free-text LLM summary


@dataclass
class FieldStats:
    """Primary quantitative output — one instance per search session."""
    query: str
    year_range: tuple[int, int]

    # Volume
    total_papers: int
    review_papers: int             # title/type contains "review", "survey", "meta-analysis"
    papers_per_year: dict[int, int]
    growth_rate_pct: float         # (last 2yr count - prev 2yr count) / prev 2yr count
    cagr_pct: float                # compound annual growth rate over full range

    # Citations
    cumulative_citations: int
    avg_citation_velocity: float
    median_citations: float
    h_index_estimate: int
    top_cited_papers: list[tuple[str, int]]  # (title, citations)

    # Structure
    top_venues: list[tuple[str, int]]
    top_authors: list[tuple[str, int]]
    country_distribution: dict[str, int]
    industry_ratio: float          # 0.0–1.0

    # Dimension scores (0–100)
    interest_score: float
    motivation_score: float
    confidence_score: float
    market_score: float

    # LLM outputs (None if LLM not available)
    top_themes: list[str] | None
    top_funders: list[tuple[str, int]] | None
    field_narrative: str | None
    maturity_label: str | None     # "Emerging" | "Growing" | "Established" | "Saturating"
```

---

## 5. Quantitative Output Specification

Every search session produces the following mandatory outputs:

### 5.1 Volume Metrics

| Metric | Description |
|---|---|
| **Total papers found** | Deduplicated record count in date range |
| **Review / survey papers** | Subset matching "review", "survey", "systematic review", "meta-analysis" in title or type field |
| **Papers per year** | Time-series table: `year → count` |
| **YoY growth rate** | `(count[last 2yr] − count[prev 2yr]) / count[prev 2yr] × 100%` |
| **CAGR** | Compound annual growth rate across full date range |

### 5.2 Citation Metrics

| Metric | Description |
|---|---|
| **Total citations** | Sum across all papers |
| **Median citations** | Robust central tendency |
| **Average citation velocity** | Mean of `citations / age` per paper |
| **H-index estimate** | Virtual h-index for the keyword-defined paper set |
| **Top 10 most cited** | Title + citation count + year |

### 5.3 Structural Metrics

| Metric | Description |
|---|---|
| **Top 10 venues** | Venue name + paper count |
| **Top 20 authors** | Name + paper count + affiliation |
| **Country distribution** | Country → paper count (OpenAlex institution data) |
| **Industry vs. academia ratio** | % papers with at least one industry co-author |

### 5.4 Intelligence Scores (0–100)

| Score | Computation method |
|---|---|
| **Interest** | Volume + growth rate + citation velocity (statistical, no LLM) |
| **Motivation** | LLM classification of problem-framing sentences in abstracts |
| **Confidence** | LLM detection of claim strength (strong / hedged / negative) |
| **Market Interest** | Industry ratio + funder count + patent language signals |

### 5.5 LLM Narrative Report (optional; requires Ollama)

- 3–5 paragraph field summary
- Top motivation themes (bulleted list)
- Maturity label: **Emerging / Growing / Established / Saturating**
- Open research questions identified from abstract corpus

---

## 6. UI Screen Sketches

### Search Tab
```
┌─ Research Field Intelligence ─────────────────────────────────────────────────┐
│  Keywords:   [federated learning privacy                        ]  [🔍 Search] │
│  Year range: [2015] – [2025]    Min citations: [5]   Max results/source: [200] │
│  Sources: ☑ arXiv  ☑ Semantic Scholar  ☑ OpenAlex  ☑ PubMed  ☑ Crossref      │
│           □ IEEE (API key required)    □ Springer (API key required)           │
│  ─────────────────────────────────────────────────────────────────────────    │
│  [▶ Run Search]   [↺ Load from cache]   [📂 Import local files / folder]       │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Dashboard Tab
```
┌─ "federated learning privacy"  (2015–2025) ───────────────────────────────────┐
│  4,382 total papers  ·  1,147 review/survey papers  ·  6 sources  ·  YoY +34% │
│                                                                                │
│  ┌── Papers per Year ────────────────────────────────────────────────────────┐ │
│  │  500 ┤                                                     ████           │ │
│  │  400 ┤                                          ████  ████ ████           │ │
│  │  300 ┤                               ████  ████ ████  ████ ████           │ │
│  │  200 ┤               ████  ████ ████ ████  ████ ████  ████ ████           │ │
│  │    0 └──────────────────────────────────────────────────────────────       │ │
│  │        2015  2016  2017  2018  2019  2020  2021  2022  2023  2024          │ │
│  └────────────────────────────────────────────────────────────────────────── ┘ │
│                                                                                │
│  ┌── Dimension Scores ────────────────────────────────────────────────────── ┐ │
│  │  Interest        ████████████████░░  82 / 100                             │ │
│  │  Motivation      ████████████░░░░░░  63 / 100                             │ │
│  │  Confidence      ██████████████░░░░  71 / 100                             │ │
│  │  Market Interest █████████░░░░░░░░░  47 / 100                             │ │
│  └────────────────────────────────────────────────────────────────────────── ┘ │
│                                                                                │
│  [Export CSV]  [Export HTML Report]  [Export PDF]  [→ Analyze a Proposal]     │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Library Tab
```
┌─ Local Library ───────────────────────────────────────────────────────────────┐
│  [📁 Import folder]  [📄 Import file]  Search library: [____________]          │
│  ─────────────────────────────────────────────────────────────────────────    │
│  Showing 312 local papers  ·  Formats: PDF (289), BibTeX (23)                 │
│                                                                                │
│  Title                          Year  Authors          Citations  Source       │
│  ─────────────────────────────  ────  ───────────────  ─────────  ──────────  │
│  Privacy in Federated ML…       2023  Wang, Li, …       412       local/PDF   │
│  …                                                                             │
│                                                                                │
│  [☑ Include local papers in next analysis]                                     │
└───────────────────────────────────────────────────────────────────────────────┘
```

### Proposal Analyzer Tab
```
┌─ Proposal Analyzer ───────────────────────────────────────────────────────────┐
│  Upload:  [📄 Drop PDF / DOCX / TXT here]    — or paste text below —          │
│  ┌──────────────────────────────────────────────────────────────────────────┐ │
│  │  (text area for draft proposal)                                          │ │
│  └──────────────────────────────────────────────────────────────────────────┘ │
│  LLM model: [qwq:32b ▼]   Compare against: [current search results ▼]        │
│  [▶ Analyze Proposal]                                                          │
│  ─────────────────────────────────────────────────────────────────────────    │
│  RESULTS                                                                       │
│  Novelty score:      73 / 100  ██████████████░░░░░                            │
│  Overlap detected:   12 papers above 70% similarity  →  [View overlap table]  │
│  Research gaps:      4 identified                    →  [View gap analysis]   │
│  Recommended cites:  8 papers                        →  [Add to library]      │
│  LLM narrative:      [▼ expand]                                               │
└───────────────────────────────────────────────────────────────────────────────┘
```

---

## 7. Technology Stack

| Layer | Choice | Rationale |
|---|---|---|
| Language | Python 3.11+ | Rich scientific ecosystem |
| Web UI | `Streamlit` | Python-native dashboard, no JavaScript build step |
| API backend | `FastAPI` + `uvicorn` | Async, typed, auto OpenAPI docs |
| Async I/O | `asyncio` + `httpx` | Parallel API queries |
| PDF parsing | `pdfplumber` + `pypdf` | Text + metadata extraction |
| BibTeX / RIS | `bibtexparser` + `rispy` | Reference format parsers |
| DOCX parsing | `python-docx` | Proposal document support |
| Storage | `SQLite` via `SQLAlchemy 2` | Zero-install, portable |
| Schema validation | `pydantic v2` | Data model + API contract |
| NLP (fast, offline) | `spaCy` + `scikit-learn` | TF-IDF, NER, clustering |
| Semantic embeddings | `sentence-transformers` (local) | Proposal similarity scoring |
| LLM runtime | `Ollama` (local HTTP server) | Privacy-preserving, GPU/CPU, hot-swap models |
| Charts | `Plotly` | Interactive in Streamlit; PNG export for reports |
| HTML export | `Jinja2` + embedded Plotly | Self-contained HTML dashboard |
| PDF export | `WeasyPrint` | HTML → PDF, no external tools |
| Config | `pydantic-settings` + `.env` | Typed settings with env-var override |
| Testing | `pytest` + `pytest-asyncio` | Async-aware test suite |

---

## 8. Startup

```bash
# 1. Install Ollama and pull a model
ollama pull qwen2.5:14b           # recommended default

# 2. Install Python dependencies
pip install -r requirements.txt

# 3. Configure
cp .env.example .env              # add optional API keys

# 4. Launch (Windows)
start.bat

# 4. Launch (Unix / macOS)
./start.sh

# start.bat / start.sh does:
#   uvicorn src.api.main:app --port 8000  (background)
#   streamlit run src/ui/app.py           (foreground)
#   → open http://localhost:8501
```

---

## 9. Privacy & Security

| Concern | Mitigation |
|---|---|
| Paper abstracts / proposals leaving the machine | All LLM inference via local Ollama; zero external LLM API calls |
| API keys exposed | Keys in `.env` only; `.env` listed in `.gitignore`; never logged |
| Scraping ToS violations | Only official public APIs used; scraping disabled by default |
| Uploaded proposal file storage | Processed in-memory; not written to disk unless user explicitly saves |
| SQLite file permissions | Tool sets file to user-read-only on creation (platform-appropriate) |

