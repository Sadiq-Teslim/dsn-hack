from __future__ import annotations

from app.services.text_utils import tokenize
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


def bridge_cross_domain(profile: UserProfile, intent: IntentSignal) -> IntentSignal:
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
