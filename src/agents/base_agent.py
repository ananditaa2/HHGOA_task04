"""
Base Agent Protocol & Shared Investigation State
"""

from abc import ABC, abstractmethod
from typing import Dict, List, Any, Optional
from pydantic import BaseModel, Field


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
