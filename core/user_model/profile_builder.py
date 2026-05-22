from __future__ import annotations

import math
from collections import Counter, defaultdict

from app.schemas import HistoryItem, UserPersona
from app.services.text_utils import tokenize
from core.schemas import NigerianRegister, UserProfile


def build_user_profile(persona: UserPersona) -> UserProfile:
    ratings = [float(item.rating) for item in persona.history]
    mean = sum(ratings) / len(ratings) if ratings else 3.8
    variance = sum((rating - mean) ** 2 for rating in ratings) / len(ratings) if ratings else 0.0
    std = math.sqrt(variance)
    mode = Counter(ratings).most_common(1)[0][0] if ratings else 4.0
    skew = _skew(ratings, mean, std)
    category_affinity = _category_affinity(persona.history)
    token_counter = _persona_tokens(persona)
    vocabulary = [token for token, _ in token_counter.most_common(20)]
    taste_tokens = _taste_tokens(persona, token_counter)
    embedding = {
        token: count / max(1, sum(token_counter.values()))
        for token, count in token_counter.most_common(60)
    }
    return UserProfile(
        persona=persona,
        history_count=len(persona.history),
        rating_mean=round(mean, 3),
        rating_std=round(std, 3),
        rating_mode=mode,
        rating_skew=round(skew, 3),
        rating_bias=round(mean - 3.8, 3),
        category_affinity=category_affinity,
        vocabulary_fingerprint=vocabulary,
        taste_tokens=taste_tokens,
        taste_embedding=embedding,
        nigerian_register=_infer_register(persona),
        cold_start=len(persona.history) < 2,
    )


def _skew(ratings: list[float], mean: float, std: float) -> float:
    if not ratings or std == 0:
        return 0.0
    return sum(((rating - mean) / std) ** 3 for rating in ratings) / len(ratings)


def _category_affinity(history: list[HistoryItem]) -> dict[str, float]:
    by_category: dict[str, list[float]] = defaultdict(list)
    for item in history:
        by_category[item.category].append(float(item.rating))
    return {
        category: round(sum(values) / len(values), 3)
        for category, values in by_category.items()
    }


def _persona_tokens(persona: UserPersona) -> Counter[str]:
    parts: list[str] = [
        persona.location,
        persona.occupation,
        persona.tone,
        persona.budget_level,
        persona.language_preference,
        persona.cultural_context,
        " ".join(persona.interests),
        " ".join(persona.likes),
        " ".join(persona.dislikes),
    ]
    for item in persona.history:
        parts.append(f"{item.title} {item.category} {item.review_text}")
    return Counter(tokenize(" ".join(parts)))


def _taste_tokens(persona: UserPersona, token_counter: Counter[str]) -> list[str]:
    blocked = {
        "nigeria",
        "nigerian",
        "lagos",
        "abuja",
        "port",
        "harcourt",
        "english",
        "with",
        "and",
        "for",
        "the",
    }
    explicit = tokenize(" ".join(persona.interests + persona.likes))
    tokens = []
    for token in explicit + [token for token, _ in token_counter.most_common(40)]:
        if len(token) > 2 and token not in blocked and token not in tokens:
            tokens.append(token)
        if len(tokens) >= 20:
            break
    return tokens


def _infer_register(persona: UserPersona) -> NigerianRegister:
    text = f"{persona.language_preference} {persona.tone} {persona.cultural_context}".lower()
    if "pidgin" in text:
        return NigerianRegister.PIDGIN
    if "yoruba" in text:
        return NigerianRegister.YORUBA
    if "hausa" in text:
        return NigerianRegister.HAUSA
    if "igbo" in text:
        return NigerianRegister.IGBO
    if "judge" in text or "formal" in text:
        return NigerianRegister.FORMAL
    if "nigeria" in f"{persona.location} {persona.cultural_context}".lower():
        return NigerianRegister.STANDARD
    return NigerianRegister.STANDARD
