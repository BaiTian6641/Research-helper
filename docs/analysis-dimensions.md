# Analysis Dimensions

This document defines how each of the four intelligence dimensions is computed from the collected paper data.

---

## 1. Interest

**Question:** How much attention is this field receiving, and is it trending up or down?

### Signals Used

| Signal | Source | Weight |
|---|---|---|
| Total paper count | All sources | 0.25 |
| Year-over-year growth rate | Publication dates | 0.35 |
| Total citation count | Semantic Scholar, IEEE | 0.20 |
| Average citation velocity | All sources | 0.20 |

### Computation

```
growth_rate = (papers_last_2_years - papers_prev_2_years) / papers_prev_2_years

citation_velocity = sum(citations_i / (current_year - year_i + 1)) / N

interest_score = normalize(
    0.25 * log(total_papers + 1) +
    0.35 * growth_rate +
    0.20 * log(total_citations + 1) +
    0.20 * citation_velocity
)
```

Final score: **0–100** (percentile against baseline of a "cold" field = 0).

### Output
- Trend chart: papers per year (bar chart)
- Growth rate: % change per 2-year window
- Interest score: 0–100

---

## 2. Motivation

**Question:** What problems are researchers trying to solve? What drives them?

### Approach: Two-Tier Abstract Sentence Classification

**Tier A — Local LLM (preferred, requires Ollama):**
Each abstract is sent to a local model (e.g. qwen2.5:14b) with a few-shot classification prompt.
The model labels each sentence as `problem`, `motivation`, `result`, or `other` and returns structured JSON.

**Tier B — Heuristic fallback (no LLM):**
Each abstract is split into sentences. Sentences are classified as **problem-framing** if they match motivational language patterns:

#### Pattern Groups

| Group | Example trigger phrases |
|---|---|
| Problem statement | "however", "unfortunately", "lacks", "fails to", "is limited by", "challenge", "barrier", "gap" |
| Open question | "remains unclear", "is not well understood", "little is known", "open problem" |
| Motivation claim | "motivated by", "inspired by", "in response to", "to address" |
| Societal/impact need | "critical need", "urgent", "growing demand", "essential for" |

#### Aggregation
- Collect all problem-framing sentences across all abstracts
- Cluster by semantic similarity (sentence embeddings or TF-IDF + KMeans)
- Return top 5–10 motivation clusters with representative sentences

### Motivation Score

```
motivation_score = (problem_sentences / total_abstract_sentences) * 100
```

A high score indicates researchers feel the field has open, unresolved challenges.

### Output
- Top motivation themes (clustered sentences)
- Motivation score: 0–100 (higher = more open problems perceived)
- Word cloud of problem-framing vocabulary

---

## 3. Confidence

**Question:** How strongly do researchers claim success? Are results presented boldly or cautiously?

### Approach: Two-Tier Claim Strength Detection

**Tier A — Local LLM (preferred):**
Result / conclusion sentences in the abstract are classified by a local model into
`strong`, `moderate`, `hedged`, or `negative` with structured JSON output.

**Tier B — Heuristic fallback:**
Classify abstract sentences as result/claim sentences, then score their hedging level by pattern matching.

#### Claim Polarity Patterns

| Level | Label | Example phrases |
|---|---|---|
| High confidence | `strong` | "outperforms", "state-of-the-art", "significantly improves", "achieves X%", "demonstrates" |
| Moderate confidence | `moderate` | "shows promise", "competitive", "comparable to", "can be used for" |
| Low confidence / hedging | `hedged` | "may", "might", "could potentially", "preliminary", "suggests", "appears to" |
| Negative / failure | `negative` | "failed", "did not improve", "no significant difference", "inconclusive" |

#### Confidence Score

```
confidence_score = (
    1.0 * strong_count +
    0.5 * moderate_count +
    0.1 * hedged_count +
    0.0 * negative_count
) / total_result_sentences * 100
```

### Additional Signals
- Ratio of papers that include quantitative results (contain "%" or numeric comparisons)
- Reproducibility signals: "code available", "open source", "dataset released"

### Output
- Confidence score: 0–100
- Distribution chart: strong / moderate / hedged / negative (stacked bar)
- Top "strong claim" excerpts (most cited papers)

---

## 4. Market Interest

**Question:** Is industry investing? Are there commercialisation signals?

### Signals Used

| Signal | Source | How detected |
|---|---|---|
| Industry author affiliations | OpenAlex institution data | Industry vs. academia classification |
| Funding / grant mentions | Crossref funder data, abstract text | "funded by", "supported by", sponsor names |
| Patent references | Abstract text | "patent", "commercialisation", "industry partner" |
| Application-domain keywords | Abstract text | domain-specific product/deployment language |
| High citation from non-academic venues | Semantic Scholar | cited-by analysis |

#### Industry Affiliation Classification
Institutions are tagged as:
- `academia` — universities, research institutes
- `industry` — corporations, startups, labs (Google, Microsoft, NVIDIA, etc.)
- `government` — national labs, government agencies
- `hybrid` — joint academia-industry

#### Known Major Industry Affiliations (seed list)
Google, Meta, Microsoft, Amazon, Apple, NVIDIA, IBM, Samsung, Huawei, Baidu,
Tencent, ByteDance, Intel, Qualcomm, OpenAI, DeepMind, Tesla, Bosch, Siemens, etc.

#### Market Score

```
industry_ratio = industry_papers / total_papers

funding_ratio = funded_papers / total_papers

patent_ratio = papers_mentioning_patents / total_papers

market_score = normalize(
    0.45 * industry_ratio +
    0.35 * funding_ratio +
    0.20 * patent_ratio
) * 100
```

### Output
- Market interest score: 0–100
- Industry vs. academia paper ratio (pie chart)
- Top funding agencies / sponsors
- Top industry organisations contributing papers

---

## Combined Dashboard Summary

```
┌─────────────────────────────────────────────────────┐
│  Field: "federated learning privacy"   (2018–2025)  │
│  Papers found: 4,382  |  Sources: 6                │
├──────────────────┬──────────────────────────────────┤
│  Interest        │  ████████████████░░  82 / 100   │
│  Motivation      │  ████████████░░░░░░  63 / 100   │
│  Confidence      │  ██████████████░░░░  71 / 100   │
│  Market Interest │  █████████░░░░░░░░░  47 / 100   │
├──────────────────┴──────────────────────────────────┤
│  Growth rate: +34% (2022→2024)                     │
│  Top venue: NeurIPS, ICML, ICLR                    │
│  Top motive: "privacy leakage in gradient sharing" │
│  Top funder: NSF, DARPA, EU Horizon                │
└─────────────────────────────────────────────────────┘
```

---

## Notes on Score Interpretation

| Score Range | Interpretation |
|---|---|
| 0–25 | Niche / emerging — very limited activity |
| 26–50 | Growing — gaining research attention |
| 51–75 | Established — active research community |
| 76–100 | Hot / saturated — dominant research topic |

Scores are **relative and heuristic**. They are useful for comparing fields against each other, not as absolute measures.
