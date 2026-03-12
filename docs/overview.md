# Research Field Intelligence Tool — Project Overview

## Purpose

A locally-hosted web application (Streamlit + FastAPI) that accepts keyword(s) or
topic strings from the user, queries multiple academic databases in parallel,
aggregates the results into a structured database, and produces quantitative analytics
that reveal the research landscape of that field. Users can also import their own
local paper collections and analyse draft research proposals against the field.

All AI-powered analysis runs via a **local LLM** (Ollama) — no data leaves the machine.

The four primary intelligence dimensions are:

| Dimension | Question answered |
|---|---|
| **Interest** | How much attention is the field receiving, and is it growing? |
| **Motivation** | What problems are researchers trying to solve? |
| **Confidence** | How strongly do researchers claim results? |
| **Market Interest** | Is industry investing, and are there commercial applications? |

---

## Core User Flow

```
User provides keyword(s) / topic  ──or──  imports local papers
        │                                       │
        ▼                                       ▼
Tool queries 6+ academic databases      Local files parsed &
in parallel (arXiv, Semantic Scholar,   normalised (PDF, BibTeX,
OpenAlex, PubMed, Crossref, …)         RIS, CSV)
        │                                       │
        └───────────────┬───────────────────────┘
                        ▼
        Results normalised & deduplicated
                        │
                        ▼
        Stored: SQLite database + CSV export
                        │
                ┌───────┴───────┐
                ▼               ▼
     Statistical analytics   Local LLM analytics
     (trend, citations,      (motivation, confidence,
      venues, authors)        themes, narrative)
                │               │
                └───────┬───────┘
                        ▼
        4-dimension scores (0–100) computed
                        │
                        ▼
        Dashboard displayed (Streamlit)
        + optional HTML / PDF / CSV export
                        │
                        ▼  (optional)
        Proposal Analyzer: upload draft → novelty score,
        gap analysis, recommended citations
```

---

## Target Users

- Academic researchers scoping a new field before committing to a project
- PhD students doing a literature review
- R&D teams evaluating a technology area before investment
- Science journalists or analysts tracking emerging topics

---

## High-Level Feature List

### Phase 1 — Data Collection & Storage
- Keyword-driven search across 6+ academic databases (parallel async)
- Retrieve title, authors, year, abstract, venue, citation count, DOI
- Deduplication by DOI / title similarity
- Local library import: PDF, BibTeX, RIS, CSV
- Persistence: SQLite + CSV export

### Phase 2 — Statistical Analytics
- Publication volume over time (trend line), YoY growth rate, CAGR
- Citation velocity, h-index estimate, top-10 most-cited papers
- Top venues, top authors, country/institution distribution
- Review / survey paper count and ratio
- Abstract NLP: TF-IDF keyword frequency, NER (spaCy, no LLM)

### Phase 3 — LLM-Powered Intelligence Dimensions
- Interest score (statistical: volume + growth + citations)
- Motivation analysis (LLM: problem-framing sentence classification + clustering)
- Confidence score (LLM: claim strength detection)
- Market interest score (industry ratio + funder/patent signals)
- Field narrative summary + maturity label (LLM)

### Phase 4 — UI & Reporting
- Streamlit web dashboard (Search / Dashboard / Library / Proposal / Settings)
- FastAPI REST backend
- HTML / PDF / CSV export
- Draft proposal analysis: novelty score, gap analysis, recommended citations
