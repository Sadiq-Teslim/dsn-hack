from typing import Any

from pydantic import BaseModel, Field, field_validator


class HistoryItem(BaseModel):
    title: str
    category: str
    rating: float = Field(ge=1, le=5)
    review_text: str = ""


class UserPersona(BaseModel):
    name: str = "Guest"
    location: str = "Lagos, Nigeria"
    age_range: str = "18-24"
    occupation: str = "Student"
    interests: list[str] = Field(default_factory=list)
    budget_level: str = "medium"
    tone: str = "warm and practical"
    likes: list[str] = Field(default_factory=list)
    dislikes: list[str] = Field(default_factory=list)
    language_preference: str = "English"
    cultural_context: str = "Nigerian urban shopper"
    history: list[HistoryItem] = Field(default_factory=list)


class ProductDetails(BaseModel):
    title: str
    category: str
    description: str = ""
    price: float | None = Field(default=None, ge=0)
    brand: str | None = None
    attributes: dict[str, Any] = Field(default_factory=dict)


class GenerateReviewRequest(BaseModel):
    user_persona: UserPersona
    product: ProductDetails


class EvidenceItem(BaseModel):
    title: str
    category: str
    rating: float
    reason: str
    source: str | None = None
    review_text: str | None = None
    retrieval_score: float | None = None


class GenerateReviewResponse(BaseModel):
    rating: float
    review_text: str
    confidence: float
    reasoning: str
    evidence: list[EvidenceItem]
    llm_provider: str
    fallback_used: bool
    reasoning_trace: dict[str, Any] | None = None
    calibration: dict[str, Any] | None = None
    consistency_check: str | None = None


class RecommendRequest(BaseModel):
    user_persona: UserPersona
    context: str = ""
    top_k: int = Field(default=10, ge=1, le=20)
    include_categories: list[str] = Field(default_factory=list)
    session_id: str | None = None
    conversational: bool = False


class RecommendedItem(BaseModel):
    rank: int
    item_id: str
    title: str
    category: str
    score: float
    reason: str
    matched_preferences: list[str]
    price: float | None = None


class RecommendResponse(BaseModel):
    items: list[RecommendedItem]
    reasoning: str
    llm_provider: str
    fallback_used: bool
    reasoning_trace: dict[str, Any] | None = None
    session_id: str | None = None
    status: str = "complete"
    follow_up_questions: list[str] = Field(default_factory=list)


class YarnRequest(BaseModel):
    user_persona: UserPersona
    source_text: str = Field(min_length=1)
    mode: str = "Nigerian Pidgin"
    task: str = "review"


class YarnResponse(BaseModel):
    mode: str
    voice_script: str
    audio_hint: str
    judge_note: str
    fallback_used: bool


class YarnTTSRequest(BaseModel):
    text: str = Field(min_length=1, max_length=2000)
    voice: str = "Idera"
    response_format: str = "mp3"


class YarnTTSResponse(BaseModel):
    audio_data_url: str | None
    voice: str
    response_format: str
    fallback_used: bool
    message: str


class DemoPersona(BaseModel):
    id: str
    label: str
    persona: UserPersona


class HealthResponse(BaseModel):
    status: str
    app: str
    llm_provider: str
    groq_configured: bool
    yarngpt_configured: bool = False


class EvaluationMetrics(BaseModel):
    task_a_rmse: float
    task_a_rouge_l: float
    task_b_ndcg_at_10: float
    task_b_hit_rate_at_10: float
    notes: list[str]


class DatasetBuildRequest(BaseModel):
    categories: list[str] = Field(
        default_factory=lambda: [
            "Grocery_and_Gourmet_Food",
            "Movies_and_TV",
            "Video_Games",
            "All_Beauty",
        ]
    )
    max_reviews_per_category: int = Field(default=5000, ge=100, le=100000)

    @field_validator("categories")
    @classmethod
    def require_categories(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("At least one category is required.")
        return value
