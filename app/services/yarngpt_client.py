import base64

import httpx

from app.config import Settings


class YarnGPTClient:
    def __init__(self, settings: Settings):
        self.settings = settings

    @property
    def configured(self) -> bool:
        return bool(self.settings.yarngpt_api_key)

    async def text_to_speech(
        self,
        text: str,
        voice: str,
        response_format: str,
    ) -> tuple[str | None, str]:
        if not self.configured:
            return None, "YarnGPT API key is not configured."

        url = f"{self.settings.yarngpt_base_url.rstrip('/')}/tts"
        headers = {"Authorization": f"Bearer {self.settings.yarngpt_api_key}"}
        payload = {
            "text": text[:2000],
            "voice": voice or self.settings.yarngpt_voice,
            "response_format": response_format or self.settings.yarngpt_response_format,
        }
        try:
            async with httpx.AsyncClient(timeout=45.0) as client:
                response = await client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            detail = exc.response.text[:220] if exc.response is not None else str(exc)
            return None, f"YarnGPT request failed: {detail}"
        except httpx.HTTPError as exc:
            return None, f"YarnGPT request failed: {exc}"

        mime = {
            "mp3": "audio/mpeg",
            "wav": "audio/wav",
            "opus": "audio/ogg",
            "flac": "audio/flac",
        }.get(payload["response_format"], "audio/mpeg")
        encoded = base64.b64encode(response.content).decode("ascii")
        return f"data:{mime};base64,{encoded}", "YarnGPT audio generated."
