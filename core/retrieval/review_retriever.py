from __future__ import annotations

from typing import Any

from app.schemas import EvidenceItem, ProductDetails, UserPersona
from app.services.text_utils import keyword_set, stable_round
from core.schemas import UserProfile


def retrieve_review_examples(
    persona: UserPersona,
    profile: UserProfile,
    product: ProductDetails,
    corpus_reviews: list[dict[str, Any]] | None = None,
    limit: int = 5,
) -> list[EvidenceItem]:
    target_tokens = keyword_set(product.title, product.category, product.description, product.attributes)
    scored: list[tuple[float, EvidenceItem]] = []

    for item in persona.history:
        tokens = keyword_set(item.title, item.category, item.review_text)
        category_bonus = 0.28 if item.category == product.category else 0.0
        taste_bonus = len(tokens & set(profile.taste_tokens)) / max(1, len(profile.taste_tokens)) * 0.18
        overlap = len(target_tokens & tokens) / max(1, len(target_tokens | tokens))
        score = overlap + category_bonus + taste_bonus + item.rating / 25
        scored.append(
            (
                score,
                EvidenceItem(
                    title=item.title,
                    category=item.category,
                    rating=item.rating,
                    source="own_history",
                    review_text=item.review_text,
                    retrieval_score=stable_round(score, 3),
                    reason=(
                        f"Own-history exemplar with {stable_round(score, 2):.2f} retrieval strength; "
                        f"captures {item.category.replace('_', ' ')} tone and rating behavior."
                    ),
                ),
            )
        )

    for review in corpus_reviews or []:
        if review.get("user_id") == persona.name:
            continue
        tokens = keyword_set(
            review.get("title", ""),
            review.get("category", ""),
            review.get("review_text", ""),
        )
        overlap = len(target_tokens & tokens) / max(1, len(target_tokens | tokens))
        category_bonus = 0.22 if review.get("category") == product.category else 0.0
        taste_bonus = len(tokens & set(profile.taste_tokens)) / max(1, len(profile.taste_tokens)) * 0.12
        score = overlap + category_bonus + taste_bonus + float(review.get("rating", 3)) / 35
        if score < 0.18:
            continue
        scored.append(
            (
                score,
                EvidenceItem(
                    title=str(review.get("title", "Amazon review exemplar")),
                    category=str(review.get("category", product.category)),
                    rating=float(review.get("rating", 3)),
                    source="similar_user",
                    review_text=str(review.get("review_text", "")),
                    retrieval_score=stable_round(score, 3),
                    reason=(
                        f"Similar-user review exemplar with {stable_round(score, 2):.2f} retrieval strength."
                    ),
                ),
            )
        )

    return [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]
