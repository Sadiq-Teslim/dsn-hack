import json
from typing import Any

import httpx

from app.config import Settings


class GroqClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.groq_api_key)

    async def chat(
        self,
        messages: list[dict[str, str]],
        temperature: float = 0.4,
        response_format: dict[str, str] | None = None,
    ) -> str | None:
        if not self.configured:
            return None

        url = f"{self.settings.groq_base_url.rstrip('/')}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.settings.groq_model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": 500,
        }
        if response_format:
            payload["response_format"] = response_format
        headers = {
            "Authorization": f"Bearer {self.settings.groq_api_key}",
            "Content-Type": "application/json",
        }
        try:
            async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, json.JSONDecodeError, KeyError, IndexError):
            return None

        try:
            return data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError):
            return None
