from app.config import Settings
from app.schemas import EvidenceItem, ProductDetails, UserPersona
from app.services.groq_client import GroqClient
from app.services.persona import PersonaSummary


def fallback_review(
    persona: UserPersona,
    product: ProductDetails,
    rating: float,
    evidence: list[EvidenceItem],
) -> str:
    strengths = persona.likes[:2] or persona.interests[:2] or ["practical value"]
    caveat = persona.dislikes[0] if persona.dislikes else "anything that feels overpriced"
    local_note = ""
    if "nigeria" in f"{persona.location} {persona.cultural_context}".lower():
        local_note = " For my Nigerian day-to-day, the convenience and value matter a lot."
    evidence_note = ""
    if evidence:
        evidence_note = f" It reminds me of what I liked about {evidence[0].title.lower()}."
    return (
        f"I would give {product.title} {rating:.1f} stars. "
        f"It fits my taste for {', '.join(strengths)}, and the {product.category.replace('_', ' ')} "
        f"use case is clear.{local_note}{evidence_note} "
        f"My only watch-out is {caveat}, but overall it feels like something I would recommend."
    )


def fallback_recommendation_summary(persona: UserPersona, context: str) -> str:
    context_line = f" for '{context}'" if context else ""
    return (
        f"Ranked items{context_line} by matching {persona.name}'s history, stated likes, "
        f"budget level, category affinity, and cold-start product quality signals."
    )


async def generate_review_text(
    settings: Settings,
    persona: UserPersona,
    product: ProductDetails,
    rating: float,
    evidence: list[EvidenceItem],
) -> tuple[str, bool]:
    client = GroqClient(settings)
    summary = PersonaSummary(persona)
    evidence_text = "\n".join(
        f"- {item.title} ({item.category}, {item.rating}/5): {item.reason}" for item in evidence
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You simulate concise product reviews from a user persona. "
                "Write like a real reviewer, not an assistant. Avoid stereotypes. "
                "Use Nigerian context only when it naturally affects value, convenience, tone, or use."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{summary.describe_for_prompt(product)}\n"
                f"Predicted rating: {rating}/5\n"
                f"Retrieved evidence:\n{evidence_text or 'No close evidence.'}\n"
                "Write one review of 55-95 words. Do not mention that you are an AI."
            ),
        },
    ]
    generated = await client.chat(messages, temperature=0.55)
    if generated:
        return generated, False
    return fallback_review(persona, product, rating, evidence), True


async def generate_recommendation_summary(
    settings: Settings,
    persona: UserPersona,
    context: str,
    ranked_titles: list[str],
) -> tuple[str, bool]:
    client = GroqClient(settings)
    messages = [
        {
            "role": "system",
            "content": "Explain recommendation rankings in one concise paragraph for judges.",
        },
        {
            "role": "user",
            "content": (
                f"Persona: {PersonaSummary(persona).describe_for_prompt()}\n"
                f"Context: {context or 'None'}\n"
                f"Ranked items: {', '.join(ranked_titles)}\n"
                "Explain why this ranking is personalized in 45-80 words."
            ),
        },
    ]
    generated = await client.chat(messages, temperature=0.35)
    if generated:
        return generated, False
    return fallback_recommendation_summary(persona, context), True
