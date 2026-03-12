# Pipeline & Workflow

## End-to-End Pipeline

```
Step 1: Input (Streamlit UI or API call)
Step 2: Cache Check
Step 3: Parallel API Fetching  ──and/or──  Local Library Ingestion
Step 4: Normalisation & Deduplication
Step 5: Storage (SQLite + CSV)
Step 6: Statistical Analytics
Step 7: LLM Analytics (optional, requires Ollama)
Step 8: Score Calculation
Step 9: Report / Dashboard Rendering
Step 10 (optional): Proposal Analysis
```

---

## Step 1 — Input

**Primary entry:** Streamlit web UI (‘Search’ tab) → calls FastAPI backend
**Alternative:** direct FastAPI POST or CLI wrapper

```
# Via Streamlit UI:
#   User fills in search form → frontend calls POST /api/v1/search

# Via CLI (thin wrapper that calls the same FastAPI endpoint):
python -m src.cli search \
  --query "federated learning privacy" \
  --years 2018-2025 \
  --min-citations 5 \
  --max-results 200 \
  --sources arxiv semantic_scholar openalex pubmed crossref \
  --output ./results/
```

Parsed into a `SearchConfig` object:
```python
@dataclass
class SearchConfig:
    query: str
    year_start: int
    year_end: int
    min_citations: int
    max_results_per_source: int
    sources: list[str]
    output_dir: Path
    force_refresh: bool = False
```

---

## Step 2 — Cache Check

- Compute a **cache key** from: `hash(query + year_start + year_end + sources)`
- Check `.cache/{key}.json` for a previous run
- If cache hit and `--force-refresh` not set → skip fetch, load from cache
- If cache miss → proceed to Step 3

---

## Step 3 — Parallel API Fetching

All enabled fetchers are launched concurrently with `asyncio.gather()`:

```python
results = await asyncio.gather(
    arxiv_fetcher.search(config),
    semantic_scholar_fetcher.search(config),
    openalex_fetcher.search(config),
    pubmed_fetcher.search(config),
    crossref_fetcher.search(config),
    return_exceptions=True     # failed source doesn't cancel others
)
```

Each fetcher:
1. Constructs the source-specific query string (handling Boolean operators, field mappings)
2. Paginates through results respecting rate limits (token bucket or exponential backoff)
3. Returns a `list[RawRecord]`

---

## Step 4 — Normalisation & Deduplication

### Normalisation

Each `RawRecord` is mapped to the common `Paper` schema:
- Author names standardised: `"Last, First"` format
- Years extracted from varying date formats (`YYYY`, `YYYY-MM`, `YYYY-MM-DD`)
- Abstracts stripped of HTML tags / LaTeX artefacts
- DOIs lowercased and validated

### Deduplication

```
For each new paper:
  1. If DOI matches an existing paper → merge (keep highest citation count)
  2. Else if title similarity (Levenshtein) ≥ 0.92 AND |year_diff| ≤ 1 → merge
  3. Else → add as new record
```

Merge strategy:
- `citations` → max of both
- `abstract` → longest non-null
- `sources` → union of source tags
- `authors` → from highest-trust source (Semantic Scholar > OpenAlex > arXiv)

---

## Step 5 — Storage

After deduplication:

```python
# Write to SQLite
sqlite_store.upsert_many(papers)

# Write to CSV
csv_exporter.write(papers, output_dir / "papers.csv")

# Save raw API cache
cache.save(cache_key, raw_results)
```

The SQLite database schema:

```sql
CREATE TABLE papers (
    id TEXT PRIMARY KEY,
    doi TEXT,
    arxiv_id TEXT,
    pmid TEXT,
    title TEXT NOT NULL,
    authors TEXT,           -- JSON array
    year INTEGER,
    venue TEXT,
    venue_type TEXT,        -- journal | conference | preprint | workshop
    abstract TEXT,
    keywords TEXT,          -- JSON array
    citations INTEGER,
    citation_velocity REAL,
    influential_citations INTEGER,
    sources TEXT,           -- JSON array
    url TEXT,
    is_local INTEGER DEFAULT 0,
    fetched_at TEXT,
    -- LLM-derived (populated after analytics)
    themes TEXT,            -- JSON array, NULL until LLM runs
    motivation_sentences TEXT,
    confidence_label TEXT,
    industry_affiliated INTEGER,
    funder_names TEXT       -- JSON array
);

CREATE TABLE search_sessions (
    id TEXT PRIMARY KEY,
    query TEXT,
    config TEXT,            -- JSON blob
    run_at TEXT,
    paper_count INTEGER
);

CREATE TABLE proposal_analyses (
    id TEXT PRIMARY KEY,
    proposal_text TEXT,
    run_at TEXT,
    novelty_score REAL,
    overlapping_papers TEXT, -- JSON array of {paper_id, similarity}
    gap_clusters TEXT,       -- JSON array
    recommended_citations TEXT, -- JSON array of paper_ids
    llm_narrative TEXT
);
```

---

## Step 6 — Statistical Analytics

Run without LLM — pure Python / spaCy:

```
TrendAnalyzer.run(papers)
  → yearly_counts, growth_rate, cagr, interest_score

CitationAnalyzer.run(papers)
  → citation_velocity, h_index_estimate, top_cited_papers

VenueAnalyzer.run(papers)
  → top_venues, top_authors, country_distribution

NLPFast.run(papers)
  → top_ngrams (uni/bi/trigrams via TF-IDF)
```

---

## Step 7 — LLM Analytics (optional)

Requires Ollama running locally. Falls back to heuristic if unavailable.

```
LLM ThemeExtractor.run(papers)
  → themes per paper (structured JSON)

LLM MotivationClassifier.run(papers)
  → motivation_sentences, motivation_clusters, motivation_score

LLM ConfidenceDetector.run(papers)
  → confidence_labels, confidence_score

LLM MarketExtractor.run(papers)
  → industry_affiliated, funder_names

LLM NarrativeSummary.run(papers)
  → field_narrative, maturity_label
```

---

## Step 8 — Score Calculation

```
ScoreCalculator.compute(trend, citations, nlp, llm_results, market)
  → interest_score    [0-100]  (statistical)
  → motivation_score   [0-100]  (LLM or heuristic)
  → confidence_score   [0-100]  (LLM or heuristic)
  → market_score       [0-100]  (industry ratio + funder + patent signals)
```

---

## Step 9 — Report / Dashboard Rendering

```python
report_data = ReportData(
    config=config,
    papers=papers,
    trend=trend_result,
    citations=citation_result,
    nlp=nlp_result,
    llm=llm_result,
    market=market_result,
    venues=venue_result,
    scores=score_result,
)

# Always: Streamlit dashboard (live in browser)
# The Streamlit UI reads report_data from the FastAPI response.

# Optional: static exports
if config.html_report:
    HTMLReport(report_data).render(output_dir / "report.html")
if config.pdf_report:
    PDFReport(report_data).render(output_dir / "report.pdf")
CSVExporter.write(papers, output_dir / "papers.csv")
```

---

## Step 10 (optional) — Proposal Analysis

Triggered from the ‘Proposal Analyzer’ tab in Streamlit.

```
1. User uploads PDF / DOCX / TXT  →  text extracted
2. LLM extracts claims, methods, objectives (structured JSON)
3. Proposal sentences embedded  →  cosine similarity vs. paper abstracts
4. Overlap table generated (papers > threshold similarity)
5. Gap analysis: proposal questions not covered by existing literature
6. Recommended citations: highly relevant papers not in the proposal
7. Output: novelty score (0–100), overlap table, gap list, citation list
```

---

## Error Handling & Resilience

| Scenario | Behaviour |
|---|---|
| API source is down / times out | Log warning; continue with other sources |
| API rate limit hit (429) | Exponential backoff: 2s → 4s → 8s → 16s; max 3 retries |
| API key missing for Tier 2 source | Skip source; warn user |
| Abstract missing for a paper | Store `null`; exclude from NLP steps |
| Zero results returned | Exit gracefully with "no results found" message; suggest broader query |
| Network offline, cache exists | Load from cache automatically |

---

## Configuration File Support

Users can store defaults in `config.yaml`:

```yaml
defaults:
  max_results_per_source: 200
  sources:
    - arxiv
    - semantic_scholar
    - openalex
    - pubmed
    - crossref
  output_dir: ./results

api_keys:
  ieee: ""          # leave blank to disable
  springer: ""
  core: ""
  openalex_email: "user@example.com"   # enables polite pool rate limit
```

---

## Iteration & Re-analysis

Because all results are persisted in SQLite, users can:

```bash
# Re-run analytics only (no new API calls)
python main.py analyze --db ./results/papers.db --query "federated learning privacy"

# Add a new source to an existing dataset
python main.py fetch --db ./results/papers.db --sources ieee --query "federated learning privacy"

# Compare two queries side by side
python main.py compare \
  --query-a "federated learning" \
  --query-b "split learning" \
  --db-a ./results/federated/ \
  --db-b ./results/split/
```
