from __future__ import annotations

import time

from core.orchestration.step import Step
from core.orchestration.trace import add_step_trace
from core.schemas import AgentRuntimeContext


class Pipeline:
    def __init__(self, name: str, steps: list[Step]):
        self.name = name
        self.steps = steps

    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        for step in self.steps:
            started = time.perf_counter()
            before_keys = sorted(context.working.keys())
            context = await step.run(context)
            elapsed = (time.perf_counter() - started) * 1000
            outputs = context.working.get("_last_step_outputs", {})
            add_step_trace(
                context.trace,
                step.name,
                outputs.pop("_summary", f"{step.name} completed."),
                elapsed,
                inputs={"working_keys_before": before_keys},
                outputs=outputs,
            )
            context.working.pop("_last_step_outputs", None)
        return context
