"""
Metrics and Audit Reporting Utilities (README answer-format aware)
"""

from typing import Dict, List, Any


def calculate_case_pack_metrics(case_results: List[Dict[str, Any]]) -> Dict[str, Any]:
    total_cases = len(case_results)

    def verdict(c):
        return c.get("case", {}).get("verdict", c.get("investigation", {}).get("verdict", ""))

    def exposure(c):
        return c.get("case", {}).get("exposure_usd",
                                     c.get("investigation", {}).get("exposure_usd", 0.0))

    def conflict(c):
        return c.get("case", {}).get("conflict_score",
                                     c.get("investigation", {}).get("conflict_score", 0.0))

    def pattern(c):
        return c.get("case", {}).get("pattern",
                                     c.get("investigation", {}).get("pattern", ""))

    def actions(c, phase):
        nba = c.get("next_best_actions", {})
        return [a.get("action") for a in nba.get(phase, [])]

    fraud_count = sum(1 for c in case_results if verdict(c) == "fraud")
    legit_count = sum(1 for c in case_results if verdict(c) == "legitimate")
    sar_count = sum(1 for c in case_results if c.get("sar", {}).get("file") is True)
    total_exposure = sum(exposure(c) for c in case_results)

    rules_triggered = set()
    for c in case_results:
        finals = actions(c, "final")
        inits = actions(c, "initial")
        if "VERIFY_WITH_CUSTOMER" in inits:
            rules_triggered.add("R1")
        if "BLOCK_CARD" in finals:
            rules_triggered.add("R2")
        if "CLOSE_NO_FRAUD" in finals:
            rules_triggered.add("R3")
        if "DECLINE_TRANSACTION" in finals or "DECLINE_TRANSACTION" in inits:
            rules_triggered.add("R5")
        if "MONITOR_CONNECTED_CARDS" in finals:
            rules_triggered.add("R6")
        if "WARN_CUSTOMER" in finals:
            rules_triggered.add("R7")
        if conflict(c) >= 0.40 or "ESCALATE_TO_ANALYST" in finals:
            rules_triggered.add("R8")
        if pattern(c) == "undocumented":
            rules_triggered.add("R9")
        if c.get("sar", {}).get("file") is True or "FILE_REPORT" in finals:
            rules_triggered.add("R9")
        if any(a.get("route") == "L2" for a in c.get("next_best_actions", {}).get("final", [])):
            rules_triggered.add("L2-route")

    evolved_count = 0
    for c in case_results:
        if actions(c, "initial") != actions(c, "final"):
            evolved_count += 1

    return {
        "total_cases": total_cases,
        "fraud_cases": fraud_count,
        "legitimate_cases": legit_count,
        "sar_filings": sar_count,
        "total_exposure_usd": round(total_exposure, 2),
        "rule_coverage_count": len(rules_triggered),
        "rules_triggered": sorted(rules_triggered),
        "evolution_count": evolved_count,
        "evolution_rate_pct": round((evolved_count / total_cases * 100), 1) if total_cases else 0.0,
    }
