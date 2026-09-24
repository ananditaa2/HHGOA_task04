"""
Strict JSON Schema & Answer Format Validator
Audits TigerDetect case JSONs against the exact answer format in README (2).md:
top-level fields, Part 1 (case), Part 2 (sar), Part 3 (next_best_actions),
enum vocabularies, and the SAR/verdict consistency rules.
"""

from typing import Dict, List, Any, Tuple
from src.rag.policy_store import VALID_ACTIONS, APPROVAL_ROUTES

VALID_VERDICTS = {"fraud", "legitimate", "uncertain"}
VALID_STATUSES = {"open", "closed_fraud", "closed_legitimate", "escalated"}
VALID_PATTERNS = {
    "card_testing", "card_not_present_fraud", "card_not_present_new_device",
    "out_of_region_use", "account_takeover", "undocumented", "none",
}
VALID_SOURCES = {"graph", "document", "customer", "external"}
VALID_EVIDENCE_REQUEST_TYPES = {"customer_validation", "step_up_auth", "analyst_info"}


class CaseSchemaValidator:
    @staticmethod
    def validate_case(case_data: Dict[str, Any]) -> Tuple[bool, List[str]]:
        errors: List[str] = []

        # 1. Top-level fields (README Answer Format)
        for k in ["case_id", "case", "evidence_requests", "next_best_actions",
                  "sar", "stop_reason", "tool_calls", "tokens", "latency_s"]:
            if k not in case_data:
                errors.append(f"Missing top-level key: '{k}'")
        if errors:
            return False, errors

        # 2. Part 1: case
        c = case_data.get("case", {})
        for k in ["status", "verdict", "fraud_probability", "pattern",
                  "pattern_description", "affected_txn_ids", "first_suspicious_txn_id",
                  "connected_card_ids", "connected_device_profiles", "exposure_usd",
                  "evidence", "similar_prior_cases", "summary",
                  "written_to_graph", "graph_case_id"]:
            if k not in c:
                errors.append(f"Missing case.{k}")
        if errors:
            return False, errors

        if c["verdict"] not in VALID_VERDICTS:
            errors.append(f"Invalid case.verdict: {c['verdict']}")
        if c["status"] not in VALID_STATUSES:
            errors.append(f"Invalid case.status: {c['status']}")
        if c["pattern"] not in VALID_PATTERNS:
            errors.append(f"Invalid case.pattern: {c['pattern']}")
        prob = c.get("fraud_probability")
        if not isinstance(prob, (int, float)) or not (0.0 <= float(prob) <= 1.0):
            errors.append(f"Invalid case.fraud_probability: {prob}")
        if c["pattern"] == "undocumented" and not str(c.get("pattern_description", "")).strip():
            errors.append("pattern_description required when pattern is 'undocumented'")

        is_legit = c["verdict"] == "legitimate"
        if is_legit:
            if c.get("affected_txn_ids") not in ([], None):
                errors.append("legitimate verdict requires empty affected_txn_ids")
            if float(c.get("exposure_usd", 0) or 0) != 0:
                errors.append("legitimate verdict requires exposure_usd = 0")
        else:
            if not c.get("affected_txn_ids"):
                errors.append("non-legitimate verdict requires non-empty affected_txn_ids")
            if float(c.get("exposure_usd", 0) or 0) <= 0:
                errors.append("non-legitimate verdict requires positive exposure_usd")

        # Evidence entries
        for i, ev in enumerate(c.get("evidence", [])):
            if ev.get("claim") is None or ev.get("source") not in VALID_SOURCES:
                errors.append(f"evidence[{i}] missing claim or invalid source")
            if "ref" not in ev or "entity_ids" not in ev:
                errors.append(f"evidence[{i}] missing ref/entity_ids")

        # 3. Part 2: sar
        sar = case_data.get("sar", {})
        if "file" not in sar:
            errors.append("sar.file missing")
        else:
            if sar["file"] is True:
                if not str(sar.get("narrative", "")).strip():
                    errors.append("sar.file=true requires narrative")
                if len(str(sar.get("narrative", "")).split()) < 20:
                    errors.append("sar.narrative too short (README: 6-12 sentences, self-standing)")
                if not sar.get("subjects"):
                    errors.append("sar.file=true requires subjects")
                if not sar.get("activity_dates") or len(sar.get("activity_dates")) != 2:
                    errors.append("sar.file=true requires activity_dates [first, last]")
                if not sar.get("total_amount_usd"):
                    errors.append("sar.file=true requires total_amount_usd")
            else:
                if str(sar.get("narrative", "") or "").strip():
                    errors.append("sar.file=false requires empty narrative")
                if sar.get("subjects") not in ([], None):
                    errors.append("sar.file=false requires empty subjects")
                if sar.get("total_amount_usd", 0) not in (0, 0.0, None):
                    errors.append("sar.file=false requires total_amount_usd = 0")
                if sar.get("activity_dates") not in ([], None):
                    errors.append("sar.file=false requires empty activity_dates")

        # 4. Part 3: next_best_actions
        nba = case_data.get("next_best_actions", {})
        for k in ["initial", "final", "what_changed"]:
            if k not in nba:
                errors.append(f"Missing next_best_actions.{k}")
        for phase in ("initial", "final"):
            for a in nba.get(phase, []):
                if a.get("action") not in VALID_ACTIONS:
                    errors.append(f"Invalid action in {phase}: {a.get('action')}")
                if a.get("route") not in APPROVAL_ROUTES:
                    errors.append(f"Invalid route in {phase}: {a.get('route')}")
                if not str(a.get("reason", "")).strip():
                    errors.append(f"Missing reason in {phase} action {a.get('action')}")
        if not nba.get("final"):
            errors.append("next_best_actions.final must contain at least one action")

        # 5. Evidence requests
        for i, r in enumerate(case_data.get("evidence_requests", [])):
            if r.get("type") not in VALID_EVIDENCE_REQUEST_TYPES:
                errors.append(f"evidence_requests[{i}] invalid type: {r.get('type')}")
            if "assumed_response" not in r or "asked_after_step" not in r:
                errors.append(f"evidence_requests[{i}] missing assumed_response/asked_after_step")

        return (len(errors) == 0), errors
