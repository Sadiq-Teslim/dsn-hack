from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "BCT LLM Agent Challenge"
    llm_provider: str = "groq"
    groq_api_key: str | None = None
    groq_model: str = "llama-3.1-8b-instant"
    groq_base_url: str = "https://api.groq.com/openai/v1"
    yarngpt_api_key: str | None = None
    yarngpt_base_url: str = "https://yarngpt.ai/api/v1"
    yarngpt_voice: str = "Idera"
    yarngpt_response_format: str = "mp3"
    llm_timeout_seconds: float = 12.0
    data_path: str = "data/fixtures"
    cors_origins: list[str] = ["*"]

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")


@lru_cache
def get_settings() -> Settings:
    return Settings()
