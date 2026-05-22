from __future__ import annotations

from app.config import Settings
from app.services.text_utils import clamp, stable_round
from core.orchestration import CoreLLMClient
from core.schemas import CandidateItem, IntentSignal, UserProfile


async def llm_rerank_candidates(
    settings: Settings,
    profile: UserProfile,
    intent: IntentSignal,
    candidates: list[CandidateItem],
    limit: int = 20,
) -> tuple[list[CandidateItem], bool, dict]:
    shortlist = candidates[:limit]
    llm = CoreLLMClient(settings)
    candidate_lines = "\n".join(
        f"{idx+1}. {item.title} | {item.category} | local={item.local_score:.3f} | "
        f"matches={', '.join(item.matched_preferences) or 'none'} | {item.reason}"
        for idx, item in enumerate(shortlist)
    )
    messages = [
        {
            "role": "system",
            "content": (
                "You are a recommender re-ranker. Reason before recommending. Return strict JSON only. "
                "Schema: {\"ranked\":[{\"title\":\"candidate title\", \"llm_score\":0.0, "
                "\"reason\":\"specific reason grounded in persona and context\"}]}. "
                "Use only candidate titles provided. Score 0-1."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Persona: {profile.persona.name}, {profile.persona.location}, "
                f"budget {profile.persona.budget_level}, likes {profile.persona.likes}, "
                f"dislikes {profile.persona.dislikes}, taste tokens {profile.taste_tokens[:12]}.\n"
                f"Context: {intent.raw_context or 'No explicit context'}\n"
                f"Intent descriptors: {intent.taste_descriptors}\n"
                f"Candidates:\n{candidate_lines}\n"
                "Re-rank these candidates with reasoning. Output JSON only."
            ),
        },
    ]
    parsed, meta = await llm.json_chat(messages, temperature=0.20)
    if parsed and isinstance(parsed.get("ranked"), list):
        by_title = {item.title.lower(): item for item in shortlist}
        reranked: list[CandidateItem] = []
        for row in parsed["ranked"]:
            title = str(row.get("title", "")).lower()
            candidate = by_title.get(title)
            if not candidate:
                continue
            llm_score = _safe_score(row.get("llm_score"), candidate.local_score)
            candidate.llm_score = llm_score
            candidate.score = stable_round(clamp(0.45 * candidate.local_score + 0.55 * llm_score, 0, 1))
            reason = str(row.get("reason", "")).strip()
            if len(reason) > 20:
                candidate.reason = reason
            reranked.append(candidate)
        if reranked:
            remaining = [item for item in candidates if item.title.lower() not in {r.title.lower() for r in reranked}]
            return _sort_for_intent(reranked, intent) + remaining, bool(meta.get("fallback_used")), meta

    fallback = []
    for candidate in candidates:
        candidate.llm_score = candidate.local_score
        candidate.score = candidate.local_score
        candidate.reason = _fallback_reason(profile, intent, candidate)
        fallback.append(candidate)
    return _sort_for_intent(fallback, intent), True, meta


def _sort_for_intent(candidates: list[CandidateItem], intent: IntentSignal) -> list[CandidateItem]:
    target_categories = set(intent.target_categories)
    if target_categories:
        return sorted(
            candidates,
            key=lambda item: (item.category in target_categories, item.score),
            reverse=True,
        )
    return sorted(candidates, key=lambda item: item.score, reverse=True)


def _safe_score(value: object, fallback: float) -> float:
    try:
        return stable_round(clamp(float(value), 0, 1))
    except (TypeError, ValueError):
        return fallback


def _fallback_reason(profile: UserProfile, intent: IntentSignal, candidate: CandidateItem) -> str:
    matches = ", ".join(candidate.matched_preferences) or "catalog quality"
    context = f" for '{intent.raw_context}'" if intent.raw_context else ""
    return (
        f"Reasoned fit{context}: {candidate.title} matches {profile.persona.name}'s "
        f"budget level, category signals, and {matches}."
    )
