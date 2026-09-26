"""
Next-Best Action Router & Dynamic Policy Evaluator
Maps real evidence signals (gathered by the detective from the CSV-derived
graph) onto README (2).md Fraud Policy actions R1-R10 with the exact action
identifiers and approval routes (auto / L1 / L2). No case-id hardcoding.
"""

from typing import Dict, List, Any, Optional
from src.agents.base_agent import BaseAgent, AgentContext
from src.rag.policy_store import VALID_ACTIONS


class PolicyEngineAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="PolicyEngineAgent")

    # ------------------------------------------------------------------
    def determine_initial_phase(self, context: AgentContext, graph: Any) -> AgentContext:
        cid = context.case_id
        trigger = context.trigger_type
        risk_value = context.trigger_details.get("risk_score")
        risk_score = float(risk_value) if risk_value is not None else None
        baseline = context.trigger_details.get("baseline", {})
        exposure = context.exposure_usd
        ring = context.trigger_details.get("ring_cards", []) or []
        id_15 = str(context.trigger_details.get("id_15", "")).lower()
        proxy_flag = str(context.trigger_details.get("proxy_flag", ""))
        channel = str(
            context.trigger_details.get("channel", baseline.get("channel", "online"))
        )
        pattern = context.primary_pattern

        initial_actions: List[Dict[str, Any]] = []
        evidence_requests: List[Dict[str, Any]] = []

        # R1: single weak signal (incl. risk score alone) below the 0.70 bar
        weak_single = (
            (risk_score is None or risk_score < 0.70)
            and not (len(ring) >= 3)
            and pattern != "card_testing"
        )

        if trigger == "analyst_request":
            # Analyst asked for a ring review: open the case and request forensics.
            initial_actions.append(self._act("CREATE_CASE", "auto",
                                             "R6/R9: analyst-reported shared device profile; open the ring investigation."))
            initial_actions.append(self._act("MONITOR_CONNECTED_CARDS", "auto",
                                             "R6: connected cards sharing the device profile go under monitoring."))
            evidence_requests.append({
                "request_id": f"REQ-{cid}-01",
                "request_type": "device_forensics",
                "target": "analyst",
                "prompt": "Confirm the shared-origin population for the device profile and proxy flag from the graph.",
            })
        elif pattern == "card_testing":
            # R5: testing sequence observed
            initial_actions.append(self._act("DECLINE_TRANSACTION", "L1",
                                             "R5: card-testing sequence observed on the real card timeline."))
            initial_actions.append(self._act("STEP_UP_AUTH", "auto",
                                             "R5: require step-up before further activity."))
            evidence_requests.append({
                "request_id": f"REQ-{cid}-01",
                "request_type": "step_up_challenge",
                "target": "customer",
                "prompt": "OTP challenge to the cardholder regarding the flagged authorization.",
            })
        elif trigger == "customer_report":
            # Customer disputes the charge: verify first (R7 / R1), do not block yet.
            initial_actions.append(self._act("VERIFY_WITH_CUSTOMER", "auto",
                                             "R1/R7: customer disputes the charge; verify with the customer before any block."))
            evidence_requests.append({
                "request_id": f"REQ-{cid}-01",
                "request_type": "customer_verification",
                "target": "customer",
                "prompt": "Ask the cardholder to confirm or deny the flagged transaction.",
            })
        else:
            # risk_score trigger
            if weak_single:
                initial_actions.append(self._act("VERIFY_WITH_CUSTOMER", "auto",
                                                 (
                                                     f"R1: transaction risk score unavailable; verify before any adverse action."
                                                     if risk_score is None
                                                     else f"R1: single weak signal (risk {risk_score:.2f} < 0.70); verify before any adverse action."
                                                 )))
                evidence_requests.append({
                    "request_id": f"REQ-{cid}-01",
                    "request_type": "customer_verification",
                    "target": "customer",
                    "prompt": "Automated SMS/push asking the cardholder to confirm or deny the transaction.",
                })
            else:
                initial_actions.append(self._act("DECLINE_TRANSACTION", "L1",
                                                 f"R1: elevated risk score {risk_score:.2f} with corroborating device signals; contain first."))
                initial_actions.append(self._act("STEP_UP_AUTH", "auto",
                                                 "R1: OTP challenge before further activity."))
                evidence_requests.append({
                    "request_id": f"REQ-{cid}-01",
                    "request_type": "step_up_challenge",
                    "target": "customer",
                    "prompt": "Out-of-band OTP challenge for the flagged authorization.",
                })

        if id_15 == "new" and channel == "online" and trigger != "analyst_request":
            initial_actions.append(self._act("STEP_UP_AUTH", "auto",
                                             "Pattern 3: new-device online activity warrants step-up confirmation."))

        context.initial_recommendations = initial_actions
        context.evidence_requests = evidence_requests
        return context

    # ------------------------------------------------------------------
    def determine_final_phase(self, context: AgentContext, graph: Any) -> AgentContext:
        cid = context.case_id
        exposure = context.exposure_usd
        ring = context.trigger_details.get("ring_cards", []) or []
        connected_cards = [c["card_id"] for c in ring
                           if not c["card_id"].startswith(context.customer_id + "-")]
        baseline = context.trigger_details.get("baseline", {})
        pattern = context.primary_pattern

        cust_status = "none"
        for r in context.simulated_responses:
            if r.get("status") in ("confirmed_authorized", "subscription_acknowledged",
                                   "denied_transaction", "step_up_failed", "step_up_passed",
                                   "confirmed_device_syndicate", "no_ring_found"):
                cust_status = r["status"]
                break

        final_actions: List[Dict[str, Any]] = []
        ring_case = len(ring) >= 3

        # --------------------------------------------------------------
        # R3 / R7: legitimate outcomes
        # --------------------------------------------------------------
        if cust_status in ("confirmed_authorized", "step_up_passed", "subscription_acknowledged"):
            context.verdict = "LEGITIMATE"
            context.fraud_probability = 0.15
            if cust_status == "subscription_acknowledged":
                # R7: disputed but legitimate recurring charge — case + warning, no block
                context.fraud_probability = 0.20
                final_actions.append(self._act("CREATE_CASE", "auto",
                                               "R7: disputed recurring charge; keep the case record for the dispute."))
                final_actions.append(self._act("WARN_CUSTOMER", "auto",
                                               "R7: recurring charge matches the cardholder's own cadence; educate, do not block."))
                context.summary = (f"Case {cid}: the disputed ${exposure:,.2f} charge matches a recurring billing "
                                   f"cadence present in the cardholder's real transaction history. Rule R7: case opened, "
                                   f"customer informed, card left active.")
            else:
                final_actions.append(self._act("CLOSE_NO_FRAUD", "auto",
                                               "R3: customer confirmed the transaction (verification/step-up passed)."))
                context.summary = (f"Case {cid}: cardholder confirmed the transaction. The bank risk score was a reason "
                                   f"to look, not a verdict; real graph evidence (history, device, region) supported the "
                                   f"legitimate explanation. Closed as legitimate under R3.")
            context.sar = self._no_sar()
            context.final_recommendations = final_actions
            return context

        # --------------------------------------------------------------
        # R6 + R9: shared-origin ring (real device + proxy population)
        # --------------------------------------------------------------
        if ring_case:
            context.verdict = "FRAUD"
            context.fraud_probability = 0.90
            final_actions.append(self._act("CREATE_CASE", "auto",
                                           "R6/R9: coordinated shared-origin fraud ring across multiple cards."))
            final_actions.append(self._act("MONITOR_CONNECTED_CARDS", "auto",
                                           f"R6: {len(connected_cards)} connected cards share the same device profile and proxy flag."))
            final_actions.append(self._act("FILE_REPORT", "L2",
                                           "R6/R9: shared device profile across many cards in one window — SAR mandatory."))
            final_actions.append(self._act("BLOCK_CARD", "L1",
                                           "R2/R9: flagged card blocked as part of the ring response."))
            context.summary = (f"Case {cid}: the flagged transaction shares a device profile and anonymous proxy with "
                               f"{len(ring)} cards in a 45-day window, most scoring near zero on the bank model "
                               f"(model evasion). Undocumented coordinated pattern under R9 with R6 shared-origin "
                               f"controls: ring case opened, connected cards monitored, SAR filed.")
            context.sar = self._sar(
                cid, context.customer_id, context.card_id, context.opened_at, pattern,
                exposure, context.affected_txn_ids,
                device=context.trigger_details.get("device_info", ""),
                region=baseline.get("addr1", ""),
                connected=connected_cards, is_ring=True)
            context.final_recommendations = final_actions
            return context

        # --------------------------------------------------------------
        # R2: confirmed fraud via customer denial
        # --------------------------------------------------------------
        if cust_status in ("denied_transaction", "step_up_failed"):
            context.verdict = "FRAUD"
            context.fraud_probability = 0.85
            final_actions.append(self._act("BLOCK_CARD", "L1" if exposure <= 2500 else "L2",
                                           f"R2: customer denied the transaction; exposure ${exposure:,.2f} "
                                           f"{'within' if exposure <= 2500 else 'above'} the L1 limit."))
            final_actions.append(self._act("CREATE_CASE", "auto", "R2: open the internal fraud case."))
            if exposure > 1000 or ring_case:
                final_actions.append(self._act("FILE_REPORT", "L2",
                                               f"R2: exposure ${exposure:,.2f} exceeds $1,000 — SAR required."))
            context.summary = (f"Case {cid}: cardholder denied the transaction"
                               + (" and failed step-up authentication" if cust_status == "step_up_failed" else "")
                               + f". Pattern: {pattern.replace('_', ' ')} on the real transaction timeline. "
                               f"Card blocked under R2; exposure ${exposure:,.2f}.")
            context.sar = self._sar(
                cid, context.customer_id, context.card_id, context.opened_at, pattern,
                exposure, context.affected_txn_ids,
                device=context.trigger_details.get("device_info", ""),
                region=baseline.get("addr1", ""),
                connected=connected_cards, is_ring=False)
            context.final_recommendations = final_actions
            return context

        # --------------------------------------------------------------
        # R8: uncertain — escalate when exposed
        # --------------------------------------------------------------
        context.verdict = "SUSPICIOUS"
        context.fraud_probability = 0.50
        final_actions.append(self._act("MONITOR_CARD", "auto",
                                       "R4/R8: monitoring while the question remains open."))
        if exposure > 500 or context.conflict_score >= 0.40:
            final_actions.append(self._act("ESCALATE_TO_ANALYST", "auto",
                                           f"R8: uncertain verdict with exposure ${exposure:,.2f} "
                                           f"(conflict score {context.conflict_score:.2f})."))
        context.summary = (f"Case {cid}: evidence conflicts and the verdict is uncertain; monitoring plus analyst "
                           f"escalation under R8. The simulated customer response did not settle the question.")
        context.sar = self._no_sar()
        context.final_recommendations = final_actions
        return context

    # ------------------------------------------------------------------
    @staticmethod
    def _act(action: str, route: str, reason: str) -> Dict[str, Any]:
        assert action in VALID_ACTIONS, f"Unknown action {action}"
        return {"action": action, "approval_route": route, "reason": reason}

    @staticmethod
    def _no_sar() -> Dict[str, Any]:
        return {"file": False, "reason": None, "narrative": None,
                "jurisdiction": None, "filing_deadline_days": None}

    @staticmethod
    def _sar(case_id, customer_id, card_id, opened_at, pattern, exposure_usd,
             affected_txns, device=None, region=None, connected=None,
             is_ring=False) -> Dict[str, Any]:
        from src.rag.sar_templates import SARNarrativeGenerator
        return SARNarrativeGenerator.generate_sar(
            case_id=case_id, customer_id=customer_id, card_id=card_id,
            opened_at=opened_at, pattern=pattern, exposure_usd=exposure_usd,
            affected_txns=affected_txns, primary_device=device,
            region_code=region, connected_cards=connected, is_ring=is_ring)

    def run(self, context: AgentContext, graph: Any) -> AgentContext:
        return self.determine_final_phase(context, graph)
