from __future__ import annotations

import re

from app.config import Settings
from app.schemas import RecommendedItem, UserPersona
from core.orchestration import CoreLLMClient, Pipeline, Step, new_trace
from core.retrieval import shortlist_items
from core.schemas import AgentDecisionStatus, AgentRuntimeContext, CandidateItem, TaskBAgentResult
from core.task_b.candidate_ranker import llm_rerank_candidates
from core.task_b.cross_domain_bridge import bridge_cross_domain
from core.task_b.diversity import diversify
from core.task_b.intent_parser import parse_intent
from core.task_b.session_memory import get_or_create_session, remember_recommendations, session_context
from core.user_model import build_user_profile


async def run_task_b_pipeline(
    settings: Settings,
    persona: UserPersona,
    products: list[dict],
    context_text: str,
    include_categories: list[str],
    top_k: int,
    session_id: str | None = None,
    conversational: bool = False,
) -> TaskBAgentResult:
    trace = new_trace("task_b_recommendation")
    sid, session_state = get_or_create_session(session_id, persona, "")
    merged_context = f"{session_context(session_state)} {context_text}".strip()
    if context_text:
        session_state["turns"].append(context_text)
    context = AgentRuntimeContext(
        request_id=trace.request_id,
        session_id=sid,
        persona=persona,
        context=merged_context,
        catalog=products,
        trace=trace,
        working={
            "include_categories": include_categories,
            "top_k": top_k,
            "conversational": conversational,
            "session_state": session_state,
            "current_context": context_text,
        },
    )
    pipeline = Pipeline(
        "task_b_recommendation",
        [
            ResolveUserProfileStep(),
            ParseIntentStep(),
            CrossDomainBridgeStep(settings),
            ColdStartGateStep(),
            CandidateShortlistStep(),
            LLMRerankStep(settings),
            DiversityStep(),
            BuildRecommendationResponseStep(settings),
        ],
    )
    context = await pipeline.run(context)
    if context.working.get("status") == AgentDecisionStatus.NEEDS_CLARIFICATION:
        return TaskBAgentResult(
            items=[],
            reasoning="The agent needs a little more context before recommending.",
            reasoning_trace=context.trace,
            llm_provider=settings.llm_provider,
            fallback_used=False,
            session_id=sid,
            status=AgentDecisionStatus.NEEDS_CLARIFICATION,
            follow_up_questions=context.working.get("follow_up_questions", []),
        )
    return TaskBAgentResult(
        items=context.working["items"],
        reasoning=context.working["reasoning"],
        reasoning_trace=context.trace,
        llm_provider=settings.llm_provider,
        fallback_used=bool(context.working.get("fallback_used")),
        session_id=sid,
        status=AgentDecisionStatus.COMPLETE,
        follow_up_questions=[],
    )


class ResolveUserProfileStep(Step):
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        profile = build_user_profile(context.persona)
        context.user_profile = profile
        context.working["_last_step_outputs"] = {
            "_summary": "Built structured user profile for recommendation.",
            "cold_start": profile.cold_start,
            "rating_mean": profile.rating_mean,
            "category_affinity": profile.category_affinity,
            "taste_tokens": profile.taste_tokens[:8],
        }
        return context


class ParseIntentStep(Step):
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        intent = parse_intent(
            context.context,
            context.user_profile,
            context.working.get("include_categories", []),
        )
        context.working["intent"] = intent
        context.working["_last_step_outputs"] = {
            "_summary": "Parsed recommendation intent, constraints, and scenario type.",
            "target_categories": intent.target_categories,
            "excluded_categories": intent.excluded_categories,
            "constraints": intent.constraints,
            "min_price": intent.min_price,
            "max_price": intent.max_price,
            "max_price_exclusive": intent.max_price_exclusive,
            "price_is_approximate": intent.price_is_approximate,
            "is_cold_start": intent.is_cold_start,
            "is_cross_domain": intent.is_cross_domain,
            "needs_clarification": intent.needs_clarification,
        }
        return context


class CrossDomainBridgeStep(Step):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        intent, fallback_used, meta = await bridge_cross_domain(
            self.settings,
            context.user_profile,
            context.working["intent"],
        )
        context.working["intent"] = intent
        context.working["_last_step_outputs"] = {
            "_summary": "Expanded abstract taste descriptors for cross-domain recommendation.",
            "taste_descriptors": intent.taste_descriptors[:12],
            "is_cross_domain": intent.is_cross_domain,
            "bridge_fallback_used": fallback_used,
            "llm_configured": meta.get("configured", False),
        }
        return context


class ColdStartGateStep(Step):
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        intent = context.working["intent"]
        if context.working.get("conversational") and intent.needs_clarification:
            context.working["status"] = AgentDecisionStatus.NEEDS_CLARIFICATION
            context.working["follow_up_questions"] = intent.clarification_questions
            context.working["_last_step_outputs"] = {
                "_summary": "Cold-start chat needs bootstrap answers before recommendation.",
                "follow_up_questions": intent.clarification_questions,
            }
            return context
        context.working["_last_step_outputs"] = {
            "_summary": "Cold-start gate passed; enough context exists to recommend.",
            "cold_start": intent.is_cold_start,
        }
        return context


class CandidateShortlistStep(Step):
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        if context.working.get("status") == AgentDecisionStatus.NEEDS_CLARIFICATION:
            context.working["_last_step_outputs"] = {"_summary": "Skipped shortlist pending clarification."}
            return context
        intent = context.working["intent"]
        available_categories = {str(product.get("category", "")) for product in context.catalog}
        unsupported = [
            category
            for category in intent.target_categories
            if category not in available_categories
        ]
        excluded = [
            category
            for category in intent.excluded_categories
            if category in available_categories
        ]
        if unsupported:
            intent.unsupported_targets = unsupported
            context.working["intent"] = intent
        scoped_catalog = _conversation_scoped_catalog(context)
        candidates = shortlist_items(
            context.user_profile,
            scoped_catalog,
            intent,
            limit=50,
        )
        context.working["candidates"] = candidates
        context.working["_last_step_outputs"] = {
            "_summary": "Local retriever filtered catalog to a candidate shortlist before LLM re-ranking.",
            "candidate_count": len(candidates),
            "top_candidates": [item.title for item in candidates[:5]],
            "unsupported_targets": unsupported,
            "excluded_categories": excluded,
            "follow_up_scope": bool(context.working.get("follow_up_scope")),
            "previous_item_count": len(context.working.get("previous_item_ids", [])),
            "min_price": intent.min_price,
            "max_price": intent.max_price,
            "max_price_exclusive": intent.max_price_exclusive,
            "price_is_approximate": intent.price_is_approximate,
        }
        return context


class LLMRerankStep(Step):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        if context.working.get("status") == AgentDecisionStatus.NEEDS_CLARIFICATION:
            context.working["_last_step_outputs"] = {"_summary": "Skipped LLM re-ranking pending clarification."}
            return context
        reranked, fallback_used, meta = await llm_rerank_candidates(
            self.settings,
            context.user_profile,
            context.working["intent"],
            context.working["candidates"],
            limit=20,
        )
        context.working["reranked"] = reranked
        context.working["fallback_used"] = fallback_used
        context.working["_last_step_outputs"] = {
            "_summary": "LLM-assisted re-ranker reasoned over the shortlisted candidates before final diversity filtering.",
            "fallback_used": fallback_used,
            "llm_configured": meta.get("configured", False),
            "top_reranked": [item.title for item in reranked[:5]],
        }
        return context


class DiversityStep(Step):
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        if context.working.get("status") == AgentDecisionStatus.NEEDS_CLARIFICATION:
            context.working["_last_step_outputs"] = {"_summary": "Skipped diversity pending clarification."}
            return context
        selected = diversify(context.working["reranked"], context.working["top_k"])
        context.working["selected"] = selected
        context.working["_last_step_outputs"] = {
            "_summary": "Applied category diversity to avoid a one-note recommendation list.",
            "selected_categories": [item.category for item in selected],
        }
        return context


class BuildRecommendationResponseStep(Step):
    def __init__(self, settings: Settings):
        super().__init__()
        self.settings = settings

    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        if context.working.get("status") == AgentDecisionStatus.NEEDS_CLARIFICATION:
            context.working["_last_step_outputs"] = {"_summary": "Skipped response build pending clarification."}
            return context
        selected: list[CandidateItem] = context.working["selected"]
        items = [
            RecommendedItem(
                rank=index + 1,
                item_id=item.item_id,
                title=item.title,
                category=item.category,
                score=item.score,
                reason=item.reason,
                matched_preferences=item.matched_preferences,
                price=item.price,
            )
            for index, item in enumerate(selected)
        ]
        items, reasoning, presentation_fallback, presentation_meta = await _formalize_visible_response(
            self.settings,
            context.user_profile.persona.name,
            context.working["intent"],
            items,
        )
        context.working["items"] = items
        context.working["reasoning"] = reasoning
        context.working["fallback_used"] = bool(context.working.get("fallback_used")) or presentation_fallback
        remember_recommendations(context.working["session_state"], items)
        context.working["_last_step_outputs"] = {
            "_summary": "Built final visible recommendation response.",
            "item_count": len(items),
            "session_id": context.session_id,
            "presentation_fallback_used": presentation_fallback,
            "presentation_llm_configured": presentation_meta.get("configured", False),
        }
        return context


async def _formalize_visible_response(
    settings: Settings,
    name: str,
    intent,
    items: list[RecommendedItem],
) -> tuple[list[RecommendedItem], str, bool, dict]:
    fallback_summary = _summary(name, intent, items)
    llm = CoreLLMClient(settings)
    item_lines = "\n".join(
        f"{item.rank}. {item.title} | {item.category.replace('_', ' ')} | price={item.price} | reason={item.reason}"
        for item in items
    ) or "No available options matched all stated requirements."
    excluded_text = ", ".join(category.replace("_", " ") for category in intent.excluded_categories) or "None"
    parsed, meta = await llm.json_chat(
        [
            {
                "role": "system",
                "content": (
                    "You write polished recommendation copy for an end user. Return strict JSON only. "
                    "Schema: {\"summary\":\"formal summary\", \"items\":[{\"title\":\"exact title\", "
                    "\"reason\":\"formal user-facing reason\"}]}. Use only the supplied item titles. "
                    "If no options are supplied, return an empty items array and explain the unmet requirement clearly. "
                    "Do not invent preference matches. Only mention a preference when it is supported by the supplied item reason, "
                    "item category, item title, or price. "
                    "Use a formal, concise, helpful tone. Do not mention technical terms such as LLM, AI, "
                    "model, reranker, retrieval, candidate, score, signal, metadata, catalog, pipeline, "
                    "trace, algorithm, system, shortlist, or context match. Do not discuss internal methods. Do not over-explain."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"User name: {name}\n"
                    f"User request: {intent.raw_context}\n"
                    f"Target categories: {', '.join(category.replace('_', ' ') for category in intent.target_categories) or 'Any'}\n"
                    f"Excluded categories: {excluded_text}\n"
                    f"Draft summary: {fallback_summary}\n"
                    f"Items:\n{item_lines}\n"
                    "Rewrite the summary and each item reason for display to the user."
                ),
            },
        ],
        temperature=0.18,
        attempts=3,
    )
    if not parsed:
        return items, fallback_summary, True, meta

    summary = str(parsed.get("summary", "")).strip()
    rewritten = parsed.get("items")
    if not summary or not isinstance(rewritten, list):
        return items, fallback_summary, True, meta

    if not items:
        return items, _clean_visible_text(summary), bool(meta.get("fallback_used")), meta

    by_title = {item.title: item for item in items}
    for row in rewritten:
        if not isinstance(row, dict):
            continue
        title = str(row.get("title", ""))
        reason = str(row.get("reason", "")).strip()
        if title in by_title and len(reason) > 20:
            by_title[title].reason = _clean_visible_text(reason)
    return items, _clean_visible_text(summary), bool(meta.get("fallback_used")), meta


def _summary(name: str, intent, items: list[RecommendedItem]) -> str:
    if not items:
        price_note = _price_note(intent)
        if intent.unsupported_targets:
            available = "Grocery, Movies and TV, Video Games, Beauty, and Books"
            targets = ", ".join(category.replace("_", " ") for category in intent.unsupported_targets)
            return (
                f"I could not prepare {targets} recommendations because that category is not available in this demo collection. "
                f"Available demo categories are {available}."
            )
        if intent.target_categories and (intent.max_price is not None or intent.min_price is not None):
            targets = ", ".join(category.replace("_", " ") for category in intent.target_categories)
            return f"I could not find {targets} options {price_note}. Please raise the price limit or choose another available category."
        return "I could not find a suitable match for the current request. Please try a broader request or choose another available category."
    top = items[0]
    scenario = []
    if intent.is_cold_start:
        scenario.append("new preference profile")
    if intent.is_cross_domain:
        scenario.append("cross-category")
    if intent.unsupported_targets:
        scenario.append("partial category match")
    scenario_text = f" ({', '.join(scenario)})" if scenario else ""
    category_text = ""
    if intent.target_categories:
        category_text = " in " + ", ".join(category.replace("_", " ") for category in intent.target_categories)
    price_text = f" {_price_note(intent)}" if (intent.max_price is not None or intent.min_price is not None) else ""
    exclusion_text = ""
    if intent.excluded_categories:
        exclusion_text = ", excluding " + ", ".join(category.replace("_", " ") for category in intent.excluded_categories)
    return (
        f"I found {len(items)} suitable options for {name}{category_text}{price_text}{exclusion_text}{scenario_text}. "
        f"The leading recommendation is {top.title}, because {top.reason}"
    )


def _price_note(intent) -> str:
    if intent.min_price is None and intent.max_price is None:
        return ""
    if intent.min_price is not None and intent.max_price is not None:
        prefix = "around " if intent.price_is_approximate else "between "
        joiner = " and " if not intent.price_is_approximate else ""
        if intent.price_is_approximate:
            return f"{prefix}${intent.min_price:g}-${intent.max_price:g}"
        return f"{prefix}${intent.min_price:g}{joiner}${intent.max_price:g}"
    if intent.min_price is not None:
        return f"at or above ${intent.min_price:g}"
    comparator = "below" if intent.max_price_exclusive else "at or below"
    return f"{comparator} ${intent.max_price:g}"


def _clean_visible_text(text: str) -> str:
    replacements = {
        "LLM": "assistant",
        "AI model": "assistant",
        "AI": "assistant",
        "model": "assistant",
        "reranker": "recommendation process",
        "re-ranker": "recommendation process",
        "retrieval": "selection",
        "candidate": "option",
        "metadata": "details",
        "catalog": "collection",
        "pipeline": "process",
        "trace": "notes",
        "algorithm": "method",
        "score": "fit",
        "signal": "preference",
        "shortlist": "selection",
        "context match": "request fit",
    }
    cleaned = " ".join(text.split())
    for word, replacement in replacements.items():
        cleaned = re.sub(rf"\b{re.escape(word)}\b", replacement, cleaned, flags=re.IGNORECASE)
    return cleaned


def _conversation_scoped_catalog(context: AgentRuntimeContext) -> list[dict]:
    current = str(context.working.get("current_context", ""))
    state = context.working.get("session_state", {})
    previous_item_ids = [item_id for item_id in state.get("last_item_ids", []) if item_id]
    if not previous_item_ids or not _looks_like_follow_up(current):
        return context.catalog
    previous_ids = set(previous_item_ids)
    scoped = [item for item in context.catalog if str(item.get("item_id", item.get("title", ""))) in previous_ids]
    if not scoped:
        return context.catalog
    context.working["follow_up_scope"] = True
    context.working["previous_item_ids"] = previous_item_ids
    return scoped


def _looks_like_follow_up(text: str) -> bool:
    lowered = text.lower()
    return bool(
        re.search(r"\b(which|what|any|one|ones|them|those|these|among|of them|from them|the list|previous|first)\b", lowered)
        or re.search(r"\b(which of them|which ones|any of them|from the list)\b", lowered)
    )
