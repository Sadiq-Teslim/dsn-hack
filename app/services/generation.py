import json

from pydantic import BaseModel, Field, ValidationError

from app.config import Settings
from app.schemas import EvidenceItem, ProductDetails, UserPersona
from app.services.groq_client import GroqClient
from app.services.persona import PersonaSummary


class ReviewDraft(BaseModel):
    review_text: str = Field(min_length=40, max_length=900)


class RecommendationDraft(BaseModel):
    summary: str = Field(min_length=35, max_length=700)


class YarnDraft(BaseModel):
    voice_script: str = Field(min_length=20, max_length=900)
    judge_note: str = Field(min_length=20, max_length=500)


def _json_object(text: str | None) -> dict | None:
    if not text:
        return None
    stripped = text.strip()
    if stripped.startswith("```"):
        stripped = stripped.strip("`")
        stripped = stripped.removeprefix("json").strip()
    start = stripped.find("{")
    end = stripped.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        return json.loads(stripped[start : end + 1])
    except json.JSONDecodeError:
        return None


def _clean_review_text(text: str) -> str:
    cleaned = " ".join(text.split())
    blocked = ["as an ai", "i am an ai", "language model"]
    if any(phrase in cleaned.lower() for phrase in blocked):
        raise ValueError("Generated text exposed assistant framing.")
    return cleaned


def fallback_review(
    persona: UserPersona,
    product: ProductDetails,
    rating: float,
    evidence: list[EvidenceItem],
) -> str:
    strengths = persona.likes[:2] or persona.interests[:2] or ["practical value"]
    caveat = persona.dislikes[0] if persona.dislikes else "anything that feels overpriced"
    evidence_note = _evidence_sentence(evidence)
    local_note = _local_context_sentence(persona)
    category = product.category.replace("_", " ")
    if rating >= 4.5:
        verdict = (
            f"I would happily give {product.title} {rating:.1f} stars. The {category} fit is strong, "
            f"especially because I care about {', '.join(strengths)}."
        )
        close = "I would buy it again and recommend it without much hesitation."
    elif rating >= 3.8:
        verdict = (
            f"{product.title} lands at {rating:.1f} stars for me. It does enough things right for the "
            f"{category} use case, especially around {', '.join(strengths)}."
        )
        close = f"I would recommend it, but I would still watch out for {caveat}."
    elif rating >= 2.8:
        verdict = (
            f"I would keep {product.title} around {rating:.1f} stars. It is not a total miss, but the "
            f"value feels mixed for my needs."
        )
        close = f"If {caveat} matters to you, I would compare alternatives first."
    else:
        verdict = (
            f"{product.title} is a {rating:.1f}-star experience for me. It misses too much of what I "
            f"expect from this kind of {category} product."
        )
        close = f"I would not recommend it unless the quality improves or the price drops clearly."
    return " ".join(f"{verdict} {local_note} {evidence_note} {close}".split())


def _evidence_sentence(evidence: list[EvidenceItem]) -> str:
    if not evidence:
        return ""
    top = evidence[0]
    source = "my own past review" if top.source == "own_history" else "a similar review"
    review = (top.review_text or top.reason).strip()
    if len(review) > 120:
        review = review[:117].rstrip() + "..."
    return f"It connects with {source} for {top.title.lower()}: {review}"


def _local_context_sentence(persona: UserPersona) -> str:
    text = f"{persona.location} {persona.cultural_context}".lower()
    if "lagos" in text:
        return "For a Lagos routine, price, speed, and everyday usefulness matter here."
    if "abuja" in text:
        return "For an Abuja work routine, I am weighing polish, reliability, and daily convenience."
    if "port harcourt" in text:
        return "For home and family use, I care about whether everyone can actually benefit from it."
    if "nigeria" in text:
        return "For my Nigerian day-to-day, value and practical usefulness matter."
    return ""


def fallback_recommendation_summary(persona: UserPersona, context: str) -> str:
    context_line = f" for '{context}'" if context else ""
    return (
        f"Ranked items{context_line} by matching {persona.name}'s history, stated likes, "
        f"budget level, category affinity, and cold-start product quality signals."
    )


def fallback_yarn(source_text: str, mode: str, persona: UserPersona, task: str) -> tuple[str, str]:
    compressed = " ".join(source_text.split())
    if len(compressed) > 330:
        compressed = compressed[:327].rstrip() + "..."
    mode_lower = mode.lower()
    if "pidgin" in mode_lower:
        script = (
            f"See wetin the agent find for {persona.name}: {compressed} "
            "The main thing be say the recommendation follow the person taste, budget, and past choices."
        )
    elif "yoruba" in mode_lower:
        script = (
            f"For {persona.name}, this result is saying: {compressed} "
            "O da bi pe the system considered taste, price, and everyday usefulness."
        )
    elif "hausa" in mode_lower:
        script = (
            f"For {persona.name}, ga abin da system din ya nuna: {compressed} "
            "It keeps the shopper's taste, budget, and practical need in view."
        )
    elif "igbo" in mode_lower:
        script = (
            f"For {persona.name}, ihe the agent is saying is this: {compressed} "
            "It follows what the person likes, what they avoid, and what gives value."
        )
    else:
        script = (
            f"Here is the judge-friendly voice version for {persona.name}: {compressed} "
            "The key point is that the output is personalized from behavior, not generic."
        )
    note = f"{mode} voice layer for {task}: localized explanation without changing the model score."
    return script, note


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
                "You simulate concise product reviews from a user persona. Return strict JSON only. "
                "Schema: {\"review_text\": \"55-95 word first-person product review\"}. "
                "Write like a real reviewer, not an assistant. Avoid stereotypes. Use Nigerian context "
                "only when it naturally affects value, convenience, tone, or use."
            ),
        },
        {
            "role": "user",
            "content": (
                f"{summary.describe_for_prompt(product)}\n"
                f"Predicted rating: {rating}/5\n"
                f"Retrieved evidence:\n{evidence_text or 'No close evidence.'}\n"
                "Write one review of 55-95 words. Do not mention that you are an AI. "
                "Output JSON only."
            ),
        },
    ]
    generated = await client.chat(
        messages,
        temperature=0.45,
        response_format={"type": "json_object"},
    )
    parsed = _json_object(generated)
    if parsed:
        try:
            draft = ReviewDraft.model_validate(parsed)
            return _clean_review_text(draft.review_text), False
        except (ValidationError, ValueError):
            pass
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
            "content": (
                "Explain recommendation rankings for judges. Return strict JSON only. "
                "Schema: {\"summary\": \"45-80 word explanation\"}."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Persona: {PersonaSummary(persona).describe_for_prompt()}\n"
                f"Context: {context or 'None'}\n"
                f"Ranked items: {', '.join(ranked_titles)}\n"
                "Explain why this ranking is personalized in 45-80 words. Output JSON only."
            ),
        },
    ]
    generated = await client.chat(
        messages,
        temperature=0.25,
        response_format={"type": "json_object"},
    )
    parsed = _json_object(generated)
    if parsed:
        try:
            draft = RecommendationDraft.model_validate(parsed)
            return " ".join(draft.summary.split()), False
        except ValidationError:
            pass
    return fallback_recommendation_summary(persona, context), True


async def generate_yarn_text(
    settings: Settings,
    persona: UserPersona,
    source_text: str,
    mode: str,
    task: str,
) -> tuple[str, str, bool]:
    client = GroqClient(settings)
    messages = [
        {
            "role": "system",
            "content": (
                "You are a Nigerian localization layer for a demo called Yarn Mode. Return strict JSON only. "
                "Schema: {\"voice_script\":\"short spoken explanation\", \"judge_note\":\"why this helps evaluation\"}. "
                "Use the requested mode lightly and respectfully. Do not stereotype, invent facts, or change scores. "
                "If mode asks for a Nigerian language, use accessible language-flavoured English rather than deep translation."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Persona: {PersonaSummary(persona).describe_for_prompt()}\n"
                f"Mode: {mode}\nTask: {task}\nSource text: {source_text}\n"
                "Create a 45-90 word spoken script and a 20-45 word judge note. Output JSON only."
            ),
        },
    ]
    generated = await client.chat(
        messages,
        temperature=0.35,
        response_format={"type": "json_object"},
    )
    parsed = _json_object(generated)
    if parsed:
        try:
            draft = YarnDraft.model_validate(parsed)
            return " ".join(draft.voice_script.split()), " ".join(draft.judge_note.split()), False
        except ValidationError:
            pass
    script, note = fallback_yarn(source_text, mode, persona, task)
    return script, note, True
