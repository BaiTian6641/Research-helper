# Requirements

## 1. Functional Requirements

### 1.1 Search & Data Collection

| ID | Requirement |
|---|---|
| FR-01 | User can provide one or more keyword strings as input |
| FR-02 | User can specify date range (e.g., 2015–2025) |
| FR-03 | User can specify minimum citation count filter |
| FR-04 | User can select which databases to query (default: all) |
| FR-05 | Tool queries at least 5 academic databases per search |
| FR-06 | Tool retrieves: title, authors, year, abstract, venue, DOI, citation count, URL |
| FR-07 | Results from all sources are merged and deduplicated |
| FR-08 | Tool handles API rate limits gracefully with retry/backoff |
| FR-09 | User can set a maximum result limit per source (default: 200) |

### 1.2 Storage

| ID | Requirement |
|---|---|
| FR-10 | Results are saved to a CSV file per search session |
| FR-11 | Results are persisted in a local SQLite database for cross-session analysis |
| FR-12 | Each search session is recorded with timestamp, query, and source counts |
| FR-13 | Previously fetched data can be reloaded without re-querying APIs |

### 1.3 Analytics

| ID | Requirement |
|---|---|
| FR-14 | Publication count per year (trend chart data) |
| FR-15 | Citation velocity: total citations / years since publication |
| FR-16 | Top 10 venues / conferences by paper count |
| FR-17 | Top 20 authors by paper count |
| FR-18 | Abstract NLP: most frequent unigrams, bigrams, trigrams |
| FR-19 | Interest score computed from trend slope + volume |
| FR-20 | Motivation analysis: sentences starting with problem-framing language |
| FR-21 | Confidence score from abstract claim language detection |
| FR-22 | Market interest score from industry affiliation + funding mention detection |

### 1.4 Local Library

| ID | Requirement |
|---|---|
| FR-23 | User can import local paper files (PDF, BibTeX, RIS, CSV, TXT) |
| FR-24 | User can point the tool at a folder to batch-import papers |
| FR-25 | Imported papers are stored in a local library database tagged `source = "local"` |
| FR-26 | Local papers participate in analytics alongside API-fetched papers |
| FR-27 | User can browse, search, and delete local library entries from the UI |

### 1.5 Local LLM Engine

| ID | Requirement |
|---|---|
| FR-28 | All LLM inference runs locally via Ollama — no data sent to external services |
| FR-29 | User can select which Ollama model to use from a Settings page |
| FR-30 | LLM is used for: abstract theme extraction, motivation classification, confidence detection, market signal extraction |
| FR-31 | If no LLM is available, analytics fall back to heuristic NLP (spaCy / regex) |

### 1.6 Proposal Analyzer

| ID | Requirement |
|---|---|
| FR-32 | User can upload a draft research proposal (PDF, DOCX, or plain text) |
| FR-33 | The tool extracts claims, objectives, and methods from the proposal via local LLM |
| FR-34 | Proposal sentences are compared against field paper abstracts via cosine similarity |
| FR-35 | Output: novelty score (0–100), overlap table, gap analysis, recommended citations |

### 1.7 User Interface

| ID | Requirement |
|---|---|
| FR-36 | Streamlit web app served at `localhost:8501` |
| FR-37 | Tabs: Search, Dashboard, Library, Proposal Analyzer, Settings |
| FR-38 | Dashboard shows interactive Plotly charts (trend, citations, venues, scores) |
| FR-39 | Live progress bar during search via SSE from FastAPI backend |

### 1.8 Reporting

| ID | Requirement |
|---|---|
| FR-40 | Dimension scores and summary metrics displayed on Dashboard tab |
| FR-41 | Optional: export a standalone HTML report with embedded charts |
| FR-42 | Optional: export a PDF report |
| FR-43 | CSV export of the full paper dataset |

---

## 2. Non-Functional Requirements

| ID | Requirement |
|---|---|
| NFR-01 | All database queries run in parallel (async or thread pool) |
| NFR-02 | A search returning 1,000 results must complete within 60 seconds |
| NFR-03 | The tool must run on Windows, macOS, and Linux |
| NFR-04 | API keys are stored in a local `.env` file and never hard-coded |
| NFR-05 | No API key should be required for the minimum viable search (free APIs only) |
| NFR-06 | Abstract text is stored verbatim; no PII is collected |
| NFR-07 | The tool must work offline if a cached database already exists |
| NFR-08 | All LLM inference must run locally (Ollama); no external LLM API calls |
| NFR-09 | The Streamlit UI and FastAPI backend launch together via a single start script |

---

## 3. Constraints & Assumptions

- The tool is for **personal research and analysis**, not bulk redistribution of papers.
- Rate limits of each database API must be respected.
- Full-text PDF retrieval is **out of scope** for Phase 1.
- Machine translation of non-English abstracts is **out of scope** for Phase 1.
- The confidence and motivation scores are **heuristic / NLP-based approximations** (or LLM-based when available), not ground truth.
- Ollama must be installed separately for LLM features; the tool degrades gracefully without it.

---

## 4. Input Specification

```
# Minimal input
Keywords: "federated learning privacy"

# Extended input (all optional fields)
Keywords:       "federated learning privacy"
Date range:     2018 to 2025
Min citations:  5
Max results:    500 (per source)
Sources:        arXiv, Semantic Scholar, OpenAlex, PubMed, Crossref
Output:         ./results/federated_learning_2025-03-12/
```

---

## 5. Output Specification

```
results/
  {query}_{date}/
    papers.csv            ← all deduplicated papers
    papers.db             ← SQLite database
    report_summary.txt    ← plain-text console summary
    report.html           ← (optional) visual dashboard
    charts/               ← (optional) PNG chart images
```

### papers.csv schema

| Column | Type | Description |
|---|---|---|
| id | string | SHA-256 hash of DOI or (title + year) |
| doi | string | DOI (if available) |
| arxiv_id | string | arXiv ID (if available) |
| pmid | string | PubMed ID (if available) |
| title | string | Paper title |
| authors | string | Semicolon-separated author names |
| year | integer | Publication year |
| venue | string | Journal or conference name |
| venue_type | string | journal / conference / preprint / workshop |
| abstract | text | Full abstract |
| keywords | string | Semicolon-separated keywords |
| citations | integer | Citation count at time of fetch |
| citation_velocity | float | Citations per year |
| influential_citations | integer | Influential citation count (Semantic Scholar) |
| sources | string | Comma-separated source tags (e.g. "arxiv,semantic_scholar") |
| url | string | Link to paper page |
| is_local | boolean | True if ingested from local library |
| fetched_at | datetime | ISO-8601 timestamp of retrieval |
| fetched_at | datetime | Timestamp of retrieval |
