"""
Policy Graph Traverser (Strategic Innovation 1: Policy Rules as a Graph)
Represents bank fraud rules R1 through R10 as vertices with OVERRIDES and ESCALATES_TO edges,
dynamically traversing the graph to determine next-best actions and approval routes.
"""

from typing import Dict, List, Any, Optional, Set, Tuple
import networkx as nx


class PolicyGraphEngine:
    def __init__(self):
        self.g = nx.DiGraph()
        self._init_policy_graph()

    def _init_policy_graph(self):
        # ---------------------------------------------------------------------
        # PolicyRule Vertices (R1 through R10)
        # ---------------------------------------------------------------------
        rules = [
            {
                "id": "R1",
                "name": "Weak Signal Verification",
                "action": "VERIFY_WITH_CUSTOMER",
                "default_route": "auto",
                "min_fraud_prob": 0.40,
                "max_fraud_prob": 0.69,
                "priority": 1,
                "description": "Risk score anomaly with low-to-medium probability requires step-up verification before punitive action."
            },
            {
                "id": "R2",
                "name": "Customer Denial Immediate Action",
                "action": "BLOCK_CARD",
                "default_route": "L1",
                "min_fraud_prob": 0.70,
                "max_fraud_prob": 1.00,
                "priority": 10,
                "description": "Cardholder disputes transaction or explicitly denies authorizing charge. Immediate containment required."
            },
            {
                "id": "R3",
                "name": "Benign Authorization Clearance",
                "action": "CLOSE_NO_FRAUD",
                "default_route": "auto",
                "min_fraud_prob": 0.00,
                "max_fraud_prob": 0.35,
                "priority": 9,
                "description": "Customer confirms travel / purchase or Devil's Advocate establishes legitimate explanation. Dismiss alert."
            },
            {
                "id": "R4",
                "name": "Rapid Burst Spending Mitigation",
                "action": "DECLINE_TRANSACTION",
                "default_route": "L1",
                "min_fraud_prob": 0.70,
                "max_fraud_prob": 0.85,
                "priority": 6,
                "description": "Multiple transactions across distinct merchants within rapid window. Decline pending transactions."
            },
            {
                "id": "R5",
                "name": "Micro-Authorization Testing Cascade",
                "action": "BLOCK_CARD",
                "default_route": "L1",
                "min_fraud_prob": 0.75,
                "max_fraud_prob": 0.95,
                "priority": 8,
                "description": "Micro-authorizations (<$5.00) followed by high-value spike. Indicates automated bot testing."
            },
            {
                "id": "R6",
                "name": "Device Ring Network Compromise",
                "action": "MONITOR_CONNECTED_CARDS",
                "default_route": "L2",
                "min_fraud_prob": 0.80,
                "max_fraud_prob": 1.00,
                "priority": 9,
                "description": "Multiple cards sharing a single device profile. Multi-card syndicate detected."
            },
            {
                "id": "R7",
                "name": "Recurring Subscription False Alarm",
                "action": "WARN_CUSTOMER",
                "default_route": "auto",
                "min_fraud_prob": 0.20,
                "max_fraud_prob": 0.60,
                "priority": 7,
                "description": "Dispute matches monthly recurring billing interval (gym, software, streaming). Do not block card."
            },
            {
                "id": "R8",
                "name": "High Exposure Evidence Conflict",
                "action": "ESCALATE_TO_ANALYST",
                "default_route": "L1",
                "min_fraud_prob": 0.40,
                "max_fraud_prob": 0.90,
                "priority": 8,
                "description": "Evidence conflict score >= 0.40. Unresolved tension between risk score and historical baseline."
            },
            {
                "id": "R9",
                "name": "Regulatory SAR Mandatory Escalation",
                "action": "FILE_REPORT",
                "default_route": "L2",
                "min_fraud_prob": 0.75,
                "max_fraud_prob": 1.00,
                "priority": 10,
                "description": "Exposure > $1,000, multi-card ring, or undocumented syndicate pattern requires FinCEN SAR filing."
            },
            {
                "id": "R10",
                "name": "Second-Line Senior Review",
                "action": "ANALYST_CONFIRMATION",
                "default_route": "L2",
                "min_fraud_prob": 0.85,
                "max_fraud_prob": 1.00,
                "priority": 5,
                "description": "High consequence multi-action plan requires Level 2 supervisor sign-off."
            }
        ]

        for r in rules:
            self.g.add_node(r["id"], **r)

        # ---------------------------------------------------------------------
        # Innovation 1: Dynamic OVERRIDES Edges
        # ---------------------------------------------------------------------
        # R2 (Customer Denial) OVERRIDES R1 (Weak Verify)
        self.g.add_edge("R2", "R1", edge_type="OVERRIDES", condition="customer_denial_confirmed")
        # R3 (Benign Clearance) OVERRIDES R1 (Weak Verify)
        self.g.add_edge("R3", "R1", edge_type="OVERRIDES", condition="customer_confirmed_authorized")
        # R7 (Recurring Pattern) OVERRIDES R2 (Dispute Block)
        self.g.add_edge("R7", "R2", edge_type="OVERRIDES", condition="recurring_pattern_identified")
        # R9 (SAR) OVERRIDES auto closure when exposure high
        self.g.add_edge("R9", "R3", edge_type="OVERRIDES", condition="exposure_exceeds_1000")

        # ---------------------------------------------------------------------
        # Dynamic ESCALATES_TO Edges
        # ---------------------------------------------------------------------
        # R8 (Conflict) ESCALATES_TO L1/L2
        self.g.add_edge("R8", "R10", edge_type="ESCALATES_TO", escalation_reason="evidence_discordance")
        # R6 (Device Ring) ESCALATES_TO R9 (SAR)
        self.g.add_edge("R6", "R9", edge_type="ESCALATES_TO", escalation_reason="syndicate_detected")

    def evaluate_policy(
        self,
        fraud_probability: float,
        conflict_score: float,
        exposure_usd: float,
        trigger_type: str,
        customer_response: Optional[str] = None,
        is_recurring: bool = False,
        is_card_testing: bool = False,
        ring_detected: bool = False,
        is_out_of_region: bool = False
    ) -> Dict[str, Any]:
        """
        Traverses the PolicyRule graph to produce optimal recommendations and approval routes.
        """
        candidate_rules: Set[str] = set()

        # Step 1: Baseline candidate rules by probability and trigger
        for node, data in self.g.nodes(data=True):
            min_p = data.get("min_fraud_prob", 0.0)
            max_p = data.get("max_fraud_prob", 1.0)
            if min_p <= fraud_probability <= max_p:
                candidate_rules.add(node)

        # Trigger-specific additions
        if trigger_type == "risk_score" and fraud_probability < 0.70:
            candidate_rules.add("R1")
        if trigger_type == "customer_report":
            candidate_rules.add("R2")
        if is_recurring:
            candidate_rules.add("R7")
        if is_card_testing:
            candidate_rules.add("R5")
        if ring_detected:
            candidate_rules.add("R6")
        if conflict_score >= 0.40:
            candidate_rules.add("R8")
        if exposure_usd >= 1000.0 or ring_detected:
            candidate_rules.add("R9")
        if customer_response == "confirmed_authorized":
            candidate_rules.add("R3")
        elif customer_response == "denied_transaction":
            candidate_rules.add("R2")

        # Step 2: Traverse OVERRIDES edges
        active_rules = set(candidate_rules)
        overridden_log: List[str] = []

        for u, v, data in self.g.edges(data=True):
            if data.get("edge_type") == "OVERRIDES":
                if u in active_rules and v in active_rules:
                    # Check conditions
                    cond = data.get("condition")
                    apply_override = False
                    if cond == "customer_denial_confirmed" and customer_response == "denied_transaction":
                        apply_override = True
                    elif cond == "customer_confirmed_authorized" and (customer_response == "confirmed_authorized" or fraud_probability <= 0.35):
                        apply_override = True
                    elif cond == "recurring_pattern_identified" and is_recurring:
                        apply_override = True
                    elif cond == "exposure_exceeds_1000" and exposure_usd >= 1000.0:
                        apply_override = False  # SAR does not prevent benign closure if truly benign

                    if apply_override:
                        active_rules.discard(v)
                        overridden_log.append(f"Rule {u} OVERRIDES Rule {v} ({cond})")

        # Step 3: Determine primary actions and route
        actions: List[Dict[str, Any]] = []
        highest_route = "auto"
        route_hierarchy = {"auto": 1, "L1": 2, "L2": 3}

        # Priority sort
        sorted_active = sorted(
            list(active_rules), 
            key=lambda r: self.g.nodes[r].get("priority", 0), 
            reverse=True
        )

        for r_id in sorted_active:
            r_data = self.g.nodes[r_id]
            route = r_data.get("default_route", "auto")
            action_code = r_data.get("action")
            
            # Map action to standardized submission actions
            actions.append({
                "action": action_code,
                "rule_id": r_id,
                "rule_name": r_data.get("name"),
                "approval_route": route
            })

            if route_hierarchy.get(route, 1) > route_hierarchy.get(highest_route, 1):
                highest_route = route

        return {
            "active_rules": sorted_active,
            "overridden_rules": overridden_log,
            "actions": actions,
            "primary_route": highest_route,
            "candidate_count": len(candidate_rules)
        }
