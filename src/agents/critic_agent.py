"""
Adversarial Self-Critique Agent (Devil's Advocate - Strategic Innovation 5)
Challenges preliminary fraud findings by actively exploring innocent hypotheses:
recurring subscriptions, holiday travel, and single weak-signal false alarms.
"""

from typing import Dict, List, Any
from src.agents.base_agent import BaseAgent, AgentContext, mark_graph_signal_unavailable
from src.data.real_data import STORE


def _f(v, default=0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


class CriticAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="DevilsAdvocateCritic")

    def run(self, context: AgentContext, graph: Any) -> AgentContext:
        hypotheses: List[str] = []
        innocent_score = 0.0

        tid = context.flagged_txn_id
        graph_mode = bool(getattr(graph, "is_mcp", False))
        if graph_mode:
            txn = (
                context.trigger_details.get("mcp_transaction")
                or graph.get_transaction(tid)
                or {}
            )
        else:
            txn = graph.in_memory.get_vertex("Transaction", tid) or {}
        amount_value = txn.get("amount") if graph_mode else txn.get("amount", context.exposure_usd)
        amount = _f(amount_value, 0.0)
        baseline = context.trigger_details.get("baseline", {})
        mean_amt = float(baseline.get("mean_amt", 0) or 0)
        max_amt = float(baseline.get("max_amt", 0) or 0)
        channel = str(baseline.get("channel", txn.get("channel", "online")))
        risk_value = txn.get("risk_score")
        risk_score = _f(risk_value, 0.5) if risk_value is not None else None

        # Recurring-charge signal computed from the card's REAL history:
        # multiple prior transactions at the SAME amount (exact match) indicate
        # a regular billing cadence, not one-off fraud. Near-equal amounts are
        # coincidental in this dataset (1% tolerance matches hundreds of rows).
        is_recurring_like = False
        recurring_count = 0
        history = context.trigger_details.get("graph_transaction_history", [])
        if amount > 0 and graph_mode:
            recurring_count = sum(
                1 for row in history
                if row.get("transaction_id") != tid
                and abs(_f(row.get("amount")) - amount) <= 0.005
            )
            is_recurring_like = recurring_count >= 3
        elif amount > 0:
            hist = STORE.get_card_history(context.customer_id)
            recurring_count = sum(
                1 for r in hist
                if r.get("TransactionID") != tid
                and abs(_f(r.get("TransactionAmt")) - amount) <= 0.005
            )
            is_recurring_like = recurring_count >= 3

        # Hypothesis 1: Recurring Subscription False Alarm (Rule R7)
        # Driven by the real history (several prior charges at the same amount),
        # not a hardcoded list of subscription price points.
        if is_recurring_like:
            hypotheses.append(
                f"Transaction amount of ${amount:.2f} recurs in the cardholder's real history: "
                f"{recurring_count} prior charges at the same amount indicate a regular billing cadence "
                f"(software/gym/streaming). Cardholders frequently dispute recurring charges they forgot "
                f"to cancel, not criminal fraud."
            )
            innocent_score += 0.45
        elif graph_mode:
            mark_graph_signal_unavailable(
                context,
                "recurring_charge_history",
                "Transaction amount and history amounts are not stored in the deployed graph.",
            )

        # Hypothesis 2: Out-of-Region Holiday / Business Travel (Rule R3)
        if context.primary_pattern == "out_of_region_use" and amount <= max_amt * 1.5:
            hypotheses.append(
                f"Transaction occurred in a region with no prior history, but at ${amount:,.2f} it sits within "
                f"the cardholder's observed range (max prior ${max_amt:,.2f}) — consistent with travel rather than compromise."
            )
            innocent_score += 0.35

        # Hypothesis 3: Weak Machine Learning Model False Positive (Rule R1 / R3)
        if context.trigger_type == "risk_score" and risk_score is not None and risk_score < 0.65:
            hypotheses.append(
                f"Risk score of {risk_score:.2f} is in the weak anomaly zone (P < 0.65). "
                f"Over-reacting with card blocks will cause severe customer friction and false declines."
            )
            innocent_score += 0.40
        elif graph_mode and risk_score is None:
            mark_graph_signal_unavailable(
                context,
                "transaction_risk_score",
                "The deployed graph does not store a transaction risk-score attribute.",
            )

        # Hypothesis 4: Established Cardholder Relationship
        n_prior = int(baseline.get("n_prior", 0) or 0)
        if n_prior > 50:
            hypotheses.append(
                f"Customer {context.customer_id} has an established real track record of {n_prior} "
                f"prior transactions on this card."
            )
            innocent_score += 0.25

        innocent_score = round(min(1.0, innocent_score), 2)

        # Devil's Advocate Verdict Recommendation
        if graph_mode and (amount_value is None or risk_score is None):
            verdict = (
                "UNABLE_TO_ASSESS_FROM_GRAPH: Required transaction amount, risk score, "
                "and history attributes are unavailable in the deployed TigerGraph schema."
            )
        elif innocent_score >= 0.55:
            verdict = "CHALLENGE_FRAUD_PRESUMPTION: High probability of benign false positive or forgotten subscription."
        elif innocent_score >= 0.30:
            verdict = "REQUEST_CARDHOLDER_STEPUP: Ambiguous signals warrant step-up verification before punitive action."
        else:
            verdict = "CONCUR_WITH_FRAUD_HYPOTHESIS: Evidence of adversarial compromise (testing, ring, or proxy) is robust."

        context.innocent_explanation_score = innocent_score
        context.alternative_hypotheses = hypotheses
        context.devil_advocate_verdict = verdict

        return context
