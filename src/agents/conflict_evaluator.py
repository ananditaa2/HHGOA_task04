"""
Evidence Conflict Scoring Engine (Strategic Innovation 2: Rule R8)
Calculates explicit quantitative conflict score C in [0.0, 1.0] and logs
precisely which signals disagree with each other.
"""

from typing import Dict, List, Any, Tuple
from src.agents.base_agent import BaseAgent, AgentContext
from src.config import EVIDENCE_CONFLICT_THRESHOLD


class ConflictEvaluatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="EvidenceConflictEvaluator")

    def run(self, context: AgentContext, graph: Any) -> AgentContext:
        signals: List[Dict[str, Any]] = []

        # 1. Evaluate Polarity & Weights of Gathered Evidence
        for ev in context.evidence:
            sig_name = ev.get("signal", "")
            val = ev.get("value")
            weight = ev.get("weight", 0.5)

            # Polarity: +1.0 for Fraud signal, -1.0 for Legitimate signal, 0.0 for Neutral
            polarity = 0.0
            if sig_name == "risk_score_evaluation":
                score = float(val)
                polarity = 0.85 if score >= 0.70 else (0.65 if score >= 0.50 else -0.8)
            elif sig_name == "proxy_detection":
                polarity = 1.0 if val == "anonymous_proxy" else -0.4
            elif sig_name in ("card_testing_sequence", "shared_device_ring"):
                polarity = 1.0
            elif sig_name == "out_of_region_spend":
                polarity = 0.85
            elif sig_name in ("prior_region_history", "historical_merchant_loyalty"):
                polarity = -1.0
            elif "recurring" in sig_name:
                polarity = -0.9

            signals.append({
                "signal": sig_name,
                "value": str(val),
                "weight": weight,
                "polarity": polarity,
                "description": ev.get("description", "")
            })

        # Add Baseline Customer History Signal if available
        cid = context.customer_id
        tid = context.flagged_txn_id
        region_res = graph.query_out_of_region(cid, tid)
        if region_res.get("home_region_txns", 0) > 10 and not region_res.get("is_out_of_region", False):
            signals.append({
                "signal": "historical_merchant_loyalty",
                "value": f"{region_res.get('home_region_txns')} past txns",
                "weight": 0.8,
                "polarity": -1.0,
                "description": "Cardholder has extensive established transaction history in this category/region."
            })

        # 2. Compute Quantitative Conflict Score C
        conflict_sum = 0.0
        weight_pairs_sum = 0.0
        conflicting_pairs: List[Dict[str, Any]] = []

        n = len(signals)
        for i in range(n):
            for j in range(i + 1, n):
                s1 = signals[i]
                s2 = signals[j]
                w_pair = s1["weight"] * s2["weight"]
                p_diff = abs(s1["polarity"] - s2["polarity"])
                
                # Only contrast signals with opposite polarities
                if (s1["polarity"] > 0 and s2["polarity"] < 0) or (s1["polarity"] < 0 and s2["polarity"] > 0):
                    conflict_sum += w_pair * p_diff
                    conflicting_pairs.append({
                        "signal_a": s1["signal"],
                        "polarity_a": s1["polarity"],
                        "signal_b": s2["signal"],
                        "polarity_b": s2["polarity"],
                        "delta": round(p_diff, 2),
                        "details": f"{s1['signal']} (polarity={s1['polarity']}) disagrees with {s2['signal']} (polarity={s2['polarity']})"
                    })
                weight_pairs_sum += w_pair

        raw_c = (conflict_sum / (2.0 * weight_pairs_sum)) if weight_pairs_sum > 0 else 0.0
        final_c = round(min(1.0, max(0.0, raw_c)), 3)

        # Classify Uncertainty Level
        if final_c >= EVIDENCE_CONFLICT_THRESHOLD:
            uncertainty = "high"
        elif final_c >= 0.20:
            uncertainty = "medium"
        else:
            uncertainty = "low"

        context.conflict_score = final_c
        context.conflicting_signals = conflicting_pairs
        context.uncertainty_level = uncertainty

        return context
