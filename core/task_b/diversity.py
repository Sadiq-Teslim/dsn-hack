from __future__ import annotations

from core.schemas import CandidateItem


def diversify(items: list[CandidateItem], top_k: int) -> list[CandidateItem]:
    selected: list[CandidateItem] = []
    category_counts: dict[str, int] = {}
    for item in items:
        count = category_counts.get(item.category, 0)
        if count < 3 or len(selected) < max(3, top_k // 2):
            selected.append(item)
            category_counts[item.category] = count + 1
        if len(selected) >= top_k:
            break
    if len(selected) < top_k:
        used = {item.item_id for item in selected}
        for item in items:
            if item.item_id not in used:
                selected.append(item)
            if len(selected) >= top_k:
                break
    return selected[:top_k]
