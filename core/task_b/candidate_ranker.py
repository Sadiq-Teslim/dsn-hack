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
    category_name = candidate.category.replace("_", " ")
    matches = _readable_matches(candidate.matched_preferences)
    target_note = ""
    if intent.target_categories:
        target_note = (
            f"It stays inside the requested {category_name} lane, "
            if candidate.category in set(intent.target_categories)
            else f"It is an adjacent {category_name} option, "
        )
    budget_note = _budget_note(profile, candidate)
    context_note = _context_note(intent, candidate)
    quality_note = _quality_note(candidate)
    return f"{target_note}{context_note}{budget_note}{quality_note}{matches}"


def _readable_matches(matches: list[str]) -> str:
    clean = [match.replace("_", " ") for match in matches if match not in {"catalog", "quality"}]
    if not clean:
        return "The match is driven more by catalog quality than exact keyword overlap."
    if len(clean) == 1:
        return f"It also matches the preference signal '{clean[0]}'."
    return f"It also matches preference signals like {', '.join(clean[:3])}."


def _budget_note(profile: UserProfile, candidate: CandidateItem) -> str:
    price = candidate.price
    if price is None:
        return ""
    budget = profile.persona.budget_level.lower()
    if budget == "low":
        if price <= 15:
            return f"the price is friendly for {profile.persona.name}'s low-budget profile, "
        if price <= 30:
            return f"the price is still manageable for a careful low-budget buyer, "
        return f"the price is the main caution for a low-budget buyer, "
    if budget == "medium" and price <= 40:
        return "the price is reasonable for a medium-budget routine, "
    return "the price is acceptable for the persona's budget level, "


def _context_note(intent: IntentSignal, candidate: CandidateItem) -> str:
    text = " ".join(
        [
            candidate.title,
            candidate.category,
            str(candidate.metadata.get("description", "")),
            str(candidate.metadata.get("attributes", {})),
        ]
    ).lower()
    constraints = set(intent.constraints)
    if {"week", "routine", "school", "work", "quick", "daily"} & constraints:
        if any(word in text for word in ["quick", "morning", "daily", "work", "breakfast", "sunscreen"]):
            return "It fits the weekly-routine request because it is practical for repeated use; "
        return "It is less of a daily utility item, but still has enough persona fit to consider; "
    if "family" in constraints or "weekend" in constraints:
        if any(word in text for word in ["family", "party", "weekend", "children", "friends", "share"]):
            return "It fits the weekend or family-use context directly; "
        return "It is a secondary fit for the weekend context; "
    if "buy" in constraints and "Books" == candidate.category:
        return "It directly answers the book-buying request; "
    return "It is ranked because the item evidence lines up with the current request; "


def _quality_note(candidate: CandidateItem) -> str:
    rating = candidate.metadata.get("average_rating")
    try:
        rating_text = f"with a {float(rating):.1f}/5 catalog signal, "
    except (TypeError, ValueError):
        rating_text = ""
    return rating_text
