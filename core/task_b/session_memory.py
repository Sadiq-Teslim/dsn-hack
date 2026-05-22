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
        },
    )
    if context:
        state["turns"].append(context)
    return sid, state


def session_context(state: dict) -> str:
    return " ".join(state.get("turns", [])[-4:])
