from __future__ import annotations

import time

from tcm.agent import consult
from tcm.schemas import TCMConsultRequest, UserContext

from ..normalization import normalize_tcm_response
from ..schemas import AgentOutput


class TCMAdapter:
    async def run(self, question: str, context: UserContext) -> AgentOutput:
        started = time.perf_counter()
        response = await consult(TCMConsultRequest(question=question, context=context))
        latency_ms = round((time.perf_counter() - started) * 1000)
        return normalize_tcm_response(response, latency_ms=latency_ms)
