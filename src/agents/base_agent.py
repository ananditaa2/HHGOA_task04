"""
Base Agent Protocol & Shared Investigation State
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


def mark_graph_signal_unavailable(
    context: "AgentContext", signal: str, reason: str
) -> None:
    unavailable = context.trigger_details.setdefault("unavailable_graph_signals", [])
    if signal not in unavailable:
        unavailable.append(signal)
    if not any(
        item.get("signal") == "graph_signal_unavailable"
        and item.get("value", {}).get("signal") == signal
        for item in context.evidence
    ):
        context.evidence.append({
            "source": "tigergraph_mcp",
            "signal": "graph_signal_unavailable",
            "value": {"signal": signal, "reason": reason},
            "weight": 0.0,
            "path": f"(HHGOA_Fraud:unavailable:{signal})",
            "description": f"TigerGraph MCP could not provide {signal}: {reason}",
        })


class AgentContext(BaseModel):
    case_id: str
    opened_at: str
    trigger_type: str  # 'risk_score', 'customer_report', 'analyst_request'
    trigger_details: Dict[str, Any] = Field(default_factory=dict)
    
    # Target entities
    customer_id: str
    card_id: str
    flagged_txn_id: str
    
    # Graph-extracted signals
    affected_txn_ids: List[str] = Field(default_factory=list)
    exposure_usd: float = 0.0
    detected_patterns: List[str] = Field(default_factory=list)
    primary_pattern: str = "card_not_present_anomalous"
    
    # Evidence & Provenance
    evidence: List[Dict[str, Any]] = Field(default_factory=list)
    provenance_paths: List[str] = Field(default_factory=list)
    
    # Conflict & Uncertainty (Innovation 2)
    conflict_score: float = 0.0
    conflicting_signals: List[Dict[str, Any]] = Field(default_factory=list)
    uncertainty_level: str = "low"
    
    # Adversarial Critique (Innovation 5)
    devil_advocate_verdict: Optional[str] = None
    innocent_explanation_score: float = 0.0
    alternative_hypotheses: List[str] = Field(default_factory=list)
    
    # Evidence Requests & Simulation
    evidence_requests: List[Dict[str, Any]] = Field(default_factory=list)
    simulated_responses: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Recommendation Progression
    initial_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    final_recommendations: List[Dict[str, Any]] = Field(default_factory=list)
    
    # Final Verdict & SAR
    verdict: str = "FRAUD"  # FRAUD, LEGITIMATE, SUSPICIOUS
    fraud_probability: float = 0.85
    sar: Dict[str, Any] = Field(default_factory=dict)
    summary: str = ""


class BaseAgent(ABC):
    def __init__(self, name: str):
        self.name = name

    @abstractmethod
    def run(self, context: AgentContext, graph_adapter: Any) -> AgentContext:
        """Execute agent specialized reasoning step on the shared context."""
        pass
