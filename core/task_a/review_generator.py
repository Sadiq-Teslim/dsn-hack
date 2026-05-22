from __future__ import annotations

from app.config import Settings
from app.schemas import EvidenceItem, ProductDetails, UserPersona
from app.services.generation import fallback_review
from core.localization import retrieve_nigerian_exemplars
from core.orchestration import CoreLLMClient
from core.schemas import UserProfile


async def generate_grounded_review(
    settings: Settings,
    profile: UserProfile,
    product: ProductDetails,
    rating: float,
    evidence: list[EvidenceItem],
) -> tuple[str, bool, dict]:
    llm = CoreLLMClient(settings)
    exemplar_text = "\n".join(
        f"- {item.text}" for item in retrieve_nigerian_exemplars(profile, product.description, limit=4)
    )
    evidence_text = "\n".join(
        f"- {item.title} ({item.category}, {item.rating}/5): {item.reason}" for item in evidence
    )
    persona = profile.persona
    messages = [
        {
            "role": "system",
            "content": (
                "You generate user-faithful product reviews. Return strict JSON only with schema "
                "{\"review_text\":\"55-110 word first-person review\"}. Do not mention AI. "
                "Use the calibrated rating as fixed. Use Nigerian register only if it naturally fits."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Persona: {persona.name}, {persona.age_range}, {persona.occupation}, "
                f"{persona.location}. Budget: {persona.budget_level}. Tone: {persona.tone}. "
                f"Likes: {', '.join(persona.likes)}. Dislikes: {', '.join(persona.dislikes)}. "
                f"Vocabulary fingerprint: {', '.join(profile.vocabulary_fingerprint[:12])}.\n"
                f"Product: {product.title} ({product.category}). {product.description}\n"
                f"Calibrated rating: {rating}/5.\n"
                f"Retrieved review evidence:\n{evidence_text or 'None'}\n"
                f"Nigerian register exemplars:\n{exemplar_text or 'None'}\n"
                "Write one realistic review consistent with rating, evidence, and persona."
            ),
        },
    ]
    parsed, meta = await llm.json_chat(messages, temperature=0.42)
    text = parsed.get("review_text") if parsed else None
    if isinstance(text, str) and len(text.split()) >= 35:
        return " ".join(text.split()), bool(meta.get("fallback_used")), meta
    return fallback_review(UserPersona.model_validate(persona), product, rating, evidence), True, meta
