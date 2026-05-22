from __future__ import annotations

from app.services.text_utils import tokenize


POSITIVE = {"good", "great", "useful", "solid", "love", "recommend", "value", "reliable", "easy"}
NEGATIVE = {"bad", "poor", "weak", "overpriced", "slow", "waste", "harsh", "messy", "regret"}


def check_review_consistency(review_text: str, rating: float) -> str:
    tokens = set(tokenize(review_text))
    pos = len(tokens & POSITIVE)
    neg = len(tokens & NEGATIVE)
    if rating >= 4 and pos >= neg:
        return "passed: positive review language is consistent with calibrated rating"
    if rating <= 2.5 and neg >= pos:
        return "passed: critical review language is consistent with calibrated rating"
    if 2.5 < rating < 4.0:
        return "passed: mixed rating allows balanced review language"
    return "warning: review sentiment may need human inspection"
