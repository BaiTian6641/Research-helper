# Data Sources

This document lists every academic database the tool targets, their access model, API quality, and implementation notes.

---

## Tier 1 — Free, No API Key Required (default enabled)

### 1. arXiv
| Property | Detail |
|---|---|
| URL | https://arxiv.org/search/ |
| API | `http://export.arxiv.org/api/query` (Atom/XML) |
| Fields covered | CS, Physics, Math, Biology, Economics, Stats |
| Rate limit | ~3 req/s (unofficial) |
| Records per request | Up to 2,000 |
| Key fields available | title, authors, year, abstract, DOI (sometimes), categories |
| Citation count | **Not available** |
| Notes | Best for preprints; many papers appear here before journals |

### 2. Semantic Scholar
| Property | Detail |
|---|---|
| URL | https://www.semanticscholar.org |
| API | `https://api.semanticscholar.org/graph/v1/` |
| Fields covered | All disciplines |
| Rate limit | 100 req/s (free tier) |
| Key fields available | title, authors, year, abstract, DOI, citation count, external IDs |
| Citation count | Yes (highly reliable) |
| Notes | Excellent citation data; provides `influentialCitationCount` |

### 3. OpenAlex
| Property | Detail |
|---|---|
| URL | https://openalex.org |
| API | `https://api.openalex.org/works` |
| Fields covered | All disciplines |
| Rate limit | 10 req/s without key; 100 req/s with (free) polite pool |
| Key fields available | title, authors, year, abstract (inverted index), DOI, citations, concepts, institutions |
| Citation count | Yes |
| Notes | Open replacement for Microsoft Academic; covers 200M+ works; has institution/country data useful for market analysis |

### 4. PubMed (NCBI Entrez)
| Property | Detail |
|---|---|
| URL | https://pubmed.ncbi.nlm.nih.gov |
| API | `https://eutils.ncbi.nlm.nih.gov/entrez/eutils/` |
| Fields covered | Biomedical, life sciences, clinical |
| Rate limit | 3 req/s (unauthenticated), 10 req/s (with API key) |
| Key fields available | title, authors, year, abstract, MeSH terms, journal, DOI, PMID |
| Citation count | Not in main API; available via iCite |
| Notes | Essential for biology/medical topics; MeSH terms enrich topic analysis |

### 5. Crossref
| Property | Detail |
|---|---|
| URL | https://www.crossref.org |
| API | `https://api.crossref.org/works` |
| Fields covered | All disciplines (DOI registry) |
| Rate limit | 50 req/s (polite pool with email header) |
| Key fields available | title, authors, year, DOI, venue, type, funder, license |
| Citation count | `is-referenced-by-count` (basic) |
| Notes | Best source for **funder / grant data** → market interest signals |

### 6. CORE
| Property | Detail |
|---|---|
| URL | https://core.ac.uk |
| API | `https://api.core.ac.uk/v3/` |
| Fields covered | Open-access across all disciplines |
| Rate limit | Free API key available; 10 req/s |
| Key fields available | title, authors, year, abstract, DOI, full-text URL |
| Citation count | Not available |
| Notes | Good for full-text access to OA papers |

---

## Tier 2 — Free with API Key

### 7. IEEE Xplore
| Property | Detail |
|---|---|
| URL | https://ieeexplore.ieee.org |
| API | `https://developer.ieee.org/apis` |
| Fields covered | Electrical engineering, CS, electronics |
| Rate limit | 200 req/day (free tier) |
| Key fields available | title, authors, year, abstract, DOI, citations, keywords |
| Citation count | Yes |
| Notes | Requires IEEE developer account; strong for hardware/systems topics |

### 8. Springer Nature
| Property | Detail |
|---|---|
| URL | https://dev.springernature.com |
| API | `https://api.springernature.com/meta/v2/json` |
| Fields covered | STEM, medicine |
| Rate limit | 5,000 req/day (free) |
| Key fields available | title, authors, year, abstract, DOI, journal |
| Citation count | **Not available** |
| Notes | Springer and Nature journals; good for high-impact papers |

---

## Tier 3 — Unofficial / Scraping (use carefully)

### 9. Google Scholar (via `scholarly`)
| Property | Detail |
|---|---|
| Access | Python `scholarly` library (unofficial) |
| Rate limit | Very strict; CAPTCHA-prone; use residential proxy or ScraperAPI |
| Citation count | Yes (highly visible) |
| Notes | Rich citation data but fragile; **disabled by default**; enable explicitly |

---

## Source Priority and Deduplication

### Local Source

Papers imported from local files (PDF, BibTeX, RIS, CSV, TXT) are tagged
`source = "local"` and stored in `local_library.db`. They are merged into the
main analysis alongside API-fetched papers. Deduplication applies: if a local
paper matches an API-fetched paper by DOI or title, they are merged (API metadata
enriches the local record).

### Deduplication order (highest trust first):

1. DOI match (exact)
2. Title + Year fuzzy match (Levenshtein ≥ 0.92)
3. arXiv ID cross-reference

When duplicate detected, merge fields, preserving:
- Highest citation count
- Longest abstract
- All source tags (e.g., `["arxiv", "semantic_scholar"]`)

---

## Source Coverage Matrix

| Topic Area | Best Sources |
|---|---|
| Computer Science | arXiv, Semantic Scholar, IEEE, ACM (future) |
| Biology / Medicine | PubMed, OpenAlex, Semantic Scholar |
| Physics / Math | arXiv, OpenAlex, Crossref |
| Engineering | IEEE, Crossref, Springer |
| Social Sciences | OpenAlex, Crossref, Semantic Scholar |
| Interdisciplinary | OpenAlex (broadest coverage) |
| Market / Funding signals | Crossref (funder data), OpenAlex (institution) |
