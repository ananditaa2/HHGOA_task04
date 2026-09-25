"""
Evidence Simulator (Deterministic Customer & Analyst Response Simulator)
Responses are derived from the actual evidence of each case — the trigger text,
the real-history recurring cadence, device New/Found status, the amount profile
(p95 baseline), and the real shared-origin ring — never from a case-id list.
Per README (2).md §5, customer and analyst replies are not provided; they are
simulated here and the assumption is recorded in the case's evidence_requests.
"""

from typing import Dict, List, Any, Optional, Tuple
from src.agents.base_agent import BaseAgent, AgentContext, mark_graph_signal_unavailable
from src.data.real_data import STORE


class EvidenceSimulatorAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="EvidenceSimulatorAgent")

    # ------------------------------------------------------------------
    def run(self, context: AgentContext, graph: Any) -> AgentContext:
        baseline = context.trigger_details.get("baseline", {})
        id_15 = str(context.trigger_details.get("id_15", "")).lower()
        proxy_flag = str(context.trigger_details.get("proxy_flag", ""))
        ring = context.trigger_details.get("ring_cards", []) or []
        if getattr(graph, "is_mcp", False):
            return self._run_mcp(context, ring, proxy_flag)
        amount = self._flagged_amount(context)
        recurring, recurring_count = self._recurring_stats(context)

        trigger_text = str(context.trigger_details.get("trigger_text", ""))
        disputed = context.trigger_type == "customer_report" or "never made" in trigger_text.lower()
        outside_profile = bool(baseline.get("outside_profile"))

        # ------------------------------------------------------------------
        # Single decision: what does the customer's simulated stance resolve to?
        #   "acknowledged"  -> recurring subscription recognised (R7)
        #   "denied"        -> customer reaffirms the dispute / ring denial
        #   "stepup_failed" -> adverse non-response (outside-profile new device)
        #   "confirmed"     -> cardholder confirms (travel, own device, VPN, ...)
        # ------------------------------------------------------------------
        decision, message = self._customer_stance(
            disputed, recurring, recurring_count, len(ring) >= 3,
            id_15, proxy_flag, outside_profile, amount, baseline)

        responses: List[Dict[str, Any]] = []
        for req in context.evidence_requests:
            req_type = req.get("request_type", "")

            if req_type == "device_forensics":
                responses.append(self._analyst_ring_response(req, ring, proxy_flag,
                                                             context.opened_at))
                continue

            if req_type == "step_up_challenge":
                passed = decision == "confirmed"
                responses.append({
                    "request_id": req.get("request_id"),
                    "responder": "customer",
                    "response_type": "step_up_result",
                    "status": "step_up_passed" if passed else "step_up_failed",
                    "message": (message if not passed else
                                "Cardholder completed the OTP challenge promptly."),
                    "verification_timestamp": context.opened_at,
                })
                continue

            # customer_verification / subscription_inquiry / incident_affidavit
            status_map = {
                "acknowledged": "subscription_acknowledged",
                "denied": "denied_transaction",
                "stepup_failed": "denied_transaction",
                "confirmed": "confirmed_authorized",
            }
            responses.append({
                "request_id": req.get("request_id"),
                "responder": "customer",
                "response_type": ("subscription_acknowledgment" if decision == "acknowledged"
                                  else "fraud_denial" if decision in ("denied", "stepup_failed")
                                  else "transaction_confirmation"),
                "status": status_map[decision],
                "message": message,
                "verification_timestamp": context.opened_at,
            })

        context.simulated_responses = responses
        return context

    @staticmethod
    def _run_mcp(
        context: AgentContext,
        ring: List[Dict[str, str]],
        proxy_flag: str,
    ) -> AgentContext:
        mark_graph_signal_unavailable(
            context,
            "customer_amount_history",
            "The deployed graph contains no transaction amounts or prior amount history.",
        )
        responses: List[Dict[str, Any]] = []
        reported_dispute = (
            context.trigger_type == "customer_report"
            or "never made" in str(context.trigger_details.get("trigger_text", "")).lower()
        )
        for request in context.evidence_requests:
            request_type = request.get("request_type", "")
            if request_type == "customer_verification" and reported_dispute:
                responses.append({
                    "request_id": request.get("request_id"),
                    "responder": "case_record",
                    "response_type": "recorded_customer_report",
                    "status": "denied_transaction",
                    "message": "The existing case record states that the customer disputes this transaction; no customer was contacted.",
                    "verification_timestamp": context.opened_at,
                })
            else:
                unavailable_signal = (
                    "device_forensics"
                    if request_type == "device_forensics"
                    else "customer_verification"
                )
                mark_graph_signal_unavailable(
                    context,
                    unavailable_signal,
                    "No live analyst or customer action was performed; the graph has no supporting profile attributes.",
                )
                responses.append({
                    "request_id": request.get("request_id"),
                    "responder": "system",
                    "response_type": "evidence_unavailable",
                    "status": "not_obtained",
                    "message": "No external customer or analyst action was performed; required graph evidence is unavailable.",
                    "verification_timestamp": context.opened_at,
                })
        context.simulated_responses = responses
        return context

    # ------------------------------------------------------------------
    @staticmethod
    def _customer_stance(disputed: bool, recurring: bool, recurring_count: int,
                         ring: bool, id_15: str, proxy_flag: str,
                         outside_profile: bool, amount: float,
                         baseline: Dict[str, Any]) -> Tuple[str, str]:
        """The one place a simulated customer response is decided."""
        if disputed and recurring:
            return "acknowledged", (
                f"On review the customer recognised the charge: ${amount:,.2f} recurs in their own "
                f"transaction history ({recurring_count} prior charges at the same amount) — a "
                f"subscription they had forgotten. They will cancel it via the merchant.")
        if disputed:
            return "denied", (
                f"Customer reaffirms the report: they did not make the ${amount:,.2f} purchase"
                + (" and do not recognise the device." if id_15 == "new" else "."))
        if recurring:
            return "acknowledged", (
                f"Customer recognised the charge as a recurring subscription: ${amount:,.2f} appears "
                f"{recurring_count} times at the same amount in their own history.")
        if ring:
            return "denied", (
                "Cardholder denied the transaction and does not recognise the device; the same "
                "device profile is active on other accounts in the same window.")
        if id_15 == "new" and outside_profile:
            return "stepup_failed", (
                f"No response to the OTP challenge; the ${amount:,.2f} purchase exceeds 1.25x the "
                f"cardholder's p95 spend (${baseline.get('p95_amt', 0):,.2f}) and came from a "
                f"first-seen device.")
        if id_15 == "new":
            return "confirmed", ("Cardholder confirmed the purchase and explained the new device "
                                 "is their own.")
        if proxy_flag:
            return "confirmed", ("Cardholder confirmed the transaction was made over a corporate "
                                 "VPN, which explains the proxy flag.")
        return "confirmed", ("Cardholder confirmed the transaction after reviewing the billing "
                             "descriptor.")

    # ------------------------------------------------------------------
    @staticmethod
    def _flagged_amount(context: AgentContext) -> float:
        txn = STORE.get_flagged_txn(context.flagged_txn_id) or {}
        try:
            return float(txn.get("TransactionAmt") or 0)
        except (TypeError, ValueError):
            return 0.0

    @staticmethod
    def _recurring_stats(context: AgentContext) -> Tuple[bool, int]:
        """Real-history cadence test: how many prior charges match the flagged
        amount EXACTLY. A 1% tolerance matches hundreds of coincidental
        near-equal charges in this dataset and destroys the signal; a half-cent
        tolerance isolates true billing recurrences."""
        def _f(v, default=0.0):
            try:
                return float(v)
            except (TypeError, ValueError):
                return default

        tid = context.flagged_txn_id
        amount = EvidenceSimulatorAgent._flagged_amount(context)
        if amount <= 0:
            return False, 0
        hist = STORE.get_card_history(context.customer_id)
        n_same = sum(1 for r in hist
                     if r.get("TransactionID") != tid
                     and abs(_f(r.get("TransactionAmt")) - amount) <= 0.005)
        return n_same >= 3, n_same

    @staticmethod
    def _analyst_ring_response(req: Dict[str, Any], ring: List[Dict[str, str]],
                               proxy_flag: str, opened_at: str) -> Dict[str, Any]:
        examples = [c["card_id"] for c in ring[:5]]
        return {
            "request_id": req.get("request_id"),
            "responder": "analyst",
            "response_type": "ring_investigation",
            "status": "confirmed_device_syndicate" if len(ring) >= 3 else "no_ring_found",
            "message": (f"Analyst review of the real shared-origin population: the device profile appears on "
                        f"{len(ring)} customer cards in the 45-day window ({', '.join(examples) if examples else 'none'}), "
                        f"proxy flag '{proxy_flag}'. "
                        + ("Coordinated use of one proxied device across many cardholders confirmed."
                           if len(ring) >= 3 else
                           "No multi-card coordination found on this device.")),
            "verification_timestamp": opened_at,
        }
