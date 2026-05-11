from collections import Counter
from typing import Any

from app.schemas import EvidenceItem, ProductDetails, UserPersona
from app.services.persona import PersonaSummary
from app.services.text_utils import clamp, cosine_counter, keyword_set, stable_round, tokenize


def product_tokens(product: ProductDetails | dict[str, Any]) -> set[str]:
    if isinstance(product, ProductDetails):
        return keyword_set(
            product.title,
            product.category,
            product.description,
            product.brand or "",
            product.attributes,
        )
    return keyword_set(
        product.get("title", ""),
        product.get("category", ""),
        product.get("description", ""),
        product.get("brand", ""),
        product.get("attributes", {}),
    )


def retrieve_evidence(
    persona: UserPersona,
    product: ProductDetails,
    limit: int = 3,
) -> list[EvidenceItem]:
    target_tokens = product_tokens(product)
    evidence: list[tuple[float, EvidenceItem]] = []
    for history in persona.history:
        history_tokens = keyword_set(history.title, history.category, history.review_text)
        category_bonus = 0.25 if history.category == product.category else 0.0
        overlap = len(target_tokens & history_tokens) / max(1, len(target_tokens | history_tokens))
        score = overlap + category_bonus + (history.rating / 20)
        evidence.append(
            (
                score,
                EvidenceItem(
                    title=history.title,
                    category=history.category,
                    rating=history.rating,
                    reason=f"Similar category/style signal with {score:.2f} retrieval strength.",
                ),
            )
        )
    return [item for _, item in sorted(evidence, key=lambda pair: pair[0], reverse=True)[:limit]]


def predict_rating(persona: UserPersona, product: ProductDetails, catalog_item: dict[str, Any] | None = None) -> tuple[float, float, str]:
    summary = PersonaSummary(persona)
    base_rating = float(catalog_item.get("average_rating", 3.8)) if catalog_item else 3.8
    category_affinity = summary.category_affinity.get(product.category, summary.average_rating)
    target_tokens = product_tokens(product)
    preference_overlap = len(target_tokens & summary.preference_tokens()) / max(1, len(target_tokens))
    dislike_overlap = len(target_tokens & summary.dislike_tokens()) / max(1, len(target_tokens))

    budget_adjustment = 0.0
    price = product.price if product.price is not None else (catalog_item or {}).get("price")
    if price is not None:
        if summary.persona.budget_level.lower() == "low" and price > 30:
            budget_adjustment -= 0.35
        elif summary.persona.budget_level.lower() == "medium" and price > 80:
            budget_adjustment -= 0.2
        elif summary.persona.budget_level.lower() == "high" and price > 40:
            budget_adjustment += 0.1

    predicted = (
        0.45 * base_rating
        + 0.35 * category_affinity
        + 0.20 * summary.average_rating
        + preference_overlap * 0.9
        - dislike_overlap * 0.8
        + budget_adjustment
    )
    rating = stable_round(clamp(predicted, 1.0, 5.0), 1)
    confidence = stable_round(
        clamp(0.52 + 0.08 * len(persona.history) + preference_overlap * 0.25, 0.45, 0.92)
    )
    reasoning = (
        f"Rating blends item quality ({base_rating:.1f}), user average "
        f"({summary.average_rating:.1f}), category affinity ({category_affinity:.1f}), "
        f"preference overlap ({preference_overlap:.2f}), and budget fit."
    )
    return rating, confidence, reasoning


def rank_products(
    persona: UserPersona,
    products: list[dict[str, Any]],
    context: str,
    include_categories: list[str],
    top_k: int,
) -> list[dict[str, Any]]:
    summary = PersonaSummary(persona)
    context_counter = Counter(tokenize(context))
    preference_tokens = summary.preference_tokens()
    dislike_tokens = summary.dislike_tokens()
    ranked: list[dict[str, Any]] = []

    for product in products:
        if include_categories and product["category"] not in include_categories:
            continue
        tokens = product_tokens(product)
        text_counter = Counter(tokenize(" ".join([product["title"], product["description"], product["category"]])))
        preference_match = len(tokens & preference_tokens) / max(1, len(tokens))
        dislike_match = len(tokens & dislike_tokens) / max(1, len(tokens))
        context_match = cosine_counter(context_counter, text_counter) if context else 0.0
        category_affinity = summary.category_affinity.get(product["category"], summary.average_rating)
        popularity = clamp(float(product.get("average_rating", 3.8)) / 5, 0, 1)
        volume = clamp(float(product.get("rating_number", 1)) / 2000, 0, 1)

        budget_penalty = 0.0
        price = product.get("price")
        if price is not None:
            if summary.persona.budget_level.lower() == "low" and price > 30:
                budget_penalty = 0.18
            elif summary.persona.budget_level.lower() == "medium" and price > 80:
                budget_penalty = 0.08

        score = (
            0.22 * popularity
            + 0.08 * volume
            + 0.22 * (category_affinity / 5)
            + 0.30 * preference_match
            + 0.18 * context_match
            - 0.22 * dislike_match
            - budget_penalty
        )
        matched_preferences = sorted((tokens & preference_tokens) - {"nigeria", "nigerian"})[:5]
        ranked.append(
            {
                **product,
                "score": stable_round(clamp(score, 0, 1)),
                "matched_preferences": matched_preferences,
            }
        )

    return sorted(ranked, key=lambda item: item["score"], reverse=True)[:top_k]
