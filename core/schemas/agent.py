from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

from app.schemas import EvidenceItem, RecommendedItem, UserPersona


class NigerianRegister(str, Enum):
    STANDARD = "Standard Nigerian English"
    PIDGIN = "Nigerian Pidgin"
    YORUBA = "Yoruba-flavoured English"
    HAUSA = "Hausa-flavoured English"
    IGBO = "Igbo-flavoured English"
    FORMAL = "Formal judge summary"


class AgentDecisionStatus(str, Enum):
    COMPLETE = "complete"
    NEEDS_CLARIFICATION = "needs_clarification"
    FALLBACK = "fallback"


class StepTrace(BaseModel):
    name: str
    summary: str
    latency_ms: float = 0.0
    inputs: dict[str, Any] = Field(default_factory=dict)
    outputs: dict[str, Any] = Field(default_factory=dict)


class ReasoningTrace(BaseModel):
    request_id: str
    pipeline: str
    steps: list[StepTrace] = Field(default_factory=list)

    def compact(self) -> dict[str, Any]:
        return {
            "request_id": self.request_id,
            "pipeline": self.pipeline,
            "steps": [
                {
                    "name": step.name,
                    "summary": step.summary,
                    "latency_ms": round(step.latency_ms, 2),
                    "outputs": step.outputs,
                }
                for step in self.steps
            ],
        }


class UserProfile(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    persona: UserPersona
    history_count: int
    rating_mean: float
    rating_std: float
    rating_mode: float
    rating_skew: float
    rating_bias: float
    category_affinity: dict[str, float] = Field(default_factory=dict)
    vocabulary_fingerprint: list[str] = Field(default_factory=list)
    taste_tokens: list[str] = Field(default_factory=list)
    taste_embedding: dict[str, float] = Field(default_factory=dict)
    nigerian_register: NigerianRegister = Field(default=NigerianRegister.STANDARD, alias="register")
    cold_start: bool = False


class RatingCalibration(BaseModel):
    sentiment: float = Field(ge=0, le=1)
    raw_rating: float = Field(ge=1, le=5)
    calibrated_rating: float = Field(ge=1, le=5)
    explanation: str


class IntentSignal(BaseModel):
    raw_context: str = ""
    target_categories: list[str] = Field(default_factory=list)
    unsupported_targets: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    taste_descriptors: list[str] = Field(default_factory=list)
    is_cross_domain: bool = False
    is_cold_start: bool = False
    needs_clarification: bool = False
    clarification_questions: list[str] = Field(default_factory=list)


class CandidateItem(BaseModel):
    item_id: str
    title: str
    category: str
    score: float
    local_score: float
    llm_score: float | None = None
    reason: str
    matched_preferences: list[str] = Field(default_factory=list)
    price: float | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class NigerianExemplar(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    id: str
    nigerian_register: NigerianRegister = Field(alias="register")
    tone: str
    text: str
    tags: list[str] = Field(default_factory=list)


class AgentRuntimeContext(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    request_id: str
    session_id: str | None = None
    persona: UserPersona
    user_profile: UserProfile | None = None
    product: dict[str, Any] | None = None
    context: str = ""
    catalog: list[dict[str, Any]] = Field(default_factory=list)
    reviews: list[dict[str, Any]] = Field(default_factory=list)
    working: dict[str, Any] = Field(default_factory=dict)
    trace: ReasoningTrace


class TaskAAgentResult(BaseModel):
    rating: float
    review_text: str
    confidence: float
    reasoning: str
    evidence: list[EvidenceItem]
    calibration: RatingCalibration
    reasoning_trace: ReasoningTrace
    llm_provider: str
    fallback_used: bool
    consistency_check: str


class TaskBAgentResult(BaseModel):
    items: list[RecommendedItem]
    reasoning: str
    reasoning_trace: ReasoningTrace
    llm_provider: str
    fallback_used: bool
    session_id: str
    status: AgentDecisionStatus = AgentDecisionStatus.COMPLETE
    follow_up_questions: list[str] = Field(default_factory=list)
