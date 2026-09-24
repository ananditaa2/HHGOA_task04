"""
Time-Decay Weighted Case Memory Retrieval (Strategic Innovation 4)
Applies exponential half-life decay W(dt) = exp(-ln(2)*dt / tau) with tau = 45 days
to prioritize recent historical fraud precedents over stale cases.
"""

import math
import datetime
from typing import Dict, List, Any, Optional, Tuple
from src.config import TIME_DECAY_HALF_LIFE_DAYS


class CaseMemoryRetriever:
    def __init__(self, half_life_days: float = TIME_DECAY_HALF_LIFE_DAYS):
        self.half_life_days = half_life_days

    def compute_decay_weight(self, alert_date_str: str, precedent_date_str: str) -> Tuple[float, float]:
        """
        Computes the time decay weight and days difference.
        Returns: (decay_weight, days_difference)
        """
        try:
            alert_dt = datetime.datetime.fromisoformat(alert_date_str.replace("Z", ""))
        except Exception:
            alert_dt = datetime.datetime.now()

        try:
            precedent_dt = datetime.datetime.fromisoformat(precedent_date_str.replace("Z", ""))
        except Exception:
            precedent_dt = alert_dt - datetime.timedelta(days=30)

        dt_days = max(0.0, (alert_dt - precedent_dt).total_seconds() / 86400.0)
        weight = math.exp(-math.log(2.0) * dt_days / self.half_life_days)
        return round(weight, 4), round(dt_days, 1)

    def rank_precedents(
        self,
        current_case: Dict[str, Any],
        historical_cases: List[Dict[str, Any]],
        limit: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Ranks historical cases based on semantic pattern similarity combined with time-decay weighting.
        """
        alert_date = current_case.get("opened_at", datetime.datetime.now().isoformat())
        target_pattern = str(current_case.get("pattern", "")).lower()

        ranked: List[Dict[str, Any]] = []
        for case in historical_cases:
            case_pattern = str(case.get("pattern", "")).lower()
            
            # Base pattern matching score
            sim_score = 0.5
            if target_pattern and case_pattern:
                if target_pattern == case_pattern:
                    sim_score = 1.0
                elif any(word in case_pattern for word in target_pattern.split("_")):
                    sim_score = 0.8

            closed_date = str(case.get("closed_at", case.get("opened_at", "")))
            decay_weight, dt_days = self.compute_decay_weight(alert_date, closed_date)

            composite_weight = round(sim_score * decay_weight, 4)

            enriched = dict(case)
            enriched["time_decay_weight"] = decay_weight
            enriched["days_prior"] = dt_days
            enriched["composite_relevance"] = composite_weight
            ranked.append(enriched)

        ranked.sort(key=lambda x: x.get("composite_relevance", 0.0), reverse=True)
        return ranked[:limit]
