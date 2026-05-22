from __future__ import annotations

from uuid import uuid4

from core.schemas import ReasoningTrace, StepTrace


def new_trace(pipeline: str, request_id: str | None = None) -> ReasoningTrace:
    return ReasoningTrace(request_id=request_id or str(uuid4()), pipeline=pipeline)


def add_step_trace(
    trace: ReasoningTrace,
    name: str,
    summary: str,
    latency_ms: float,
    inputs: dict | None = None,
    outputs: dict | None = None,
) -> None:
    trace.steps.append(
        StepTrace(
            name=name,
            summary=summary,
            latency_ms=latency_ms,
            inputs=inputs or {},
            outputs=outputs or {},
        )
    )
