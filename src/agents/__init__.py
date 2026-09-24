"""
Agents Package for TigerDetect
"""
from src.agents.base_agent import AgentContext, BaseAgent
from src.agents.detective_agent import DetectiveAgent
from src.agents.conflict_evaluator import ConflictEvaluatorAgent
from src.agents.critic_agent import CriticAgent
from src.agents.evidence_simulator import EvidenceSimulatorAgent
from src.agents.policy_engine import PolicyEngineAgent
from src.agents.coordinator import InvestigationCoordinator

__all__ = [
    "AgentContext",
    "BaseAgent",
    "DetectiveAgent",
    "ConflictEvaluatorAgent",
    "CriticAgent",
    "EvidenceSimulatorAgent",
    "PolicyEngineAgent",
    "InvestigationCoordinator"
]
