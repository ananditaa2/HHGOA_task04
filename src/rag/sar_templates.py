"""
FinCEN Suspicious Activity Report (SAR) Narrative Generator
Generates strict, regulatory-grade 6-12 sentence narratives answering
Who, What, When, Where, How, and Why, strictly conforming to BSA/AML compliance standards.
"""

from typing import Dict, List, Any, Optional
import datetime


class SARNarrativeGenerator:
    @staticmethod
    def generate_sar(
        case_id: str,
        customer_id: str,
        card_id: str,
        opened_at: str,
        pattern: str,
        exposure_usd: float,
        affected_txns: List[str],
        primary_device: Optional[str] = None,
        region_code: Optional[str] = None,
        connected_cards: Optional[List[str]] = None,
        is_ring: bool = False,
        force_file: Optional[bool] = None
    ) -> Dict[str, Any]:
        """
        Evaluates whether a SAR is required and produces the regulatory filing object.
        Mandatory filing criteria:
        1. Fraud exposure >= $1,000.00 USD
        2. Multi-card syndicate / device ring detected (>= 3 cards)
        3. Complex coordinated account takeover or synthetic identity pattern
        """
        should_file = False
        reason = ""

        if force_file is not None:
            should_file = force_file
            reason = "Regulatory threshold triggered by compliance rules." if should_file else ""
        elif exposure_usd >= 1000.0:
            should_file = True
            reason = f"Aggregated fraudulent exposure of ${exposure_usd:,.2f} USD exceeds the $1,000.00 regulatory threshold."
        elif is_ring or (connected_cards and len(connected_cards) >= 3):
            should_file = True
            reason = f"Organized multi-card fraud syndicate identified via shared device fingerprint {primary_device or 'D-SHARED'} spanning {len(connected_cards or [])} payment cards."
        elif "takeover" in pattern.lower() and exposure_usd >= 500.0:
            should_file = True
            reason = "Account takeover with credential and device spoofing exceeding high-sensitivity risk baseline."

        if not should_file:
            return {
                "file": False,
                "reason": None,
                "narrative": None,
                "jurisdiction": None,
                "filing_deadline_days": None
            }

        # ---------------------------------------------------------------------
        # Construct Regulatory 6-12 Sentence Narrative (Who, What, When, Where, How, Why)
        # ---------------------------------------------------------------------
        txn_count = len(affected_txns)
        txn_list_str = ", ".join(affected_txns[:5])
        if txn_count > 5:
            txn_list_str += f", and {txn_count - 5} additional authorizations"

        device_desc = f"device hardware signature {primary_device}" if primary_device else "an anomalous untrusted device"
        region_desc = f"billing region {region_code}" if region_code else "an unverified remote jurisdiction"

        ring_clause = ""
        if connected_cards and len(connected_cards) >= 2:
            ring_clause = (
                f" Graph analytics revealed that the underlying device fingerprint was concurrently "
                f"associated with {len(connected_cards)} distinct customer payment cards ({', '.join(connected_cards[:4])}), "
                f"demonstrating an organized, coordinated card-compromise ring."
            )

        narrative = (
            f"This Suspicious Activity Report is filed by the Fraud Intelligence and Anti-Money Laundering unit regarding suspected unauthorized financial activity linked to Customer {customer_id} and Card {card_id}. "
            f"The suspicious activity was initially flagged on {opened_at} following automated graph anomaly detection and behavioral rule triggers. "
            f"A total of {txn_count} fraudulent or disputed transaction authorizations totaling ${exposure_usd:,.2f} USD were identified, including transaction references: {txn_list_str}. "
            f"The illicit transactions were executed across digital card-not-present payment channels routed through {region_desc} utilizing {device_desc}.{ring_clause} "
            f"The modus operandi reflects sophisticated {pattern.replace('_', ' ')} characterized by rapid-fire settlement velocity, evasion of standard velocity caps, and deliberate merchant category dispersion. "
            f"The institution initiated immediate containment protocols, placing administrative holds on the affected accounts and preventing additional financial loss. "
            f"Investigation corroborated that the legitimate account holder did not authorize these transactions, confirming criminal exploitation. "
            f"All relevant transaction logs, graph topological neighborhoods, device signatures, and IP routing artifacts have been preserved in institution archives for law enforcement review. "
            f"The filing institution requests regulatory oversight and will cooperate fully with relevant criminal investigative bodies pursuant to the Bank Secrecy Act."
        )

        return {
            "file": True,
            "reason": reason,
            "narrative": narrative,
            "jurisdiction": "FinCEN (US)",
            "filing_deadline_days": 30
        }
