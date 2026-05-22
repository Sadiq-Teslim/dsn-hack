from __future__ import annotations

from uuid import uuid4

from app.schemas import UserPersona

_SESSIONS: dict[str, dict] = {}


def get_or_create_session(session_id: str | None, persona: UserPersona, context: str) -> tuple[str, dict]:
    sid = session_id or str(uuid4())
    state = _SESSIONS.setdefault(
        sid,
        {
            "persona_name": persona.name,
            "turns": [],
            "constraints": [],
            "last_item_ids": [],
            "last_titles": [],
            "last_categories": [],
        },
    )
    if context:
        state["turns"].append(context)
    return sid, state


def session_context(state: dict) -> str:
    return " ".join(state.get("turns", [])[-4:])


def remember_recommendations(state: dict, items: list) -> None:
    state["last_item_ids"] = [getattr(item, "item_id", "") for item in items if getattr(item, "item_id", "")]
    state["last_titles"] = [getattr(item, "title", "") for item in items if getattr(item, "title", "")]
    state["last_categories"] = [getattr(item, "category", "") for item in items if getattr(item, "category", "")]
