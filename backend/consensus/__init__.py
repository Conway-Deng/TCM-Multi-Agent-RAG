"""Deprecated pre-v1 cross-domain migration archive.

The active API imports ``backend/orchestration`` instead. This package is retained only
for rollback/audit safety and must not be imported by runtime code.
"""

from .orchestrator import ConsensusOrchestrator
from .schemas import AgentOutput, ConsensusConsultRequest, ConsensusResponse

DEPRECATED = True
__all__ = ["AgentOutput", "ConsensusConsultRequest", "ConsensusOrchestrator", "ConsensusResponse"]
