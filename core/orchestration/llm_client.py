from __future__ import annotations

import json
import time
from typing import Any

from app.config import Settings
from app.services.groq_client import GroqClient


class CoreLLMClient:
    """Small Groq wrapper for agent steps: JSON parsing, retries, and fallback metadata."""

    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = GroqClient(settings)

    @property
    def configured(self) -> bool:
        return self.client.configured

    async def json_chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.25,
        attempts: int = 2,
    ) -> tuple[dict[str, Any] | None, dict[str, Any]]:
        started = time.perf_counter()
        last_text: str | None = None
        for attempt in range(1, attempts + 1):
            last_text = await self.client.chat(
                messages,
                temperature=temperature,
                response_format={"type": "json_object"},
            )
            parsed = self._json_object(last_text)
            if parsed is not None:
                return parsed, {
                    "configured": self.configured,
                    "attempts": attempt,
                    "latency_ms": round((time.perf_counter() - started) * 1000, 2),
                    "fallback_used": False,
                }
        return None, {
            "configured": self.configured,
            "attempts": attempts,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "fallback_used": True,
            "last_text": last_text,
        }

    @staticmethod
    def _json_object(text: str | None) -> dict[str, Any] | None:
        if not text:
            return None
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            stripped = stripped.removeprefix("json").strip()
        start = stripped.find("{")
        end = stripped.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        try:
            value = json.loads(stripped[start : end + 1])
        except json.JSONDecodeError:
            return None
        return value if isinstance(value, dict) else None
