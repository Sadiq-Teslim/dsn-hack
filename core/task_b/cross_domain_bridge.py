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
                        "Bridge source-domain taste into target-domain descriptors."
                    ),
                },
            ],
            temperature=0.18,
        )
        descriptors = parsed.get("descriptors") if parsed else None
        if isinstance(descriptors, list) and descriptors:
            for descriptor in descriptors:
                clean = str(descriptor).strip().lower()
                if clean and clean not in intent.taste_descriptors:
                    intent.taste_descriptors.append(clean)
            if "cross-domain taste transfer" not in intent.taste_descriptors:
                intent.taste_descriptors.append("cross-domain taste transfer")
            intent.taste_descriptors = intent.taste_descriptors[:18]
            return intent, bool(meta.get("fallback_used")), meta

    return _fallback_bridge(profile, intent), True, {"configured": False, "fallback_used": True}


def _fallback_bridge(profile: UserProfile, intent: IntentSignal) -> IntentSignal:
    descriptors = list(intent.taste_descriptors)
    source = " ".join(profile.taste_tokens + list(profile.category_affinity))
    for token in tokenize(source):
        for descriptor in BRIDGE_MAP.get(token, []):
            if descriptor not in descriptors:
                descriptors.append(descriptor)
    if intent.is_cross_domain and "cross-domain taste transfer" not in descriptors:
        descriptors.append("cross-domain taste transfer")
    intent.taste_descriptors = descriptors[:18]
    return intent
