from __future__ import annotations

from app.config import Settings
from app.services.text_utils import tokenize
from core.orchestration import CoreLLMClient
from core.schemas import IntentSignal, UserProfile

BRIDGE_MAP = {
    "comedy": ["light", "social", "fun", "weekend", "family"],
    "political": ["serious", "smart", "drama", "premium", "work"],
    "family": ["safe", "share", "gentle", "home", "visitors"],
    "football": ["competitive", "multiplayer", "friends", "weekend"],
    "coffee": ["morning", "work", "routine", "dependable"],
    "skincare": ["gentle", "heat", "daily", "polished"],
    "budget": ["affordable", "value", "quick", "practical"],
}

STOP_DESCRIPTORS = {
    "based",
    "recommend",
    "suggest",
    "taste",
    "food",
    "movie",
    "movies",
    "item",
    "items",
    "product",
    "products",
}


async def bridge_cross_domain(
    settings: Settings,
    profile: UserProfile,
    intent: IntentSignal,
) -> tuple[IntentSignal, bool, dict]:
    if intent.is_cross_domain:
        llm = CoreLLMClient(settings)
        parsed, meta = await llm.json_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Extract abstract taste descriptors for cross-domain recommendation. "
                        "Return strict JSON only: {\"descriptors\":[\"short descriptor\"]}. "
                        "Do not recommend items."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Persona likes: {profile.persona.likes}. Interests: {profile.persona.interests}. "
                        f"History categories: {list(profile.category_affinity)}. "
                        f"Taste tokens: {profile.taste_tokens[:16]}. "
                        f"User request: {intent.raw_context}. Target categories: {intent.target_categories}. "
                        "Bridge source-domain taste into target-domain descriptors. Use abstract descriptors like "
                        "'likes social humour', 'values quick practical routines', 'prefers culturally familiar experiences', "
                        "or 'wants shareable family experiences'. Do not return generic query words."
                    ),
                },
            ],
            temperature=0.18,
        )
        descriptors = parsed.get("descriptors") if parsed else None
        if isinstance(descriptors, list) and descriptors:
            cleaned = _clean_descriptors([str(descriptor) for descriptor in descriptors])
            seed = _clean_descriptors(intent.taste_descriptors + profile.taste_tokens)
            intent.taste_descriptors = []
            for descriptor in cleaned + seed:
                if descriptor not in intent.taste_descriptors:
                    intent.taste_descriptors.append(descriptor)
            if "cross-domain taste transfer" not in intent.taste_descriptors:
                intent.taste_descriptors.append("cross-domain taste transfer")
            intent.taste_descriptors = intent.taste_descriptors[:18]
            return intent, bool(meta.get("fallback_used")), meta

    return _fallback_bridge(profile, intent), True, {"configured": False, "fallback_used": True}


def _fallback_bridge(profile: UserProfile, intent: IntentSignal) -> IntentSignal:
    descriptors: list[str] = []
    source = " ".join(profile.taste_tokens + list(profile.category_affinity))
    for token in tokenize(source):
        for descriptor in BRIDGE_MAP.get(token, []):
            if descriptor not in descriptors:
                descriptors.append(descriptor)
    for descriptor in _clean_descriptors(profile.taste_tokens + intent.taste_descriptors):
        if descriptor not in descriptors:
            descriptors.append(descriptor)
    if intent.is_cross_domain and "cross-domain taste transfer" not in descriptors:
        descriptors.append("cross-domain taste transfer")
    intent.taste_descriptors = descriptors[:18]
    return intent


def _clean_descriptors(values: list[str]) -> list[str]:
    cleaned: list[str] = []
    for value in values:
        descriptor = " ".join(str(value).lower().strip().split())
        if len(descriptor) < 4 or descriptor in STOP_DESCRIPTORS:
            continue
        if descriptor not in cleaned:
            cleaned.append(descriptor)
    return cleaned
