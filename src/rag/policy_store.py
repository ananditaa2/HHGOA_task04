"""
Bank Fraud Policy Knowledge Store (v1.0)
Standardized next-best action taxonomy and organizational approval routes.
"""

from typing import Dict, List, Any

# Valid standardized actions — the exact identifiers from README (2).md Fraud Policy §1
VALID_ACTIONS = {
    "ALLOW_TRANSACTION": "Let the flagged transaction stand.",
    "DECLINE_TRANSACTION": "Decline the flagged authorization only. Card stays active.",
    "MONITOR_CARD": "Card stays active; raise monitoring sensitivity for 72 hours.",
    "MONITOR_CONNECTED_CARDS": "Put other cards linked to the same device profile, region cluster, or ring under monitoring.",
    "WARN_CUSTOMER": "Send an informational message (e.g. a recurring charge reminder, a security tip).",
    "VERIFY_WITH_CUSTOMER": "Ask the cardholder whether they made the transaction. Card stays active pending reply.",
    "STEP_UP_AUTH": "Require a one-time passcode or app confirmation before further activity.",
    "BLOCK_CARD": "Block this card and reissue.",
    "BLOCK_ALL_CARDS": "Block every card the customer holds.",
    "GENERATE_REPORT": "Write up the investigation for the internal record, without opening a case.",
    "CREATE_CASE": "Open an internal fraud case with the evidence attached, and write it to the graph.",
    "FILE_REPORT": "File a suspicious activity report with the regulator.",
    "ESCALATE_TO_ANALYST": "Hand the case to a human analyst with the evidence.",
    "CLOSE_NO_FRAUD": "Close the alert as legitimate."
}

# Approval routes — README (2).md Fraud Policy §2
APPROVAL_ROUTES = {
    "auto": "Agent may act alone",
    "L1": "Team lead approval required",
    "L2": "Fraud manager approval required"
}

# Detailed Fraud Policy Handbook
POLICY_HANDBOOK = {
    "R1": {
        "title": "Weak Anomaly Verification",
        "description": "Risk score anomaly under 0.70 with no prior complaints must initiate customer contact prior to adverse actions.",
        "actions": ["VERIFY_WITH_CUSTOMER"],
        "route": "auto"
    },
    "R2": {
        "title": "Confirmed Cardholder Dispute Containment",
        "description": "Direct customer denial or unauthorized report requires immediate card block and case creation.",
        "actions": ["BLOCK_CARD", "CREATE_CASE"],
        "route": "L1"
    },
    "R3": {
        "title": "Legitimate Transaction Clearance",
        "description": "When customer validates transaction or travel is verified, alert must be closed with no adverse impact.",
        "actions": ["CLOSE_NO_FRAUD"],
        "route": "auto"
    },
    "R4": {
        "title": "Rapid Merchant Velocity Mitigation",
        "description": "High frequency cross-merchant transaction burst within 1 hour triggers selective transaction decline.",
        "actions": ["DECLINE_TRANSACTION", "MONITOR_CARD"],
        "route": "L1"
    },
    "R5": {
        "title": "Automated Testing Micro-Auth Protection",
        "description": "Preceding sequence of sub-$5 authorizations followed by high-dollar spend indicates card testing bot. Block card immediately.",
        "actions": ["BLOCK_CARD", "CREATE_CASE"],
        "route": "L1"
    },
    "R6": {
        "title": "Device Fingerprint Multi-Card Compromise",
        "description": "Device profile linked to >= 3 distinct cards requires ring monitoring, case creation, and supervisory escalation.",
        "actions": ["MONITOR_CONNECTED_CARDS", "CREATE_CASE"],
        "route": "L2"
    },
    "R7": {
        "title": "Recurring Subscription Dispute Protection",
        "description": "Dispute on recurring merchant with monthly cadence requires customer education / warning rather than card cancellation.",
        "actions": ["CREATE_CASE", "VERIFY_WITH_CUSTOMER", "WARN_CUSTOMER"],
        "route": "auto"
    },
    "R8": {
        "title": "Unresolved Signal Discordance Escalation",
        "description": "When quantitative Evidence Conflict Score >= 0.40, escalate directly to human analyst with signal breakdown.",
        "actions": ["CREATE_CASE"],
        "route": "L1"
    },
    "R9": {
        "title": "FinCEN Regulatory Reporting Threshold",
        "description": "Aggregate fraud exposure > $1,000, multi-card syndicate, or undocumented modus operandi mandates filing FinCEN SAR.",
        "actions": ["FILE_REPORT"],
        "route": "L2"
    },
    "R10": {
        "title": "Supervisory Second-Line Concurrence",
        "description": "High consequence multi-action execution plans require Level 2 supervisor sign-off before settlement.",
        "actions": [],
        "route": "L2"
    }
}
