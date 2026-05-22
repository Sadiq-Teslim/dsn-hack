from pathlib import Path

from fastapi import Depends, FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.config import Settings, get_settings
from app.schemas import (
    DemoPersona,
    EvaluationMetrics,
    GenerateReviewRequest,
    GenerateReviewResponse,
    HealthResponse,
    RecommendRequest,
    RecommendResponse,
    YarnRequest,
    YarnResponse,
    YarnTTSRequest,
    YarnTTSResponse,
)
from app.services.data_store import DataStore, get_data_store
from app.services.evaluation import fixture_metrics
from app.services.generation import generate_yarn_text
from app.services.yarngpt_client import YarnGPTClient
from core.task_a import run_task_a_pipeline
from core.task_b import run_task_b_pipeline

BASE_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = BASE_DIR / "static"

app = FastAPI(
    title="BCT LLM Agent Challenge",
    description="User modeling and recommendation agent for the DSN x BCT hackathon.",
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
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/task-a", include_in_schema=False)
async def task_a_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "task-a.html")


@app.get("/task-b", include_in_schema=False)
async def task_b_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "task-b.html")


@app.get("/evaluation", include_in_schema=False)
async def evaluation_page() -> FileResponse:
    return FileResponse(STATIC_DIR / "evaluation.html")


@app.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
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


@app.get("/api/v1/evaluation", response_model=EvaluationMetrics)
async def evaluation(store: DataStore = Depends(get_data_store)) -> EvaluationMetrics:
    return fixture_metrics(store.products, store.reviews)


@app.post("/api/v1/generate-review", response_model=GenerateReviewResponse)
async def generate_review(
    request: GenerateReviewRequest,
    settings: Settings = Depends(get_settings),
    store: DataStore = Depends(get_data_store),
) -> GenerateReviewResponse:
    result = await run_task_a_pipeline(
        settings,
        request.user_persona,
        request.product,
        store.products,
        store.reviews,
    )
    return GenerateReviewResponse(
        rating=result.rating,
        review_text=result.review_text,
        confidence=result.confidence,
        reasoning=result.reasoning,
        evidence=result.evidence,
        llm_provider=result.llm_provider,
        fallback_used=result.fallback_used,
        reasoning_trace=result.reasoning_trace.compact(),
        calibration=result.calibration.model_dump(),
        consistency_check=result.consistency_check,
    )


@app.post("/api/v1/recommend", response_model=RecommendResponse)
async def recommend(
    request: RecommendRequest,
    settings: Settings = Depends(get_settings),
    store: DataStore = Depends(get_data_store),
) -> RecommendResponse:
    result = await run_task_b_pipeline(
        settings,
        request.user_persona,
        store.products,
        request.context,
        request.include_categories,
        request.top_k,
        request.session_id,
        request.conversational,
    )
    return RecommendResponse(
        items=result.items,
        reasoning=result.reasoning,
        llm_provider=result.llm_provider,
        fallback_used=result.fallback_used,
        reasoning_trace=result.reasoning_trace.compact(),
        session_id=result.session_id,
        status=result.status.value,
        follow_up_questions=result.follow_up_questions,
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
        request.task,
    )
    return YarnResponse(
        mode=request.mode,
        voice_script=script,
        audio_hint="Use the Read Aloud button in the browser for a spoken demo.",
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
