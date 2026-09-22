from __future__ import annotations

import json

from providers import build_llm_provider
from providers.base import LLMProvider

from .model_calls import StructuredCallResult, call_structured_model
from .schemas import ActivePerspectiveName, RoutingDecision


ROUTER_MODEL = "THUDM/GLM-4-9B-0414"
ROUTER_SYSTEM_PROMPT = (
    "You are a routing component for a development-only evidence system. "
    "Decide whether the question should be sent to the TCM evidence pathway, the Western evidence pathway, or both. "
    "Do not answer the health question, offer medical advice, or add medical facts. "
    "The only available perspectives are tcm and western. Return one JSON object matching the requested schema."
)


class CrossPerspectiveRouter:
    def __init__(self, provider: LLMProvider | None = None) -> None:
        self.provider = provider or build_llm_provider(ROUTER_MODEL, thinking_behavior="omit")

    async def route_auto(self, question: str) -> StructuredCallResult:
        prompt = (
            f"Question:\n{question}\n\n"
            "Return JSON with use_tcm, use_western, reason_summary, and requested_perspectives. "
            "requested_perspectives must exactly match the true routing booleans."
        )
        return await call_structured_model(
            provider=self.provider,
            role="router",
            response_model=RoutingDecision,
            system=ROUTER_SYSTEM_PROMPT,
            prompt=prompt,
            max_tokens=256,
        )

    @staticmethod
    def route_forced(perspectives: list[ActivePerspectiveName]) -> RoutingDecision:
        selected = list(dict.fromkeys(perspectives))
        return RoutingDecision(
            use_tcm="tcm" in selected,
            use_western="western" in selected,
            reason_summary="Perspectives were selected explicitly by forced development routing.",
            requested_perspectives=selected,
        )


def routing_payload(decision: RoutingDecision) -> str:
    return json.dumps(decision.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
