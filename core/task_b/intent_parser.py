from __future__ import annotations

from app.services.text_utils import tokenize
from core.schemas import IntentSignal, UserProfile

CATEGORY_ALIASES = {
    "beauty": "All_Beauty",
    "skin": "All_Beauty",
    "skincare": "All_Beauty",
    "food": "Grocery_and_Gourmet_Food",
    "foods": "Grocery_and_Gourmet_Food",
    "grocery": "Grocery_and_Gourmet_Food",
    "groceries": "Grocery_and_Gourmet_Food",
    "meal": "Grocery_and_Gourmet_Food",
    "meals": "Grocery_and_Gourmet_Food",
    "breakfast": "Grocery_and_Gourmet_Food",
    "snack": "Grocery_and_Gourmet_Food",
    "snacks": "Grocery_and_Gourmet_Food",
    "drink": "Grocery_and_Gourmet_Food",
    "drinks": "Grocery_and_Gourmet_Food",
    "movie": "Movies_and_TV",
    "movies": "Movies_and_TV",
    "film": "Movies_and_TV",
    "films": "Movies_and_TV",
    "watch": "Movies_and_TV",
    "game": "Video_Games",
    "games": "Video_Games",
    "play": "Video_Games",
    "book": "Books",
    "books": "Books",
    "read": "Books",
    "reading": "Books",
    "novel": "Books",
    "novels": "Books",
}


def parse_intent(context: str, profile: UserProfile, include_categories: list[str]) -> IntentSignal:
    token_list = tokenize(context)
    tokens = set(token_list)
    categories = list(include_categories)
    mentioned = [
        (index, CATEGORY_ALIASES[token])
        for index, token in enumerate(token_list)
        if token in CATEGORY_ALIASES
    ]
    recommend_index = _first_index(token_list, {"recommend", "suggest", "show", "find"})
    if include_categories:
        target_mentions = [
            category
            for index, category in mentioned
            if recommend_index is not None and index > recommend_index and category not in categories
        ]
    else:
        target_mentions = _target_categories_from_mentions(mentioned, recommend_index)
    for category in target_mentions:
        if category not in categories:
            categories.append(category)
    if not categories:
        for category in _infer_practical_categories(tokens):
            if category not in categories:
                categories.append(category)
    constraints = [
        token
        for token in [
            "budget",
            "cheap",
            "affordable",
            "family",
            "weekend",
            "work",
            "school",
            "quick",
            "routine",
            "useful",
            "week",
            "daily",
            "buy",
        ]
        if token in tokens
    ]
    source_categories = set(profile.category_affinity)
    mentioned_categories = {category for _, category in mentioned}
    source_mentions = mentioned_categories - set(categories)
    is_cross_domain = bool(source_mentions and categories and source_mentions.difference(categories))
    if not is_cross_domain:
        is_cross_domain = bool(source_categories and categories and not source_categories.intersection(categories))
    if not is_cross_domain and categories and any(word in tokens for word in ["based", "taste", "like", "liked"]):
        is_cross_domain = len(mentioned_categories | source_categories) > 1
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
        unsupported_targets=[],
        constraints=constraints,
        taste_descriptors=descriptors,
        is_cross_domain=is_cross_domain,
        is_cold_start=is_cold_start,
        needs_clarification=needs_clarification,
        clarification_questions=questions,
    )


def _first_index(tokens: list[str], words: set[str]) -> int | None:
    for index, token in enumerate(tokens):
        if token in words:
            return index
    return None


def _target_categories_from_mentions(
    mentioned: list[tuple[int, str]],
    recommend_index: int | None,
) -> list[str]:
    if not mentioned:
        return []
    if recommend_index is not None:
        after = [category for index, category in mentioned if index > recommend_index]
        if after:
            return list(dict.fromkeys(after))
    return list(dict.fromkeys(category for _, category in mentioned))


def _infer_practical_categories(tokens: set[str]) -> list[str]:
    if tokens & {"book", "books", "read", "reading", "novel", "novels"}:
        return ["Books"]
    if tokens & {"food", "meal", "meals", "breakfast", "snack", "snacks", "drink", "drinks", "grocery", "groceries"}:
        return ["Grocery_and_Gourmet_Food"]
    if tokens & {"beauty", "skin", "skincare", "sunscreen", "cream", "daily"}:
        return ["All_Beauty"]
    if tokens & {"movie", "movies", "film", "films", "watch", "comedy", "drama"}:
        return ["Movies_and_TV"]
    if tokens & {"game", "games", "play", "football", "multiplayer"}:
        return ["Video_Games"]
    if tokens & {"useful", "routine", "week", "school", "work", "quick", "budget", "affordable", "cheap"}:
        return ["Grocery_and_Gourmet_Food", "All_Beauty"]
    if tokens & {"fun", "weekend", "friends", "relax"}:
        return ["Movies_and_TV", "Video_Games", "Grocery_and_Gourmet_Food"]
    return []


def _taste_descriptors(context: str, profile: UserProfile) -> list[str]:
    tokens = tokenize(context)
    descriptors = []
    for token in tokens + profile.taste_tokens:
        if len(token) > 3 and token not in descriptors:
            descriptors.append(token)
        if len(descriptors) >= 12:
            break
    return descriptors
