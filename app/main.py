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
    RecommendedItem,
)
from app.services.data_store import DataStore, get_data_store
from app.services.evaluation import fixture_metrics
from app.services.generation import generate_recommendation_summary, generate_review_text
from app.services.scoring import predict_rating, rank_products, retrieve_evidence

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


@app.get("/health", response_model=HealthResponse)
async def health(settings: Settings = Depends(get_settings)) -> HealthResponse:
    return HealthResponse(
        status="ok",
        app=settings.app_name,
        llm_provider=settings.llm_provider,
        groq_configured=bool(settings.groq_api_key),
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


def _reason_for_item(item: dict) -> str:
    matches = ", ".join(item["matched_preferences"]) or "general preference fit"
    return (
        f"Score {item['score']:.3f}: strong {item['category'].replace('_', ' ')} fit, "
        f"{item.get('average_rating', 0):.1f}/5 catalog signal, matched {matches}."
    )
