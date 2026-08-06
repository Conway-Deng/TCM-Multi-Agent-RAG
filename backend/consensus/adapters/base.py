from __future__ import annotations

from typing import Protocol

from tcm.schemas import UserContext

from ..schemas import AgentOutput


class AdapterError(Exception):
    """Safe domain-adapter error suitable for an API response."""


class FixtureDisabledError(AdapterError):
    pass


class AdapterUnavailableError(AdapterError):
    pass


class DomainAdapter(Protocol):
    async def run(self, question: str, context: UserContext) -> AgentOutput: ...
