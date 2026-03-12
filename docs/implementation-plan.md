# Implementation Plan

> **Goal:** Build the Research Field Intelligence Tool in 7 incremental sprints.
> Each sprint produces a working, testable deliverable.
> Sprints are ordered by dependency — later sprints build on earlier ones.
>
> **Preferred LLM:** `Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled`
> (27B reasoning-distilled model, runs locally via Ollama, ~17 GB / 20 GB VRAM).
> All LLM prompts, tests, and defaults are tuned for this model first.

---

## Sprint Overview

| Sprint | Name | Key Deliverable | Depends on |
|---|---|---|---|
| **S1** | Project scaffold + data model | Runnable project, `Paper` model, SQLite CRUD, CSV export | — |
| **S2** | API fetchers (Tier 1) | 5 working fetchers + orchestrator + deduplication | S1 |
| **S3** | Unified analytics engine (NLP + LLM) | Statistical analytics, Ollama LLM client, all 4 dimension scores, heuristic fallback | S1 |
| **S4** | FastAPI backend | REST API routes: search, analyze, library | S1, S2, S3 |
| **S5** | Streamlit UI (core) | Search + Dashboard + Library + Settings tabs | S4 |
| **S6** | Proposal analyzer | Upload → novelty score, gap analysis, recommended cites | S4, S3 |
| **S7** | Export, polish, docs | HTML/PDF export, start scripts, README, final testing | All |

> S3 is the largest sprint — it delivers the entire analytics pipeline in one pass
> so that statistical metrics and LLM-derived intelligence share a single interface
> from day one. This avoids a later retrofit and ensures the heuristic fallback
> path is built alongside the LLM path, not bolted on after.

---

## S1 — Project Scaffold + Data Model

### Objectives
- Set up the Python project structure, virtual environment, and dependencies
- Implement the `Paper` / `FieldStats` / `ProposalAnalysis` data classes and ORM
- Implement SQLite CRUD (`sqlite_store.py`, `library_store.py`) and CSV export
- Implement the cache manager

### Tasks

| # | Task | File(s) | Acceptance criteria |
|---|---|---|---|
| 1.1 | Create directory tree as per architecture.md § 3 | `src/`, `tests/`, etc. | `tree` output matches spec |
| 1.2 | Create `requirements.txt` with locked versions | `requirements.txt` | `pip install -r requirements.txt` succeeds |
| 1.3 | Create `.env.example` and `config.yaml` template | `.env.example`, `config.yaml` | Loadable by `pydantic-settings`; default model = `qwen3.5-reasoning` |
| 1.4 | Implement `config/settings.py` (pydantic-settings) | `src/config/settings.py` | Settings load from `.env`; `llm_model` defaults to `qwen3.5-reasoning` |
| 1.5 | Implement `config/sources.py` source registry | `src/config/sources.py` | Returns list of available sources |
| 1.6 | Implement `storage/models.py` — Paper, FieldStats, ProposalAnalysis | `src/storage/models.py` | Dataclasses + SQLAlchemy models pass `mypy` |
| 1.7 | Implement `storage/sqlite_store.py` — CRUD + upsert | `src/storage/sqlite_store.py` | Insert, query, upsert 1000 papers < 2s |
| 1.8 | Implement `storage/library_store.py` — local library DB | `src/storage/library_store.py` | Separate DB path; same Paper model |
| 1.9 | Implement `storage/csv_exporter.py` | `src/storage/csv_exporter.py` | Writes CSV matching schema in requirements.md |
| 1.10 | Implement `storage/cache.py` — hash-keyed file cache | `src/storage/cache.py` | Save + load raw JSON; cache hit returns data |
| 1.11 | Write tests for all storage modules | `tests/test_storage/` | `pytest tests/test_storage/ -v` all green |

### Dependencies (pip)
```
sqlalchemy>=2.0
pydantic>=2.0
pydantic-settings
python-dotenv
pyyaml
```

---

## S2 — API Fetchers (Tier 1)

### Objectives
- Implement async fetchers for the 5 free-tier sources + orchestrator
- Build the normalisation and deduplication pipeline
- Each fetcher is independently testable with mocked HTTP responses

### Tasks

| # | Task | File(s) | Acceptance criteria |
|---|---|---|---|
| 2.1 | Implement `searcher/base.py` — AbstractFetcher interface | `src/searcher/base.py` | `search()` and `normalise()` defined |
| 2.2 | Implement `searcher/arxiv.py` | `src/searcher/arxiv.py` | Returns ≥10 papers for "machine learning" |
| 2.3 | Implement `searcher/semantic_scholar.py` | `src/searcher/semantic_scholar.py` | Returns papers with citation counts |
| 2.4 | Implement `searcher/openalex.py` | `src/searcher/openalex.py` | Returns papers with institution data |
| 2.5 | Implement `searcher/pubmed.py` | `src/searcher/pubmed.py` | Returns papers with PMID + MeSH terms |
| 2.6 | Implement `searcher/crossref.py` | `src/searcher/crossref.py` | Returns papers with funder data |
| 2.7 | Implement `searcher/orchestrator.py` — parallel fetch + dedup | `src/searcher/orchestrator.py` | 5 fetchers run concurrently; dupes merged |
| 2.8 | Implement rate limiter / retry logic | (shared utility in `searcher/`) | 429 → backoff; timeout → skip gracefully |
| 2.9 | Optional: `searcher/ieee.py`, `searcher/springer.py` stubs | `src/searcher/ieee.py` etc. | Importable; returns empty if no API key |
| 2.10 | Write tests with mocked HTTP (use `respx` or `pytest-httpx`) | `tests/test_searcher/` | All green without live network |
| 2.11 | Integration test: live search "quantum computing" → CSV + DB | manual / CI optional | End-to-end roundtrip works |

### Dependencies (pip)
```
httpx
rapidfuzz          # Levenshtein dedup
feedparser         # arXiv Atom XML
```

---

## S3 — Unified Analytics Engine (NLP + LLM)

> **Design principle:** Analytics is a single pipeline with two execution tiers.
> Every analysis function has the signature `run(papers, llm_client=None)`.
> When `llm_client` is provided (Ollama running), the function uses the LLM.
> When `llm_client` is `None`, it falls back to the heuristic/spaCy path.
> Both tiers return the same output types — callers never need to branch.

### Objectives
- Build statistical analytics (trend, citations, venues, NLP) — no LLM required
- Build the Ollama LLM client and all 6 LLM task modules in the same sprint
- Wire both tiers behind a unified `AnalyticsPipeline` orchestrator
- Compute all 4 dimension scores (Interest, Motivation, Confidence, Market)
- Default model: **Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled** via Ollama

### Architecture of the unified pipeline

```
AnalyticsPipeline.run(papers, llm_client?)
  │
  ├─ [always]  TrendAnalyzer      → yearly_counts, growth_rate, CAGR
  ├─ [always]  CitationAnalyzer   → velocity, h-index, top-cited
  ├─ [always]  VenueAnalyzer      → top venues, authors, countries
  ├─ [always]  NLPFast (spaCy)    → TF-IDF ngrams, review detection
  │
  ├─ [if LLM]  ThemeExtractor     → themes per paper (JSON)
  ├─ [if LLM]  MotivationClassifier → problem sentences + clusters
  │  [else]    MotivationHeuristic → regex pattern matching fallback
  ├─ [if LLM]  ConfidenceDetector → claim strength labels
  │  [else]    ConfidenceHeuristic → regex pattern matching fallback
  ├─ [if LLM]  MarketExtractor    → industry/funder extraction
  │  [else]    MarketHeuristic    → keyword + institution matching
  ├─ [if LLM]  NarrativeSummary   → 3-5 paragraph field overview
  │
  └─ ScoreCalculator.compute(all of the above)
       → interest_score, motivation_score, confidence_score, market_score
       → FieldStats object (complete)
```

### Tasks — Part A: Statistical Analytics (no LLM)

| # | Task | File(s) | Acceptance criteria |
|---|---|---|---|
| 3.1 | Implement `analytics/trend.py` — papers/year, growth rate, CAGR | `src/analytics/trend.py` | Correct counts from test fixture |
| 3.2 | Implement `analytics/citations.py` — velocity, h-index, top-cited | `src/analytics/citations.py` | h-index matches manual calc on test data |
| 3.3 | Implement `analytics/venues.py` — top venues, authors, countries | `src/analytics/venues.py` | Sorted frequency tables correct |
| 3.4 | Implement `analytics/nlp_fast.py` — TF-IDF ngrams, review detection | `src/analytics/nlp_fast.py` | Top-10 bigrams sensible for test corpus |

### Tasks — Part B: Ollama LLM Client + Task Modules

| # | Task | File(s) | Acceptance criteria |
|---|---|---|---|
| 3.5 | Implement `llm/client.py` — Ollama HTTP wrapper (`complete`, `complete_json`, `list_models`, health check) | `src/llm/client.py` | `complete_json()` returns valid dict; health check returns bool |
| 3.6 | Implement `llm/model_registry.py` — model list + capability tags; default = `qwen3.5-reasoning` | `src/llm/model_registry.py` | `get_default()` returns `qwen3.5-reasoning`; `list_installed()` works |
| 3.7 | Implement `llm/prompts.py` — all prompt templates, tuned for Qwen3.5-reasoning output format | `src/llm/prompts.py` | Templates render correctly with test data |
| 3.8 | Implement `llm/tasks/theme_extractor.py` | `src/llm/tasks/theme_extractor.py` | Returns `list[str]` themes per abstract |
| 3.9 | Implement `llm/tasks/motivation_classifier.py` | `src/llm/tasks/motivation_classifier.py` | Labels sentences → motivation_score |
| 3.10 | Implement `llm/tasks/confidence_detector.py` | `src/llm/tasks/confidence_detector.py` | Labels → confidence_score |
| 3.11 | Implement `llm/tasks/market_extractor.py` | `src/llm/tasks/market_extractor.py` | Extracts industry/funder signals |
| 3.12 | Implement `llm/tasks/narrative.py` — field overview summary | `src/llm/tasks/narrative.py` | Returns 3–5 paragraph summary + maturity label |

### Tasks — Part C: Heuristic Fallbacks + Score Unification

| # | Task | File(s) | Acceptance criteria |
|---|---|---|---|
| 3.13 | Implement heuristic fallbacks: `MotivationHeuristic`, `ConfidenceHeuristic`, `MarketHeuristic` (regex / keyword patterns) | `src/analytics/heuristics.py` | Produces same output types as LLM tasks |
| 3.14 | Implement `analytics/scores.py` — ScoreCalculator (Interest, Motivation, Confidence, Market → 0–100 each) | `src/analytics/scores.py` | Score = 0–100; works with and without LLM results |
| 3.15 | Implement `analytics/pipeline.py` — `AnalyticsPipeline` orchestrator that detects Ollama availability and dispatches accordingly | `src/analytics/pipeline.py` | `run(papers)` completes with LLM; `run(papers)` also completes without |
| 3.16 | Write tests: statistical modules (fixtures), LLM tasks (mocked Ollama responses), heuristic fallbacks, pipeline orchestrator (both tiers) | `tests/test_analytics/`, `tests/test_llm/` | All green; pipeline tested in LLM mode + fallback mode |

### Preferred Model Configuration

The following is set in `config.yaml` and `config/settings.py`:

```yaml
llm:
  default_model: qwen3.5-reasoning        # Ollama model name after create
  ollama_base_url: http://localhost:11434
  max_concurrent_llm_calls: 4             # parallel abstract batches
  abstract_sample_size: 500               # LLM analyses only N abstracts for large sets
  timeout_seconds: 120                    # per-call timeout
```

**Ollama setup (documented in README):**
```bash
# Download GGUF from HuggingFace
# Jackrong/Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled

# Create Modelfile
cat > Modelfile <<EOF
FROM ./Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled.Q4_K_M.gguf
PARAMETER num_ctx 8192
PARAMETER temperature 0.3
EOF

ollama create qwen3.5-reasoning -f Modelfile
```

**Why this model:**
- 27B parameters — fits in a single 24 GB GPU (Q4_K_M quantisation)
- Reasoning-distilled: chain-of-thought traces improve classification accuracy
  and make gap analysis auditable
- Structured JSON output via Ollama `format` parameter works reliably
- Strong enough for all 6 task types (theme, motivation, confidence, market,
  narrative, proposal analysis) — no need for multiple models

**Fallback model order** (if Qwen3.5-reasoning not available):
1. `qwq:32b` — similar reasoning capability
2. `deepseek-r1:14b` — lighter, still good reasoning
3. `qwen2.5:14b` — fastest reliable option
4. `mistral:7b` — minimal quality, minimal resources
5. (no Ollama) → heuristic regex/spaCy fallback

### Dependencies (pip)
```
spacy
scikit-learn
numpy
sentence-transformers    # for embedding-based similarity
```
External: `ollama` with `qwen3.5-reasoning` model

---

## S4 — FastAPI Backend

### Objectives
- Expose all functionality as REST endpoints
- Streamlit UI will call these; they are also usable standalone
- Analytics endpoint uses the unified pipeline (auto-detects LLM)

### Tasks

| # | Task | File(s) | Acceptance criteria |
|---|---|---|---|
| 4.1 | Implement `api/main.py` — FastAPI app, startup (init AnalyticsPipeline, detect Ollama), CORS | `src/api/main.py` | `uvicorn` starts; `/docs` shows OpenAPI; logs LLM availability |
| 4.2 | Implement `api/schemas.py` — Pydantic request/response models | `src/api/schemas.py` | Serialise `FieldStats` to JSON |
| 4.3 | Implement `api/routes/search.py` — POST /api/v1/search (fetch + full analytics) | `src/api/routes/search.py` | Returns papers + `FieldStats` JSON |
| 4.4 | Implement `api/routes/analyze.py` — POST /api/v1/analyze (re-run analytics on existing DB) | `src/api/routes/analyze.py` | Accepts DB path; returns scores |
| 4.5 | Implement `api/routes/library.py` — GET/POST /api/v1/library | `src/api/routes/library.py` | Upload file → parsed papers returned |
| 4.6 | Implement SSE progress stream for long searches | `src/api/routes/search.py` | Streamlit shows live progress |
| 4.7 | Implement `ingestion/ingestion_service.py` + parsers | `src/ingestion/` | PDF, BibTeX, RIS, CSV all parse correctly |
| 4.8 | Add `GET /api/v1/status` — returns LLM availability, model name, paper count | `src/api/routes/status.py` | JSON: `{llm_available, model, papers_count}` |
| 4.9 | Write API tests with `httpx.AsyncClient` | `tests/test_api/` | All green |

### Dependencies (pip)
```
fastapi
uvicorn[standard]
sse-starlette
pdfplumber
pypdf
bibtexparser
rispy
python-docx
python-multipart
```

---

## S5 — Streamlit UI (Core)

### Objectives
- Build the 4 core tabs: Search, Dashboard, Library, Settings
- Dashboard shows all 4 dimension scores + LLM narrative (when available)
- Settings tab includes Ollama model picker with `qwen3.5-reasoning` as default
- Connect all tabs to FastAPI backend via `api_client.py`

### Tasks

| # | Task | File(s) | Acceptance criteria |
|---|---|---|---|
| 5.1 | Implement `ui/app.py` — Streamlit entry point, sidebar nav | `src/ui/app.py` | `streamlit run` shows 4 tabs |
| 5.2 | Implement `ui/api_client.py` — async calls to backend | `src/ui/api_client.py` | Fetches search results from backend |
| 5.3 | Implement `ui/pages/01_search.py` — keyword form, source toggles | `src/ui/pages/01_search.py` | Form submits; progress bar shows |
| 5.4 | Implement `ui/pages/02_dashboard.py` — charts, score cards, LLM narrative section | `src/ui/pages/02_dashboard.py` | Plotly trend chart + 4 score bars; narrative visible if LLM ran |
| 5.5 | Implement `ui/pages/03_library.py` — file upload, table browser | `src/ui/pages/03_library.py` | Import PDF → appears in table |
| 5.6 | Implement `ui/components/score_card.py` — reusable 0–100 score bar | `src/ui/components/score_card.py` | Renders correctly with LLM and heuristic scores |
| 5.7 | Implement `ui/components/trend_chart.py` — Plotly time series | `src/ui/components/trend_chart.py` | Displays papers-per-year |
| 5.8 | Implement `ui/components/venue_table.py` — sortable table | `src/ui/components/venue_table.py` | Top-10 venues shown |
| 5.9 | Implement settings page: API keys, Ollama model picker (default `qwen3.5-reasoning`), LLM health indicator | `src/ui/pages/05_settings.py` | Shows green/red LLM status; saves config |
| 5.10 | Implement `reports/charts.py` — Plotly figure builders | `src/reports/charts.py` | Figures usable by both UI and export |

### Dependencies (pip)
```
streamlit
plotly
```

---

## S6 — Proposal Analyzer

### Objectives
- Upload a proposal → extract claims → compare against field database
- Produce novelty score, overlap table, gap analysis, recommended citations
- Uses same LLM client from S3 (Qwen3.5-reasoning preferred)

### Tasks

| # | Task | File(s) | Acceptance criteria |
|---|---|---|---|
| 6.1 | Implement `llm/tasks/proposal_parser.py` — extract claims via LLM (Qwen3.5-reasoning) | `src/llm/tasks/proposal_parser.py` | Returns structured claims list |
| 6.2 | Implement `llm/tasks/gap_analyzer.py` — identify gaps + recommend cites | `src/llm/tasks/gap_analyzer.py` | Returns gaps + citation list |
| 6.3 | Implement `analytics/proposal_analysis.py` — sentence embedding + cosine similarity | `src/analytics/proposal_analysis.py` | Novelty score 0–100 correct |
| 6.4 | Implement `api/routes/proposal.py` — POST /api/v1/proposal | `src/api/routes/proposal.py` | Accepts file upload; returns analysis JSON |
| 6.5 | Implement `ui/pages/04_proposal.py` — upload, results, charts | `src/ui/pages/04_proposal.py` | Full round-trip in browser |
| 6.6 | Implement `ui/components/proposal_report.py` — overlap table, gap list | `src/ui/components/proposal_report.py` | Renders in Streamlit |
| 6.7 | Write tests (mock LLM + embedding responses) | `tests/test_proposal/` | All green |

---

## S7 — Export, Polish & Documentation

### Objectives
- Static HTML + PDF export
- Start scripts for Windows / Unix
- README with quickstart (including Qwen3.5-reasoning Ollama setup)
- Final pass on tests and edge cases

### Tasks

| # | Task | File(s) | Acceptance criteria |
|---|---|---|---|
| 7.1 | Implement `reports/html_exporter.py` — Jinja2 + Plotly → HTML | `src/reports/html_exporter.py` | Self-contained HTML opens in browser |
| 7.2 | Implement `reports/pdf_exporter.py` — WeasyPrint | `src/reports/pdf_exporter.py` | PDF generated, charts visible |
| 7.3 | Implement `reports/csv_exporter.py` (if not done) | `src/reports/csv_exporter.py` | CSV matches schema |
| 7.4 | Create `start.bat` + `start.sh` launch scripts | root | One-command startup |
| 7.5 | Write `README.md` — install, configure Ollama (Qwen3.5-reasoning setup), run, screenshots | `README.md` | A new user can go from clone → running in < 10 commands |
| 7.6 | Final integration test: full search → dashboard → proposal | manual | No errors end-to-end |
| 7.7 | Audit: security (no keys logged), error handling, edge cases | all | Pass checklist |

### Dependencies (pip)
```
jinja2
weasyprint
```

---

## Dependency Graph

```
S1 (scaffold + storage)
 ├── S2 (fetchers) ────────────────┐
 │                                 ▼
 └── S3 (analytics: NLP + LLM) ──► S4 (FastAPI backend)
                                    ├── S5 (Streamlit UI) ──► S7 (export, polish)
                                    └── S6 (proposal) ──────► S7
```

**Critical path:** S1 → S3 → S4 → S5 → S7

**Parallel:** S2 can be built alongside S3 (both only depend on S1).

---

## Implementation Order

```
Week 1:     S1  —  scaffold, models, storage, config
Week 2-3:   S2 + S3 in parallel
              S2: fetchers (API integration)
              S3 Part A: statistical analytics (trend, citations, venues, NLP)
              S3 Part B: LLM client + task modules + prompts
              S3 Part C: heuristic fallbacks + score unification + pipeline
Week 4:     S4  —  FastAPI backend (wires S2 + S3 together)
Week 5:     S5  —  Streamlit UI
Week 6:     S6  —  proposal analyzer
Week 7:     S7  —  export, polish, documentation, final testing
```

S2 and S3 run in parallel during weeks 2–3 because they both depend only on S1
and have no dependency on each other. S4 is the integration point that brings them
together.

---

## LLM Prompt Tuning Notes (for S3)

All prompts are developed and tested against **Qwen3.5-27B-Claude-4.6-Opus-Reasoning-Distilled**.

### Design guidelines for prompts

1. **Always request structured JSON output** — use Ollama's `format` parameter with
   a JSON schema so the model output is machine-parseable without post-processing.

2. **Use chain-of-thought sparingly** — this model produces reasoning traces
   automatically. For classification tasks (motivation, confidence), instruct it to
   output the label directly. For complex tasks (gap analysis, narrative), allow the
   reasoning trace and extract the final answer.

3. **Batch abstracts** — send 5–10 abstracts per prompt to reduce round-trips.
   The model's 8192 context window fits ~8 average abstracts (300 tokens each)
   plus the prompt template.

4. **Temperature 0.3** for classification tasks (deterministic), **0.7** for
   narrative/summary tasks (more creative output).

5. **Test each prompt on 20 hand-labelled abstracts** and verify F1 ≥ 0.75 for
   classification tasks before finalising.

### Example prompt template (motivation classification)

```
You are a research paper analyst. Classify each sentence in the following
abstracts as one of: "problem", "motivation", "result", "method", "other".

Return a JSON array where each element is:
{"paper_index": <int>, "sentence": <str>, "label": <str>}

Abstracts:
{% for i, abstract in abstracts %}
[{{ i }}] {{ abstract }}
{% endfor %}
```

---

## Risk Register

| Risk | Impact | Mitigation |
|---|---|---|
| API rate limits tighter than documented | Fewer results returned | Aggressive caching; fallback to cached data |
| Semantic Scholar / OpenAlex API changes | Fetcher breaks | Pin API version in URL; integration tests run weekly |
| Ollama not installed by user | LLM features unavailable | Heuristic fallback for all tasks; clear setup docs in README |
| Qwen3.5-reasoning GGUF not available / download issues | Default model missing | Fallback chain: qwq:32b → deepseek-r1:14b → qwen2.5:14b → mistral:7b |
| Large result sets (>5000 papers) slow LLM | Analytics takes too long | Sample 500 abstracts for LLM; statistical metrics run on all |
| Qwen3.5-reasoning structured output occasionally malformed | JSON parse error | Retry once with stricter prompt; fall back to heuristic if second attempt fails |
| PDF text extraction fails (scanned PDFs) | Local library gaps | Warn user; suggest OCR tool; skip unreadable files |
| WeasyPrint install issues on Windows | PDF export fails | Make PDF optional; HTML export as primary |

---

## Definition of Done (per sprint)

- [ ] All tasks in the sprint table complete
- [ ] Unit tests pass (`pytest` all green)
- [ ] No `mypy` type errors in changed files
- [ ] Code reviewed against architecture.md module structure
- [ ] Feature works end-to-end (manual smoke test)
- [ ] (S3 only) Analytics pipeline tested in both LLM mode and heuristic-fallback mode
