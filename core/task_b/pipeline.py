from __future__ import annotations

from app.config import Settings
from app.schemas import RecommendedItem, UserPersona
from core.orchestration import Pipeline, Step, new_trace
from core.retrieval import shortlist_items
from core.schemas import AgentDecisionStatus, AgentRuntimeContext, CandidateItem, TaskBAgentResult
from core.task_b.candidate_ranker import llm_rerank_candidates
from core.task_b.cross_domain_bridge import bridge_cross_domain
from core.task_b.diversity import diversify
from core.task_b.intent_parser import parse_intent
from core.task_b.session_memory import get_or_create_session, session_context
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
            "constraints": intent.constraints,
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
        if unsupported:
            intent.unsupported_targets = unsupported
            context.working["intent"] = intent
        candidates = shortlist_items(
            context.user_profile,
            context.catalog,
            intent,
            limit=50,
        )
        context.working["candidates"] = candidates
        context.working["_last_step_outputs"] = {
            "_summary": "Local retriever filtered catalog to a candidate shortlist before LLM re-ranking.",
            "candidate_count": len(candidates),
            "top_candidates": [item.title for item in candidates[:5]],
            "unsupported_targets": unsupported,
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
        context.working["items"] = items
        context.working["reasoning"] = _summary(context.user_profile.persona.name, context.working["intent"], items)
        context.working["_last_step_outputs"] = {
            "_summary": "Built final ranked recommendation response with per-item reasoning.",
            "item_count": len(items),
            "session_id": context.session_id,
        }
        return context


def _summary(name: str, intent, items: list[RecommendedItem]) -> str:
    if not items:
        if intent.unsupported_targets:
            available = "Grocery, Movies and TV, Video Games, Beauty, and Books"
            targets = ", ".join(category.replace("_", " ") for category in intent.unsupported_targets)
            return (
                f"I could not rank {targets} because that category is not loaded in this demo catalog. "
                f"Available demo categories are {available}."
            )
        return "No items matched the current constraints. Try a broader request or another available category."
    top = items[0]
    scenario = []
    if intent.is_cold_start:
        scenario.append("cold-start")
    if intent.is_cross_domain:
        scenario.append("cross-domain")
    if intent.unsupported_targets:
        scenario.append("partial catalog match")
    scenario_text = f" ({', '.join(scenario)})" if scenario else ""
    category_text = ""
    if intent.target_categories:
        category_text = " inside " + ", ".join(category.replace("_", " ") for category in intent.target_categories)
    return (
        f"Ranked {len(items)} items for {name}{category_text}{scenario_text} by combining persona memory, "
        f"context signals, local candidate retrieval, LLM-assisted re-ranking, and diversity. "
        f"Top pick: {top.title}, because {top.reason}"
    )
