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
                "Use only candidate titles provided. Score 0-1. Reasons must be natural and specific. "
                "Do not cite generic query words such as 'based', 'recommend', 'food', or 'item' as preferences."
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
    parsed, meta = await llm.json_chat(messages, temperature=0.20, attempts=4)
    if parsed and isinstance(parsed.get("ranked"), list):
        by_title = {_normalize_title(item.title): item for item in shortlist}
        reranked: list[CandidateItem] = []
        for row in parsed["ranked"]:
            title = _normalize_title(str(row.get("title", "")))
            candidate = by_title.get(title) or _nearest_title_match(title, shortlist)
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
            remaining = [
                item
                for item in candidates
                if _normalize_title(item.title) not in {_normalize_title(r.title) for r in reranked}
            ]
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


def _normalize_title(title: str) -> str:
    return " ".join(ch.lower() for ch in title if ch.isalnum() or ch.isspace()).strip()


def _nearest_title_match(title: str, candidates: list[CandidateItem]) -> CandidateItem | None:
    if not title:
        return None
    title_tokens = set(title.split())
    best: tuple[float, CandidateItem] | None = None
    for candidate in candidates:
        candidate_tokens = set(_normalize_title(candidate.title).split())
        overlap = len(title_tokens & candidate_tokens) / max(1, len(title_tokens | candidate_tokens))
        if overlap >= 0.72 and (best is None or overlap > best[0]):
            best = (overlap, candidate)
    return best[1] if best else None


def _fallback_reason(profile: UserProfile, intent: IntentSignal, candidate: CandidateItem) -> str:
    matches = ", ".join(candidate.matched_preferences) or "catalog quality"
    context = f" for '{intent.raw_context}'" if intent.raw_context else ""
    return (
        f"Reasoned fit{context}: {candidate.title} matches {profile.persona.name}'s "
        f"budget level, category signals, and {matches}."
    )
