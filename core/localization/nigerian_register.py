from __future__ import annotations

import json
from pathlib import Path

from app.services.text_utils import keyword_set
from core.schemas import NigerianExemplar, NigerianRegister, UserProfile

ROOT = Path(__file__).resolve().parents[2]
EXEMPLARS_PATH = ROOT / "data" / "nigerian_context" / "review_examples.json"


def load_nigerian_exemplars() -> list[NigerianExemplar]:
    if not EXEMPLARS_PATH.exists():
        return []
    raw = json.loads(EXEMPLARS_PATH.read_text(encoding="utf-8"))
    return [NigerianExemplar(**item) for item in raw]


def retrieve_nigerian_exemplars(
    profile: UserProfile,
    target_text: str,
    register: NigerianRegister | None = None,
    limit: int = 4,
) -> list[NigerianExemplar]:
    exemplars = load_nigerian_exemplars()
    selected_register = register or profile.nigerian_register
    target_tokens = keyword_set(target_text, profile.persona.tone, profile.persona.cultural_context)
    scored: list[tuple[float, NigerianExemplar]] = []
    for exemplar in exemplars:
        exemplar_tokens = keyword_set(exemplar.text, exemplar.tone, exemplar.tags)
        overlap = len(target_tokens & exemplar_tokens) / max(1, len(target_tokens | exemplar_tokens))
        register_bonus = 0.45 if exemplar.nigerian_register == selected_register else 0.0
        standard_bonus = 0.18 if exemplar.nigerian_register == NigerianRegister.STANDARD else 0.0
        score = overlap + register_bonus + standard_bonus
        scored.append((score, exemplar))
    return [item for _, item in sorted(scored, key=lambda pair: pair[0], reverse=True)[:limit]]
