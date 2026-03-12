"""Fast NLP pipeline — TF-IDF ngrams and review detection (no LLM required)."""

from __future__ import annotations

import re
from collections import Counter

from sklearn.feature_extraction.text import TfidfVectorizer

from src.storage.models import Paper


def extract_tfidf_ngrams(
    papers: list[Paper],
    top_n: int = 20,
    ngram_range: tuple[int, int] = (1, 3),
) -> list[tuple[str, float]]:
    """Extract top TF-IDF n-grams from paper abstracts."""
    abstracts = [p.abstract for p in papers if p.abstract]
    if not abstracts:
        return []

    vectorizer = TfidfVectorizer(
        max_features=5000,
        ngram_range=ngram_range,
        stop_words="english",
        max_df=0.8,
        min_df=2,
    )
    tfidf_matrix = vectorizer.fit_transform(abstracts)
    feature_names = vectorizer.get_feature_names_out()

    # Average TF-IDF score across documents for each term
    avg_scores = tfidf_matrix.mean(axis=0).A1
    top_indices = avg_scores.argsort()[::-1][:top_n]

    return [(feature_names[i], round(float(avg_scores[i]), 4)) for i in top_indices]


def extract_keyword_frequencies(
    papers: list[Paper], top_n: int = 30
) -> list[tuple[str, int]]:
    """Count keyword frequencies across all papers."""
    counter: Counter = Counter()
    for p in papers:
        for kw in p.get_keywords():
            if kw.strip():
                counter[kw.strip().lower()] += 1
    return counter.most_common(top_n)


def detect_review_papers(papers: list[Paper]) -> list[Paper]:
    """Return papers that look like reviews/surveys."""
    review_patterns = re.compile(
        r"\b(review|survey|systematic review|meta.analysis|overview|state.of.the.art)\b",
        re.IGNORECASE,
    )
    return [p for p in papers if review_patterns.search(p.title)]


def split_sentences(text: str) -> list[str]:
    """Simple sentence splitter."""
    sentences = re.split(r'(?<=[.!?])\s+', text.strip())
    return [s.strip() for s in sentences if len(s.strip()) > 10]


def compute_nlp_stats(papers: list[Paper]) -> dict:
    """Run all fast NLP analyses."""
    return {
        "tfidf_ngrams": extract_tfidf_ngrams(papers),
        "keyword_frequencies": extract_keyword_frequencies(papers),
        "review_paper_titles": [p.title for p in detect_review_papers(papers)],
    }
