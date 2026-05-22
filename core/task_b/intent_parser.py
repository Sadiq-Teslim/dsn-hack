from __future__ import annotations

import re

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
    explicit_new_user = _explicit_new_user(context, tokens)
    ambiguous_discovery = _ambiguous_discovery_request(context, tokens)
    min_price, max_price, max_price_exclusive, price_is_approximate = _extract_price_bounds(context)
    excluded_categories = _excluded_categories_from_context(token_list)
    categories = list(include_categories)
    mentioned = [
        (index, CATEGORY_ALIASES[token])
        for index, token in enumerate(token_list)
        if token in CATEGORY_ALIASES and CATEGORY_ALIASES[token] not in excluded_categories
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
        if category not in categories and category not in excluded_categories:
            categories.append(category)
    if not categories:
        for category in _infer_practical_categories(tokens):
            if category not in categories and category not in excluded_categories:
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
    if max_price is not None and "price_limit" not in constraints:
        constraints.append("price_limit")
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
    is_cold_start = profile.cold_start or explicit_new_user
    needs_clarification = bool((is_cold_start and (len(tokens) < 8 or ambiguous_discovery)) or ambiguous_discovery)
    questions = []
    if needs_clarification:
        questions = [
            "What kind of thing are you looking for: books, food, movies, games, beauty products, or something else?",
            "What matters most for this choice: budget, quality, convenience, family use, or something fun?",
        ]
    descriptors = _taste_descriptors(context, profile)
    return IntentSignal(
        raw_context=context,
        target_categories=categories,
        unsupported_targets=[],
        excluded_categories=excluded_categories,
        constraints=constraints,
        min_price=min_price,
        max_price=max_price,
        max_price_exclusive=max_price_exclusive,
        price_is_approximate=price_is_approximate,
        taste_descriptors=descriptors,
        is_cross_domain=is_cross_domain,
        is_cold_start=is_cold_start,
        needs_clarification=needs_clarification,
        clarification_questions=questions,
    )


def _explicit_new_user(context: str, tokens: set[str]) -> bool:
    text = context.lower()
    return bool(
        {"new", "first", "start", "starting"} & tokens
        and (
            "new here" in text
            or "first time" in text
            or "new user" in text
            or "new to this" in text
            or "just starting" in text
        )
    )


def _ambiguous_discovery_request(context: str, tokens: set[str]) -> bool:
    text = context.lower()
    broad_request = bool(
        "find something" in text
        or "recommend something" in text
        or "show me something" in text
        or "help me choose" in text
        or "help me find" in text
    )
    has_specific_category = any(token in CATEGORY_ALIASES for token in tokens)
    has_specific_constraint = bool(
        tokens
        & {
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
            "daily",
            "buy",
            "fun",
        }
    )
    has_price = any(char.isdigit() for char in context) or "$" in context
    return broad_request and not (has_specific_category or has_specific_constraint or has_price)


def _excluded_categories_from_context(tokens: list[str]) -> list[str]:
    excluded = []
    negators = {"no", "not", "without", "exclude", "excluding", "except", "avoid", "dont", "don't"}
    for index, token in enumerate(tokens):
        category = CATEGORY_ALIASES.get(token)
        if not category:
            continue
        previous = set(tokens[max(0, index - 4):index])
        if previous & negators and category not in excluded:
            excluded.append(category)
    return excluded


def _extract_price_bounds(context: str) -> tuple[float | None, float | None, bool, bool]:
    text = context.lower().replace(",", "")
    approximate = bool(re.search(r"\b(?:around|about|roughly|approximately|close\s+to)\b", text))
    range_match = re.search(r"\$?\s*(\d+(?:\.\d+)?)\s*(?:-|to|and)\s*\$?\s*(\d+(?:\.\d+)?)\b", text)
    if range_match:
        low = float(range_match.group(1))
        high = float(range_match.group(2))
        min_price, max_price = sorted([low, high])
        return min_price, max_price, False, approximate
    patterns = [
        (r"\b(?:below|under|less\s+than)\s*\$?\s*(\d+(?:\.\d+)?)\b", True),
        (r"\b(?:at\s+most|not\s+more\s+than|no\s+more\s+than|maximum|max(?:imum)?\s+of|up\s+to)\s*\$?\s*(\d+(?:\.\d+)?)\b", False),
        (r"\$?\s*(\d+(?:\.\d+)?)\s*(?:or\s+less|and\s+below|and\s+under)\b", False),
        (r"(?:<=|≤)\s*\$?\s*(\d+(?:\.\d+)?)\b", False),
        (r"<\s*\$?\s*(\d+(?:\.\d+)?)\b", True),
    ]
    for pattern, exclusive in patterns:
        match = re.search(pattern, text)
        if match:
            return None, float(match.group(1)), exclusive, approximate
    min_patterns = [
        r"\b(?:above|over|more\s+than)\s*\$?\s*(\d+(?:\.\d+)?)\b",
        r"\b(?:at\s+least|minimum|min(?:imum)?\s+of)\s*\$?\s*(\d+(?:\.\d+)?)\b",
        r">\s*\$?\s*(\d+(?:\.\d+)?)\b",
    ]
    for pattern in min_patterns:
        match = re.search(pattern, text)
        if match:
            return float(match.group(1)), None, False, approximate
    return None, None, False, approximate


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
