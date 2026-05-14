from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.schemas import (
    DemoPersona,
    HealthResponse,
    RecommendRequest,
    RecommendResponse,
    RecommendedItem,
    YarnRequest,
    YarnResponse,
    YarnTTSRequest,
    YarnTTSResponse,
)
from app.services.data_store import DataStore, get_data_store
from app.services.generation import generate_recommendation_summary, generate_yarn_text
from app.services.scoring import rank_products
from app.services.yarngpt_client import YarnGPTClient

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Team Ace Task B - Recommendation",
    description="Standalone personalized recommendation agent for the DSN x BCT LLM Agent Challenge.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", include_in_schema=False)
async def index() -> FileResponse:
    return FileResponse(STATIC_DIR / "task-b.html")


@app.get("/task-a", include_in_schema=False)
async def task_a_redirect() -> RedirectResponse:
    return RedirectResponse("/", status_code=307)


@app.get("/task-b", include_in_schema=False)
async def task_b_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "task-b.html")


@app.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app="Team Ace Task B - Recommendation",
        llm_provider=settings.llm_provider,
        groq_configured=bool(settings.groq_api_key),
        yarngpt_configured=bool(settings.yarngpt_api_key),
    )


@app.get("/api/v1/demo-personas", response_model=list[DemoPersona])
async def demo_personas(store: DataStore = Depends(get_data_store)) -> list[DemoPersona]:
    return store.demos()


@app.get("/api/v1/products")
async def products(store: DataStore = Depends(get_data_store)) -> list[dict]:
    return store.products


@app.post("/api/v1/recommend", response_model=RecommendResponse)
async def recommend(
    request: RecommendRequest,
    settings: Settings = Depends(get_settings),
    store: DataStore = Depends(get_data_store),
) -> RecommendResponse:
    ranked = rank_products(
        request.user_persona,
        store.products,
        request.context,
        request.include_categories,
        request.top_k,
    )
    items = [
        RecommendedItem(
            rank=index + 1,
            item_id=item["item_id"],
            title=item["title"],
            category=item["category"],
            score=item["score"],
            reason=_reason_for_item(item),
            matched_preferences=item["matched_preferences"],
            price=item.get("price"),
        )
        for index, item in enumerate(ranked)
    ]
    summary, fallback_used = await generate_recommendation_summary(
        settings,
        request.user_persona,
        request.context,
        [item.title for item in items],
    )
    return RecommendResponse(
        items=items,
        reasoning=summary,
        llm_provider=settings.llm_provider,
        fallback_used=fallback_used,
    )


@app.post("/api/v1/yarn", response_model=YarnResponse)
async def yarn_mode(
    request: YarnRequest,
    settings: Settings = Depends(get_settings),
) -> YarnResponse:
    script, note, fallback_used = await generate_yarn_text(
        settings,
        request.user_persona,
        request.source_text,
        request.mode,
        "recommendation",
    )
    return YarnResponse(
        mode=request.mode,
        voice_script=script,
        audio_hint="Use the audio controls in the browser for a spoken demo.",
        judge_note=note,
        fallback_used=fallback_used,
    )


@app.post("/api/v1/yarn-tts", response_model=YarnTTSResponse)
async def yarn_tts(
    request: YarnTTSRequest,
    settings: Settings = Depends(get_settings),
) -> YarnTTSResponse:
    client = YarnGPTClient(settings)
    audio_data_url, message = await client.text_to_speech(
        request.text,
        request.voice,
        request.response_format,
    )
    return YarnTTSResponse(
        audio_data_url=audio_data_url,
        voice=request.voice,
        response_format=request.response_format,
        fallback_used=audio_data_url is None,
        message=message,
    )


def _reason_for_item(item: dict) -> str:
    matches = ", ".join(item["matched_preferences"]) or "general preference fit"
    return (
        f"Score {item['score']:.3f}: strong {item['category'].replace('_', ' ')} fit, "
        f"{item.get('average_rating', 0):.1f}/5 catalog signal, matched {matches}."
    )
