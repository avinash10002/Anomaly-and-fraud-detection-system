"""
reasoning.py
============
Generates transparent, human-interpretable reasons explaining why two project descriptions
exhibit high semantic similarity.
"""

from __future__ import annotations

import re
from typing import Set

# Common English and administrative stopwords in MPLADS descriptions
STOPWORDS: Set[str] = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or", "by",
    "with", "from", "as", "is", "are", "was", "were", "be", "been", "being",
    "it", "its", "under", "over", "into", "through", "during", "before", "after",
    "above", "below", "between", "both", "each", "few", "more", "most", "other",
    "some", "such", "no", "nor", "not", "only", "own", "same", "so", "than",
    "too", "very", "s", "t", "can", "will", "just", "don", "should", "now",
    "near", "nearer", "nearby", "etc", "viz", "per", "via", "re", "upto",
    "gram", "panchayat", "village", "dist", "district", "ward", "no", "nos",
    "shri", "smt", "late", "near", "house", "road", "at", "in", "from",
}

# Domain-specific multi-word phrases to highlight if present in both
DOMAIN_PHRASES = [
    "community hall",
    "drinking water",
    "cc road",
    "c.c. road",
    "cement concrete road",
    "paver block",
    "solar street light",
    "solar light",
    "high mast light",
    "bore well",
    "borewell",
    "boundary wall",
    "sub health centre",
    "primary health centre",
    "primary school",
    "school building",
    "drainage system",
    "storm water drain",
    "culvert construction",
    "cremation ground",
    "graveyard boundary",
    "anganwadi centre",
    "pipeline work",
    "water tank",
    "interlocking tiles",
    "overhead tank",
]


def extract_content_tokens(text: str) -> Set[str]:
    """Extract lowercase alpha tokens with length >= 3 excluding stopwords."""
    words = re.findall(r"\b[a-zA-Z]{3,}\b", text.lower())
    return {w for w in words if w not in STOPWORDS}


def generate_similarity_reason(
    query_text: str,
    target_text: str,
    score: float,
) -> str:
    """
    Produce a concise, human-understandable reason for the similarity match.
    Surfaces key shared phrases or vocabulary.
    """
    q_lower = query_text.lower()
    t_lower = target_text.lower()

    # Check for domain phrase matches first
    matched_phrases = []
    for phrase in DOMAIN_PHRASES:
        if phrase in q_lower and phrase in t_lower:
            matched_phrases.append(phrase)

    # Content word overlap
    q_tokens = extract_content_tokens(query_text)
    t_tokens = extract_content_tokens(target_text)
    shared_tokens = sorted(list(q_tokens.intersection(t_tokens)))

    # Remove individual words that are already covered by matched phrases
    phrase_words = set()
    for p in matched_phrases:
        phrase_words.update(p.split())
    remaining_shared = [w for w in shared_tokens if w not in phrase_words]

    elements = []
    for p in matched_phrases[:2]:
        elements.append(f"'{p}'")
    for w in remaining_shared[:3]:
        elements.append(f"'{w}'")

    if elements:
        reason_terms = ", ".join(elements)
        if score >= 0.90:
            return f"Near-identical scope sharing core terms: {reason_terms}"
        elif score >= 0.75:
            return f"High semantic similarity matching: {reason_terms}"
        else:
            return f"Related project scope mentioning: {reason_terms}"

    if score >= 0.90:
        return "Near-identical semantic formulation and scope"
    elif score >= 0.75:
        return "Strong thematic and functional alignment"
    else:
        return "Moderate semantic alignment across work descriptions"
