"""True pinned local-model Agent, independent from frozen inference producers."""

from .contracts import (
    AgentBinding,
    AgentCamera,
    AgentDenied,
    AgentPolicy,
    AnswerCoverage,
    EvidenceRow,
    EvidenceSelection,
    ModelAction,
    RequestGoal,
    VerifiedAnswer,
)
from .manager import LocalAgentManager
from .provider import ModelCompletion, OllamaProvider

__all__ = [
    "AgentBinding", "AgentCamera", "AgentDenied", "AgentPolicy", "LocalAgentManager",
    "ModelAction", "ModelCompletion", "OllamaProvider", "AnswerCoverage", "EvidenceRow",
    "EvidenceSelection", "RequestGoal", "VerifiedAnswer",
]
