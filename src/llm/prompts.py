"""Prompt templates for all LLM tasks — tuned for Qwen3.5-reasoning."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Theme extraction
# ---------------------------------------------------------------------------
THEME_EXTRACTION_PROMPT = """You are a research paper analyst. Extract the main research themes from the following abstracts.

Return a JSON object with a single key "themes" containing a list of strings.
Each theme should be 2-5 words. Return at most 15 themes.

Abstracts:
{abstracts_text}

Return JSON only:"""

# ---------------------------------------------------------------------------
# Motivation classification
# ---------------------------------------------------------------------------
MOTIVATION_CLASSIFICATION_PROMPT = """You are a research paper analyst. For each abstract below, identify sentences that describe problems, motivations, or research gaps.

Classify each relevant sentence as one of: "problem", "motivation", "result", "method", "other".
Only return sentences classified as "problem" or "motivation".

Return a JSON object:
{{"sentences": [{{"paper_index": <int>, "sentence": "<str>", "label": "<str>"}}]}}

Abstracts:
{abstracts_text}

Return JSON only:"""

# ---------------------------------------------------------------------------
# Confidence detection
# ---------------------------------------------------------------------------
CONFIDENCE_DETECTION_PROMPT = """You are a research paper analyst. For each abstract below, identify result/claim sentences and classify their confidence level.

Labels: "strong", "moderate", "hedged", "negative"
- strong: "outperforms", "significantly improves", "achieves X%", "demonstrates"
- moderate: "shows promise", "competitive", "comparable to"
- hedged: "may", "might", "could potentially", "preliminary", "suggests"
- negative: "failed", "did not improve", "no significant difference"

Return a JSON object:
{{"claims": [{{"paper_index": <int>, "sentence": "<str>", "label": "<str>"}}]}}

Abstracts:
{abstracts_text}

Return JSON only:"""

# ---------------------------------------------------------------------------
# Market signal extraction
# ---------------------------------------------------------------------------
MARKET_EXTRACTION_PROMPT = """You are a research paper analyst. For each abstract below, extract industry and market signals.

Look for:
- Industry company names mentioned
- Funding agencies or sponsors mentioned
- Patent or commercialisation references
- Application-domain product/deployment language

Return a JSON object:
{{"signals": [{{"paper_index": <int>, "companies": [<str>], "funders": [<str>], "has_patent_ref": <bool>}}]}}

Abstracts:
{abstracts_text}

Return JSON only:"""

# ---------------------------------------------------------------------------
# Narrative summary
# ---------------------------------------------------------------------------
NARRATIVE_SUMMARY_PROMPT = """You are a research analyst writing a field overview report. Based on the following statistics and sample abstracts, write a comprehensive 3-5 paragraph summary of this research field.

Field query: {query}
Total papers: {total_papers}
Year range: {year_start}–{year_end}
Growth rate: {growth_rate:.1f}%
Top venues: {top_venues}
Top themes: {top_themes}

Sample abstracts (representative):
{sample_abstracts}

Include:
1. An overview of the field's trajectory and current state
2. Key research themes and motivations
3. The maturity level: one of "Emerging", "Growing", "Established", "Saturating"
4. Open research questions and future directions

Return a JSON object:
{{"narrative": "<3-5 paragraphs>", "maturity_label": "<one of: Emerging, Growing, Established, Saturating>", "open_questions": ["<question1>", "<question2>", ...]}}

Return JSON only:"""

# ---------------------------------------------------------------------------
# Paper-level sentiment classification
# ---------------------------------------------------------------------------
LLM_SENTIMENT_ANALYSIS_PROMPT = """You are a research paper analyst. Classify the overall sentiment of each abstract below toward its research area's prospects and results.

Classify as:
- "positive": results are promising, significant advances, strong performance, optimistic outlook
- "negative": limitations dominate, failures, risks, disappointing results, unsolved blocking issues
- "neutral": objective/methodological focus, mixed results, incremental work, no strong evaluative claim

Return a JSON object:
{{"classifications": [{{"paper_index": <int>, "label": "<positive|negative|neutral>", "reason": "<one sentence>"}}]}}

Abstracts:
{abstracts_text}

Return JSON only:"""


# ---------------------------------------------------------------------------
# Paper-level sentiment classification
# ---------------------------------------------------------------------------
LLM_SENTIMENT_ANALYSIS_PROMPT = """You are a research paper analyst. Classify the overall sentiment of each abstract below toward its research area's prospects and results.

Classify as:
- "positive": results are promising, significant advances, strong performance, optimistic outlook
- "negative": limitations dominate, failures, risks, disappointing results, unsolved blocking issues
- "neutral": objective/methodological focus, mixed results, incremental work, no strong evaluative claim

Return a JSON object:
{{"classifications": [{{"paper_index": <int>, "label": "<positive|negative|neutral>", "reason": "<one sentence>"}}]}}

Abstracts:
{abstracts_text}

Return JSON only:"""


# ---------------------------------------------------------------------------
# Proposal claim extraction
# ---------------------------------------------------------------------------
PROPOSAL_CLAIM_EXTRACTION_PROMPT = """You are a research proposal reviewer. Extract the main claims, objectives, and proposed methods from the following proposal text.

For each claim, identify:
- The claim text
- Whether it's a "novelty_claim", "objective", "method", or "hypothesis"

Return a JSON object:
{{"claims": [{{"text": "<str>", "type": "<str>"}}]}}

Proposal text:
{proposal_text}

Return JSON only:"""

# ---------------------------------------------------------------------------
# Gap analysis
# ---------------------------------------------------------------------------
GAP_ANALYSIS_PROMPT = """You are a research gap analyst. Given the proposal claims and relevant existing papers below, identify:
1. Which proposal claims overlap significantly with existing work
2. Which claims represent genuine novelty/gaps in the literature
3. Papers that the proposal should cite but doesn't seem to reference

Proposal claims:
{claims_text}

Existing papers (title + abstract snippets):
{papers_text}

Return a JSON object:
{{"overlaps": [{{"claim": "<str>", "similar_papers": ["<title>"], "similarity_note": "<str>"}}], "gaps": ["<genuine gap description>"], "recommended_citations": ["<paper title>"]}}

Return JSON only:"""


def format_abstracts_batch(abstracts: list[tuple[int, str]], max_chars: int = 6000) -> str:
    """Format a batch of (index, abstract) pairs for prompt injection."""
    parts: list[str] = []
    total = 0
    for idx, abstract in abstracts:
        text = f"[{idx}] {abstract[:500]}"
        if total + len(text) > max_chars:
            break
        parts.append(text)
        total += len(text)
    return "\n\n".join(parts)
