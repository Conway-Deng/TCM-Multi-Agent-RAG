"""DEPRECATED and inactive. No active API imports this historical adapter."""
from __future__ import annotations

import os

from tcm.schemas import UserContext

from ..schemas import AgentOutput
from .base import AdapterUnavailableError


class WestAPIAdapter:
    """Interface placeholder for a future real MediRAG-West backend."""

    def __init__(self) -> None:
        self.base_url = os.getenv("WEST_API_BASE_URL", "").strip().rstrip("/")
        self.timeout = float(os.getenv("WEST_API_TIMEOUT_SECONDS", "30"))

    async def run(self, question: str, context: UserContext) -> AgentOutput:
        del question, context
        if not self.base_url:
            raise AdapterUnavailableError("WEST_API_BASE_URL is not configured.")
        raise AdapterUnavailableError(
            "The MediRAG-West API contract is not implemented yet; no network request was made."
        )
