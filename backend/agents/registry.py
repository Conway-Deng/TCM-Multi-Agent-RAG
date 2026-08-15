from __future__ import annotations

from .specialists import (
    AcupunctureMeridianAgent,
    ConstitutionAgent,
    DietaryTherapyAgent,
    HerbalKnowledgeAgent,
    LifestyleYangshengAgent,
    SingleRAGAgent,
    SyndromeDifferentiationAgent,
)


AGENT_CLASSES = {
    "syndrome": SyndromeDifferentiationAgent,
    "herbal": HerbalKnowledgeAgent,
    "acupuncture_meridian": AcupunctureMeridianAgent,
    "constitution": ConstitutionAgent,
    "dietary_therapy": DietaryTherapyAgent,
    "lifestyle_yangsheng": LifestyleYangshengAgent,
    "single_rag": SingleRAGAgent,
}

AGENT_REGISTRY = [
    {"id": agent_id, "name": cls.agent_name, "version": cls.version, "subdomain": cls.subdomain}
    for agent_id, cls in AGENT_CLASSES.items()
]


def build_agents(agent_ids: list[str]):
    return [AGENT_CLASSES[agent_id]() for agent_id in dict.fromkeys(agent_ids) if agent_id in AGENT_CLASSES]
