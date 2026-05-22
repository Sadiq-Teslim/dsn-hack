from __future__ import annotations

from collections import Counter
from typing import Any

from app.services.text_utils import clamp, cosine_counter, keyword_set, stable_round, tokenize
from core.schemas import CandidateItem, IntentSignal, UserProfile


STOPWORDS = {
    "and",
    "the",
    "for",
    "with",
    "this",
    "that",
    "from",
    "into",
    "user",
    "nigeria",
    "nigerian",
    "shopper",
}


def shortlist_items(
    profile: UserProfile,
    products: list[dict[str, Any]],
    intent: IntentSignal,
    limit: int = 50,
) -> list[CandidateItem]:
    context_counter = Counter(tokenize(intent.raw_context))
    preference_tokens = set(profile.taste_tokens)
    dislike_tokens = keyword_set(profile.persona.dislikes)
    descriptor_tokens = set(tokenize(" ".join(intent.taste_descriptors)))
    target_categories = set(intent.target_categories)
    candidates: list[CandidateItem] = []
    candidates.extend(
        _score_products(
            profile,
            products,
            intent,
            context_counter,
            preference_tokens,
            dislike_tokens,
            descriptor_tokens,
            target_categories,
        )
    )
    if target_categories and len(candidates) < limit:
        existing = {item.item_id for item in candidates}
        candidates.extend(
            item
            for item in _score_products(
                profile,
                products,
                intent,
                context_counter,
                preference_tokens,
                dislike_tokens,
                descriptor_tokens,
                set(),
            )
            if item.item_id not in existing
        )

    if target_categories:
        return sorted(
            candidates,
            key=lambda item: (item.category in target_categories, item.local_score),
            reverse=True,
        )[:limit]
    return sorted(candidates, key=lambda item: item.local_score, reverse=True)[:limit]


def _score_products(
    profile: UserProfile,
    products: list[dict[str, Any]],
    intent: IntentSignal,
    context_counter: Counter[str],
    preference_tokens: set[str],
    dislike_tokens: set[str],
    descriptor_tokens: set[str],
    target_categories: set[str],
) -> list[CandidateItem]:
    candidates: list[CandidateItem] = []

    for product in products:
        if target_categories and product.get("category") not in target_categories:
            continue
        tokens = keyword_set(
            product.get("title", ""),
            product.get("category", ""),
            product.get("description", ""),
            product.get("brand", ""),
            product.get("attributes", {}),
        )
        text_counter = Counter(
            tokenize(
                " ".join(
                    [
                        str(product.get("title", "")),
                        str(product.get("description", "")),
                        str(product.get("category", "")),
                        str(product.get("attributes", {})),
                    ]
                )
            )
        )
        preference_match = len(tokens & preference_tokens) / max(1, len(tokens))
        descriptor_match = len(tokens & descriptor_tokens) / max(1, len(tokens))
        dislike_match = len(tokens & dislike_tokens) / max(1, len(tokens))
        context_match = cosine_counter(context_counter, text_counter) if intent.raw_context else 0.0
        category_affinity = profile.category_affinity.get(product.get("category", ""), profile.rating_mean)
        popularity = clamp(float(product.get("average_rating", 3.8)) / 5, 0, 1)
        volume = clamp(float(product.get("rating_number", 1)) / 2000, 0, 1)
        budget_penalty = _budget_penalty(profile, product.get("price"))

        local_score = (
            0.18 * popularity
            + 0.06 * volume
            + 0.18 * (category_affinity / 5)
            + 0.24 * preference_match
            + 0.20 * context_match
            + 0.18 * descriptor_match
            - 0.22 * dislike_match
            - budget_penalty
        )
        matched_preferences = sorted(
            token
            for token in ((tokens & preference_tokens) | (tokens & descriptor_tokens))
            if token not in STOPWORDS and len(token) > 2
        )[:6]
        candidates.append(
            CandidateItem(
                item_id=str(product.get("item_id", product.get("title", ""))),
                title=str(product.get("title", "")),
                category=str(product.get("category", "")),
                score=stable_round(clamp(local_score, 0, 1)),
                local_score=stable_round(clamp(local_score, 0, 1)),
                reason=_local_reason(product, matched_preferences, context_match),
                matched_preferences=matched_preferences,
                price=product.get("price"),
                metadata=product,
            )
        )
    return candidates


def _budget_penalty(profile: UserProfile, price: object) -> float:
    if price is None:
        return 0.0
    try:
        price_float = float(price)
    except (TypeError, ValueError):
        return 0.0
    budget = profile.persona.budget_level.lower()
    if budget == "low" and price_float > 30:
        return 0.18
    if budget == "medium" and price_float > 80:
        return 0.08
    return 0.0


def _local_reason(product: dict[str, Any], matches: list[str], context_match: float) -> str:
    matched = ", ".join(matches) or "cold-start quality"
    return (
        f"Local shortlist fit: {product.get('average_rating', 3.8):.1f}/5 catalog signal, "
        f"context match {context_match:.2f}, matched {matched}."
    )
