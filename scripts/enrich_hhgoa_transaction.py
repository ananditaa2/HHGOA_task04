"""Enrich one source-backed transaction in the deployed HHGOA_Fraud graph.

The script reads only the requested transaction and its matching identity row.
It upserts the existing Transaction and Customer vertices/INITIATED edge, plus
the case and customer-case link found in case_pack.csv. It never loads a full
transaction dataset or infers account, merchant, or device identifiers.
"""

from __future__ import annotations

import argparse
import csv
import os
from pathlib import Path
from typing import Any, Dict, Optional
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
GRAPH = "HHGOA_Fraud"


def nonempty(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    return value or None


def find_row(path: Path, key: str, value: str) -> Optional[Dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get(key) == value:
                return row
    return None


def transaction_attributes(
    transaction: Dict[str, str], identity: Optional[Dict[str, str]]
) -> Dict[str, Any]:
    """Map explicit source fields to the approved Transaction attributes."""
    attributes: Dict[str, Any] = {
        "transaction_id": nonempty(transaction.get("TransactionID")),
        "amount": float(transaction["TransactionAmt"]),
        "ts": nonempty(transaction.get("ts")),
        "risk_score": float(transaction["risk_score"]),
        "channel": nonempty(transaction.get("channel")),
        "product_cd": nonempty(transaction.get("ProductCD")),
    }
    if identity:
        attributes.update(
            {
                "device_type": nonempty(identity.get("DeviceType")),
                "device_info": nonempty(identity.get("DeviceInfo")),
                "id_15": nonempty(identity.get("id_15")),
                "id_28": nonempty(identity.get("id_28")),
                "id_31": nonempty(identity.get("id_31")),
            }
        )
    return {key: value for key, value in attributes.items() if value is not None}


def find_case(case_id: str) -> Optional[Dict[str, str]]:
    with (ROOT / "case_pack.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            if row.get("case_id") == case_id:
                return row
    return None


def restpp_base(host: str) -> str:
    parsed = urlparse(host)
    if not parsed.scheme or not parsed.hostname:
        raise ValueError("TG_HOST must be a valid http(s) URL")
    if parsed.port:
        return host.rstrip("/")
    port = 443 if parsed.scheme == "https" else 9000
    return f"{host.rstrip('/')}:{port}"


class RestppWriter:
    def __init__(self, host: str, secret: str) -> None:
        self.base = restpp_base(host)
        self.headers = {
            "Authorization": f"GSQL-Secret {secret}",
            "Content-Type": "application/json",
        }

    def upsert(self, payload: Dict[str, Any]) -> None:
        response = requests.post(
            f"{self.base}/restpp/graph/{GRAPH}",
            json=payload,
            headers=self.headers,
            timeout=60,
        )
        response.raise_for_status()
        body = response.json()
        if body.get("error"):
            raise RuntimeError(body.get("message", "TigerGraph RESTPP upsert failed"))
        for result in body.get("results", []):
            if isinstance(result, dict) and result.get("error"):
                raise RuntimeError(result.get("message", "TigerGraph RESTPP upsert failed"))


def vertex_payload(vertex_type: str, vertex_id: str, attrs: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "vertices": {
            vertex_type: {
                vertex_id: {
                    name: {"value": value} for name, value in attrs.items()
                }
            }
        }
    }


def edge_payload(
    from_type: str,
    from_id: str,
    edge_type: str,
    to_type: str,
    to_id: str,
) -> Dict[str, Any]:
    return {
        "edges": {
            from_type: {
                from_id: {
                    edge_type: {to_type: {to_id: {}}}
                }
            }
        }
    }


def enrich(
    transaction_id: str, writer: RestppWriter, case_id: Optional[str] = None
) -> Dict[str, Any]:
    transaction = find_row(ROOT / "transactions.csv", "TransactionID", transaction_id)
    if not transaction:
        raise ValueError(f"TransactionID {transaction_id!r} was not found in transactions.csv")
    customer_id = nonempty(transaction.get("customer_id"))
    if not customer_id:
        raise ValueError(f"TransactionID {transaction_id!r} has no customer_id")
    identity = find_row(ROOT / "identity.csv", "TransactionID", transaction_id)
    attrs = transaction_attributes(transaction, identity)

    writer.upsert(vertex_payload("Transaction", transaction_id, attrs))
    writer.upsert(
        edge_payload("Customer", customer_id, "INITIATED", "Transaction", transaction_id)
    )

    case = find_case(case_id) if case_id else None
    if case:
        case_id = nonempty(case.get("case_id"))
        case_customer = nonempty(case.get("customer_id"))
        if case_customer != customer_id:
            raise ValueError(
                f"Case {case_id!r} belongs to {case_customer!r}, not transaction customer {customer_id!r}"
            )
        if case_id and case_customer:
            writer.upsert(vertex_payload("FraudCase", case_id, {"case_id": case_id}))
            writer.upsert(
                edge_payload("Customer", case_customer, "INVOLVED_IN", "FraudCase", case_id)
            )
    return {
        "transaction_id": transaction_id,
        "customer_id": customer_id,
        "attributes_written": sorted(attrs),
        "case_id_linked": case.get("case_id") if case else None,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transaction-id", required=True)
    parser.add_argument(
        "--case-id",
        help="optionally link the customer's source case through Customer; no direct case-transaction link is created",
    )
    args = parser.parse_args()
    load_dotenv(ROOT / ".env")
    graph = os.getenv("TG_GRAPHNAME", "")
    if graph != GRAPH:
        raise SystemExit(f"Refusing to run: TG_GRAPHNAME must be {GRAPH!r}.")
    host, secret = os.getenv("TG_HOST", ""), os.getenv("TG_SECRET", "")
    if not host or not secret:
        raise SystemExit("TG_HOST and TG_SECRET are required.")
    try:
        result = enrich(args.transaction_id, RestppWriter(host, secret), args.case_id)
    except (OSError, ValueError, requests.RequestException, RuntimeError) as exc:
        raise SystemExit(f"Enrichment failed: {exc}") from exc
    print(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
