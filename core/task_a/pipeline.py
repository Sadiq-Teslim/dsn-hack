from __future__ import annotations

import re

from app.config import Settings
from app.schemas import EvidenceItem, ProductDetails, UserPersona
from app.services.scoring import predict_rating
from app.services.text_utils import clamp, keyword_set, stable_round
from core.orchestration import CoreLLMClient, Pipeline, Step, new_trace
from core.retrieval import retrieve_review_examples
from core.schemas import AgentRuntimeContext, TaskAAgentResult
from core.task_a.consistency_checker import check_review_consistency
from core.task_a.rating_calibration import calibrate_rating
from core.task_a.review_generator import generate_grounded_review
from core.user_model import build_user_profile


async def run_task_a_pipeline(
    settings: Settings,
    persona: UserPersona,
    product: ProductDetails,
    catalog: list[dict],
    reviews: list[dict],
) -> TaskAAgentResult:
    trace = new_trace("task_a_review_simulation")
    context = AgentRuntimeContext(
        request_id=trace.request_id,
        persona=persona,
        product=product.model_dump(),
        catalog=catalog,
        reviews=reviews,
        trace=trace,
    )
    pipeline = Pipeline(
        "task_a_review_simulation",
        [
            ResolveUserProfileStep(),
            RetrieveEvidenceStep(),
            PredictSentimentStep(),
            CalibrateRatingStep(),
            GenerateReviewStep(settings),
            ConsistencyCheckStep(),
            FormalizeReviewReasoningStep(settings),
        ],
    )
    context = await pipeline.run(context)
    evidence = [EvidenceItem.model_validate(item) for item in context.working["evidence"]]
    calibration = context.working["calibration"]
    return TaskAAgentResult(
        rating=calibration.calibrated_rating,
        review_text=context.working["review_text"],
        confidence=context.working["confidence"],
        reasoning=context.working["reasoning"],
        evidence=evidence,
        calibration=calibration,
        reasoning_trace=context.trace,
        llm_provider=settings.llm_provider,
        fallback_used=bool(context.working.get("fallback_used")),
        consistency_check=context.working["consistency_check"],
    )


class ResolveUserProfileStep(Step):
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        profile = build_user_profile(context.persona)
        context.user_profile = profile
        context.working["_last_step_outputs"] = {
            "_summary": "Built structured user profile with rating distribution and taste fingerprint.",
            "rating_mean": profile.rating_mean,
            "rating_std": profile.rating_std,
            "cold_start": profile.cold_start,
            "top_taste_tokens": profile.taste_tokens[:8],
            "nigerian_register": profile.nigerian_register.value,
        }
        return context


class RetrieveEvidenceStep(Step):
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        product = ProductDetails.model_validate(context.product)
        evidence = retrieve_review_examples(
            context.persona,
            context.user_profile,
            product,
            context.reviews,
            limit=5,
        )
        context.working["evidence"] = [item.model_dump() for item in evidence]
        context.working["_last_step_outputs"] = {
            "_summary": "Retrieved own-history and similar-review exemplars for grounded generation.",
            "evidence_count": len(evidence),
            "top_evidence": [item.title for item in evidence[:3]],
        }
        return context


class PredictSentimentStep(Step):
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        product = ProductDetails.model_validate(context.product)
        profile = context.user_profile
        catalog_item = _catalog_item(context.catalog, product)
        target_tokens = keyword_set(product.title, product.category, product.description, product.attributes)
        preference_overlap = len(target_tokens & set(profile.taste_tokens)) / max(1, len(target_tokens))
        dislike_overlap = len(target_tokens & keyword_set(profile.persona.dislikes)) / max(1, len(target_tokens))
        catalog_rating = float((catalog_item or {}).get("average_rating", 3.8))
        category_affinity = profile.category_affinity.get(product.category, profile.rating_mean)
        budget = _budget_adjustment(profile.persona.budget_level, product.price or (catalog_item or {}).get("price"))
        base_rating, _, legacy_reasoning = predict_rating(context.persona, product, catalog_item)
        sentiment = (base_rating - 1) / 4
        sentiment = stable_round(clamp(sentiment, 0.05, 0.98))
        context.working["sentiment"] = sentiment
        context.working["catalog_rating"] = catalog_rating
        context.working["base_rating"] = base_rating
        context.working["confidence"] = stable_round(
            clamp(0.50 + 0.05 * profile.history_count + preference_overlap * 0.25, 0.45, 0.94)
        )
        context.working["_last_step_outputs"] = {
            "_summary": "Predicted raw sentiment before converting it to a user-calibrated star rating.",
            "sentiment": sentiment,
            "base_rating": base_rating,
            "catalog_rating": catalog_rating,
            "preference_overlap": stable_round(preference_overlap),
            "dislike_overlap": stable_round(dislike_overlap),
            "base_reasoning": legacy_reasoning,
        }
        return context


class CalibrateRatingStep(Step):
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        calibration = calibrate_rating(
            context.user_profile,
            context.working["sentiment"],
            context.working["catalog_rating"],
            context.working["base_rating"],
        )
        context.working["calibration"] = calibration
        context.working["reasoning"] = calibration.explanation
        context.working["_last_step_outputs"] = {
            "_summary": "Mapped sentiment to stars using the user's personal rating distribution.",
            "raw_rating": calibration.raw_rating,
            "calibrated_rating": calibration.calibrated_rating,
            "calibration_logic": calibration.explanation,
        }
        return context


class GenerateReviewStep(Step):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        product = ProductDetails.model_validate(context.product)
        evidence = [EvidenceItem.model_validate(item) for item in context.working["evidence"]]
        review_text, fallback_used, meta = await generate_grounded_review(
            self.settings,
            context.user_profile,
            product,
            context.working["calibration"].calibrated_rating,
            evidence,
        )
        context.working["review_text"] = review_text
        context.working["fallback_used"] = fallback_used
        context.working["_last_step_outputs"] = {
            "_summary": "Generated review from calibrated score, retrieved examples, and Nigerian register exemplars.",
            "fallback_used": fallback_used,
            "llm_configured": meta.get("configured", False),
            "review_preview": review_text[:140],
        }
        return context


class ConsistencyCheckStep(Step):
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        check = check_review_consistency(
            context.working["review_text"],
            context.working["calibration"].calibrated_rating,
        )
        context.working["consistency_check"] = check
        context.working["_last_step_outputs"] = {
            "_summary": "Checked whether review sentiment and calibrated rating are aligned.",
            "consistency_check": check,
        }
        return context


class FormalizeReviewReasoningStep(Step):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        product = ProductDetails.model_validate(context.product)
        fallback = _formal_review_note(
            context.persona.name,
            product.title,
            context.working["calibration"].calibrated_rating,
            context.working["review_text"],
            context.working["consistency_check"],
        )
        llm = CoreLLMClient(self.settings)
        parsed, meta = await llm.json_chat(
            [
                {
                    "role": "system",
                    "content": (
                        "Write a formal, concise user-facing explanation for a generated review result. "
                        "Return strict JSON only: {\"reasoning\":\"formal explanation\"}. "
                        "Do not mention technical terms such as LLM, AI, model, calibration, sentiment, "
                        "retrieval, metadata, catalog, pipeline, trace, algorithm, score, or signal. "
                        "Do not discuss internal methods."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        f"Persona: {context.persona.name}, {context.persona.location}, "
                        f"budget {context.persona.budget_level}, tone {context.persona.tone}, "
                        f"likes {context.persona.likes}, dislikes {context.persona.dislikes}.\n"
                        f"Product: {product.title}, {product.category}, {product.description}\n"
                        f"Rating: {context.working['calibration'].calibrated_rating}/5\n"
                        f"Generated review: {context.working['review_text']}\n"
                        f"Consistency note: {context.working['consistency_check']}\n"
                        f"Draft explanation: {fallback}"
                    ),
                },
            ],
            temperature=0.18,
            attempts=3,
        )
        reasoning = fallback
        if parsed:
            candidate = str(parsed.get("reasoning", "")).strip()
            if len(candidate) > 20:
                reasoning = _clean_review_visible_text(candidate)
        context.working["reasoning"] = reasoning
        context.working["fallback_used"] = bool(context.working.get("fallback_used")) or bool(meta.get("fallback_used"))
        context.working["_last_step_outputs"] = {
            "_summary": "Prepared formal visible explanation for the review result.",
            "presentation_fallback_used": bool(meta.get("fallback_used")),
            "presentation_llm_configured": meta.get("configured", False),
        }
        return context


def _formal_review_note(name: str, product_title: str, rating: float, review_text: str, consistency_check: str) -> str:
    return (
        f"The generated review presents how {name} is likely to respond to {product_title}. "
        f"The {rating:.1f}/5 rating is supported by the review's tone and the stated product fit."
    )


def _clean_review_visible_text(text: str) -> str:
    replacements = {
        "LLM": "assistant",
        "AI model": "assistant",
        "model": "assistant",
        "calibration": "rating adjustment",
        "sentiment": "tone",
        "retrieval": "reference selection",
        "metadata": "details",
        "catalog": "collection",
        "pipeline": "process",
        "trace": "notes",
        "algorithm": "method",
        "score": "fit",
        "signal": "preference",
    }
    cleaned = " ".join(text.split())
    for word, replacement in replacements.items():
        cleaned = re.sub(rf"\b{re.escape(word)}\b", replacement, cleaned, flags=re.IGNORECASE)
    return cleaned


def _catalog_item(catalog: list[dict], product: ProductDetails) -> dict | None:
    exact = next(
        (item for item in catalog if item.get("title", "").lower() == product.title.lower()),
        None,
    )
    if exact:
        return exact
    return next((item for item in catalog if item.get("category") == product.category), None)


def _budget_adjustment(budget_level: str, price: object) -> float:
    if price is None:
        return 0.0
    try:
        price_float = float(price)
    except (TypeError, ValueError):
        return 0.0
    budget = budget_level.lower()
    if budget == "low" and price_float > 30:
        return -0.08
    if budget == "medium" and price_float > 80:
        return -0.04
    if budget == "high" and price_float > 40:
        return 0.03
    return 0.0
