from __future__ import annotations

from app.services.text_utils import tokenize
from core.schemas import IntentSignal, UserProfile

CATEGORY_ALIASES = {
    "beauty": "All_Beauty",
    "skin": "All_Beauty",
    "skincare": "All_Beauty",
    "food": "Grocery_and_Gourmet_Food",
    "snack": "Grocery_and_Gourmet_Food",
    "drink": "Grocery_and_Gourmet_Food",
    "movie": "Movies_and_TV",
    "film": "Movies_and_TV",
    "watch": "Movies_and_TV",
    "game": "Video_Games",
    "play": "Video_Games",
}


def parse_intent(context: str, profile: UserProfile, include_categories: list[str]) -> IntentSignal:
    tokens = set(tokenize(context))
    categories = list(include_categories)
    for token, category in CATEGORY_ALIASES.items():
        if token in tokens and category not in categories:
            categories.append(category)
    constraints = [
        token
        for token in ["budget", "cheap", "affordable", "family", "weekend", "work", "school", "quick"]
        if token in tokens
    ]
    source_categories = set(profile.category_affinity)
    is_cross_domain = bool(source_categories and categories and not source_categories.intersection(categories))
    if not categories and any(word in tokens for word in ["based", "taste", "like", "liked"]):
        is_cross_domain = True
    is_cold_start = profile.cold_start
    needs_clarification = is_cold_start and len(tokens) < 5
    questions = []
    if needs_clarification:
        questions = [
            "What is one product, film, game, or food item you recently enjoyed?",
            "Are you optimizing for budget, quality, convenience, or something fun?",
        ]
    descriptors = _taste_descriptors(context, profile)
    return IntentSignal(
        raw_context=context,
        target_categories=categories,
        constraints=constraints,
        taste_descriptors=descriptors,
        is_cross_domain=is_cross_domain,
        is_cold_start=is_cold_start,
        needs_clarification=needs_clarification,
        clarification_questions=questions,
    )


def _taste_descriptors(context: str, profile: UserProfile) -> list[str]:
    tokens = tokenize(context)
    descriptors = []
    for token in tokens + profile.taste_tokens:
        if len(token) > 3 and token not in descriptors:
            descriptors.append(token)
        if len(descriptors) >= 12:
            break
    return descriptors
