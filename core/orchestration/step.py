from __future__ import annotations

from abc import ABC, abstractmethod

from core.schemas import AgentRuntimeContext


class Step(ABC):
    name: str

    def __init__(self, name: str | None = None):
        self.name = name or self.__class__.__name__

    @abstractmethod
    async def run(self, context: AgentRuntimeContext) -> AgentRuntimeContext:
        """Run this step and return the mutated context."""
