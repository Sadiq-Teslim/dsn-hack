from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.schemas import (
    DemoPersona,
    GenerateReviewRequest,
    GenerateReviewResponse,
    HealthResponse,
    YarnRequest,
    YarnResponse,
    YarnTTSRequest,
    YarnTTSResponse,
)
from app.services.data_store import DataStore, get_data_store
from app.services.generation import generate_review_text, generate_yarn_text
from app.services.scoring import predict_rating, retrieve_evidence
from app.services.yarngpt_client import YarnGPTClient

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="Team Ace Task A - User Modeling",
    description="Standalone review and rating simulation agent for the DSN x BCT LLM Agent Challenge.",
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
    return FileResponse(STATIC_DIR / "task-a.html")


@app.get("/task-a", include_in_schema=False)
async def task_a_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "task-a.html")


@app.get("/task-b", include_in_schema=False)
async def task_b_redirect() -> RedirectResponse:
    return RedirectResponse("/", status_code=307)


@app.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app="Team Ace Task A - User Modeling",
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


@app.post("/api/v1/generate-review", response_model=GenerateReviewResponse)
async def generate_review(
    request: GenerateReviewRequest,
    settings: Settings = Depends(get_settings),
    store: DataStore = Depends(get_data_store),
) -> GenerateReviewResponse:
    catalog_item = next(
        (
            item
            for item in store.products
            if item["title"].lower() == request.product.title.lower()
            or item["category"] == request.product.category
        ),
        None,
    )
    rating, confidence, reasoning = predict_rating(
        request.user_persona,
        request.product,
        catalog_item,
    )
    evidence = retrieve_evidence(request.user_persona, request.product)
    review_text, fallback_used = await generate_review_text(
        settings,
        request.user_persona,
        request.product,
        rating,
        evidence,
    )
    return GenerateReviewResponse(
        rating=rating,
        review_text=review_text,
        confidence=confidence,
        reasoning=reasoning,
        evidence=evidence,
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
        "review",
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
