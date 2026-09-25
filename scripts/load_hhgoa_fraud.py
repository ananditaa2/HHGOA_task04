"""Load the real project CSV data into the existing HHGOA_Fraud graph.

This loader is intentionally limited to the target-specific subset documented
in the command-line help. It performs no schema operations.
"""

from __future__ import annotations

import argparse
import csv
import itertools
import json
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, Iterator, List, Optional, Set, Tuple
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv


ROOT = Path(__file__).resolve().parent.parent
TARGET_GRAPH = "HHGOA_Fraud"
DEFAULT_BATCH_SIZE = 100
MAX_RETRIES = 3
RETRYABLE_STATUS_CODES = {408, 429, 499, 500, 502, 503, 504}


@dataclass
class ScanStats:
    customers: Set[str] = field(default_factory=set)
    transactions: Set[str] = field(default_factory=set)
    cases: Set[str] = field(default_factory=set)
    customer_risk: Dict[str, float] = field(default_factory=dict)
    duplicate_customer_ids: Set[str] = field(default_factory=set)
    duplicate_transaction_ids: Set[str] = field(default_factory=set)
    duplicate_case_ids: Set[str] = field(default_factory=set)
    missing_customer_ids: int = 0
    missing_transaction_ids: int = 0
    missing_case_ids: int = 0
    missing_transaction_timestamps: int = 0
    missing_transaction_amounts: int = 0
    missing_case_customers: int = 0
    missing_case_ids_in_records: int = 0
    initiated_edges: int = 0
    involved_edges: int = 0
    skipped_accounts: int = 0
    skipped_merchants: int = 0
    transaction_rows: int = 0
    current_case_ids: Set[str] = field(default_factory=set)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="scan and report only; perform no TigerGraph writes",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=DEFAULT_BATCH_SIZE,
        help=f"upsert batch size (default: {DEFAULT_BATCH_SIZE})",
    )
    parser.add_argument(
        "--write-limit",
        type=int,
        default=None,
        help="limit each transaction and case source stream during writes only",
    )
    parser.add_argument(
        "--checkpoint-file",
        type=Path,
        default=ROOT / ".hhgoa_fraud_loader_checkpoint.json",
        help="path for resumable batch progress",
    )
    return parser.parse_args()


def require_configuration(require_secret: bool) -> Tuple[str, str]:
    load_dotenv(ROOT / ".env")
    graph = os.getenv("TG_GRAPHNAME", "")
    if graph != TARGET_GRAPH:
        raise RuntimeError(
            f"Refusing to run: TG_GRAPHNAME must be {TARGET_GRAPH!r}, got {graph or '<unset>':!r}."
        )
    host = os.getenv("TG_HOST", "").rstrip("/")
    secret = os.getenv("TG_SECRET", "")
    if not host:
        raise RuntimeError("TG_HOST is required.")
    if require_secret and not secret:
        raise RuntimeError("TG_SECRET is required for TigerGraph writes.")
    parsed = urlparse(host)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise RuntimeError("TG_HOST must be an http(s) URL.")
    return host, secret


def csv_path(name: str) -> Path:
    path = ROOT / name
    if not path.is_file():
        raise FileNotFoundError(f"Required source file not found: {path}")
    return path


def valid_float(value: str) -> Optional[float]:
    try:
        if not value.strip():
            return None
        return float(value)
    except (AttributeError, TypeError, ValueError):
        return None


def nonempty(value: Optional[str]) -> Optional[str]:
    value = (value or "").strip()
    return value or None


def restpp_base(host: str) -> str:
    parsed = urlparse(host)
    if parsed.port:
        return host
    return f"{host}:{443 if parsed.scheme == 'https' else 9000}"


def clean_attributes(attributes: Dict[str, Any]) -> Dict[str, Any]:
    return {
        key: value
        for key, value in attributes.items()
        if value is not None and value != ""
    }


def iter_case_records(stats: ScanStats) -> Iterator[Tuple[str, Dict[str, str]]]:
    """Yield current cases first, then historical cases without ID collisions."""
    current_path = csv_path("case_pack.csv")
    historical_path = csv_path("closed_cases_history.csv")

    with current_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            case_id = nonempty(row.get("case_id"))
            customer_id = nonempty(row.get("customer_id"))
            if not case_id:
                stats.missing_case_ids_in_records += 1
                continue
            stats.current_case_ids.add(case_id)
            yield "current", row

    with historical_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            case_id = nonempty(row.get("case_id"))
            if not case_id:
                stats.missing_case_ids_in_records += 1
                continue
            if case_id in stats.current_case_ids:
                stats.duplicate_case_ids.add(case_id)
                continue
            yield "historical", row


def scan_sources() -> ScanStats:
    stats = ScanStats()

    case_pack_path = csv_path("case_pack.csv")
    with case_pack_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            customer_id = nonempty(row.get("customer_id"))
            case_id = nonempty(row.get("case_id"))
            if customer_id:
                risk = valid_float(row.get("risk_score", ""))
                if risk is not None:
                    stats.customer_risk[customer_id] = risk
            else:
                stats.missing_case_customers += 1
            if not case_id:
                stats.missing_case_ids_in_records += 1

    transaction_path = csv_path("transactions.csv")
    with transaction_path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            stats.transaction_rows += 1
            customer_id = nonempty(row.get("customer_id"))
            transaction_id = nonempty(row.get("TransactionID"))
            if customer_id:
                if customer_id in stats.customers:
                    stats.duplicate_customer_ids.add(customer_id)
                stats.customers.add(customer_id)
            else:
                stats.missing_customer_ids += 1
            if not transaction_id:
                stats.missing_transaction_ids += 1
                continue
            if transaction_id in stats.transactions:
                stats.duplicate_transaction_ids.add(transaction_id)
                continue
            stats.transactions.add(transaction_id)
            if not nonempty(row.get("ts")):
                stats.missing_transaction_timestamps += 1
            if valid_float(row.get("TransactionAmt", "")) is None:
                stats.missing_transaction_amounts += 1

    for source_kind, row in iter_case_records(stats):
        case_id = nonempty(row.get("case_id"))
        customer_id = nonempty(row.get("customer_id"))
        if customer_id:
            stats.customers.add(customer_id)
        else:
            stats.missing_case_customers += 1
        if not case_id:
            continue
        if case_id in stats.cases:
            stats.duplicate_case_ids.add(case_id)
            continue
        stats.cases.add(case_id)
        stats.involved_edges += int(bool(customer_id))

    stats.initiated_edges = sum(
        1 for _ in iter_unique_transaction_rows()
        if nonempty(_.get("customer_id")) and nonempty(_.get("TransactionID"))
    )
    stats.skipped_accounts = 0
    stats.skipped_merchants = 0
    return stats


def iter_unique_transaction_rows() -> Iterator[Dict[str, str]]:
    seen: Set[str] = set()
    with csv_path("transactions.csv").open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            transaction_id = nonempty(row.get("TransactionID"))
            if not transaction_id or transaction_id in seen:
                continue
            seen.add(transaction_id)
            yield row


def report(stats: ScanStats) -> None:
    print("HHGOA_Fraud loader scan")
    print(f"Unique Customer count: {len(stats.customers):,}")
    print(f"Transaction count: {len(stats.transactions):,}")
    print(f"FraudCase count: {len(stats.cases):,}")
    print(f"INITIATED edge count: {stats.initiated_edges:,}")
    print(f"INVOLVED_IN edge count: {stats.involved_edges:,}")
    print(f"Missing customer IDs: {stats.missing_customer_ids:,}")
    print(f"Missing transaction IDs: {stats.missing_transaction_ids:,}")
    print(f"Missing case IDs: {stats.missing_case_ids_in_records:,}")
    print(f"Duplicate customer IDs: {len(stats.duplicate_customer_ids):,}")
    print(f"Duplicate transaction IDs: {len(stats.duplicate_transaction_ids):,}")
    print(f"Duplicate case IDs: {len(stats.duplicate_case_ids):,}")
    print(f"Missing transaction timestamps: {stats.missing_transaction_timestamps:,}")
    print(f"Missing transaction amounts: {stats.missing_transaction_amounts:,}")
    print(f"Case records missing customer_id: {stats.missing_case_customers:,}")
    print("Skipped Account records: 0 (no source account identifier exists)")
    print("Skipped Merchant records: 0 (no source merchant identifier exists)")


class RestppLoader:
    def __init__(self, host: str, secret: str, batch_size: int):
        self.base = restpp_base(host)
        self.headers = {
            "Authorization": f"GSQL-Secret {secret}",
            "Content-Type": "application/json",
        }
        self.batch_size = batch_size
        self.failures = 0

    def _post(
        self,
        payload: Dict[str, Any],
        stage: str,
        batch_number: int,
        records: int,
    ) -> None:
        started = time.monotonic()
        attempted = 0
        for retry in range(MAX_RETRIES + 1):
            attempted += 1
            try:
                response = requests.post(
                    f"{self.base}/restpp/graph/{TARGET_GRAPH}",
                    json=payload,
                    headers=self.headers,
                    timeout=180,
                )
                response.raise_for_status()
                record_kind = "vertices" if "vertices" in payload else "edges"
                failure = restpp_response_error(response, records, record_kind)
                if failure:
                    secret = self.headers["Authorization"].partition(" ")[2]
                    if secret:
                        failure = failure.replace(secret, "[REDACTED]")
                    raise requests.HTTPError(failure, response=response)
                elapsed = time.monotonic() - started
                print(
                    f"stage={stage} batch={batch_number} records_attempted={records} "
                    f"records_successfully_submitted={records} failures=0 "
                    f"retries={attempted - 1} elapsed={elapsed:.2f}s"
                )
                return
            except requests.RequestException as exc:
                status_code = getattr(getattr(exc, "response", None), "status_code", None)
                retryable = (
                    status_code in RETRYABLE_STATUS_CODES
                    or isinstance(exc, (requests.ConnectionError, requests.Timeout))
                )
                if not retryable or retry >= MAX_RETRIES:
                    self.failures += 1
                    elapsed = time.monotonic() - started
                    print(
                        f"stage={stage} batch={batch_number} records_attempted={records} "
                        f"records_successfully_submitted=0 failures=1 "
                        f"retries={attempted - 1} elapsed={elapsed:.2f}s"
                    )
                    raise LoaderStageError(stage, batch_number, attempted, exc) from exc
                delay = 2 ** retry
                print(
                    f"stage={stage} batch={batch_number} transient_http={status_code or 'connection'} "
                    f"retry={retry + 1}/{MAX_RETRIES} backoff={delay}s"
                )
                time.sleep(delay)

    def post_vertices(
        self,
        vertex_type: str,
        batch: Dict[str, Dict[str, Any]],
        stage: str,
        batch_number: int,
    ) -> None:
        if not batch:
            return
        payload = {
            "vertices": {
                vertex_type: {
                    vertex_id: {
                        attribute: {"value": value}
                        for attribute, value in attributes.items()
                    }
                    for vertex_id, attributes in batch.items()
                }
            }
        }
        self._post(payload, stage, batch_number, len(batch))

    def post_edges(
        self,
        from_type: str,
        edge_type: str,
        to_type: str,
        batch: Dict[str, Dict[str, Dict[str, Any]]],
        stage: str,
        batch_number: int,
    ) -> None:
        if not batch:
            return
        payload = {
            "edges": {
                from_type: {
                    source: {
                        edge_type: {
                            to_type: {
                                target: {
                                    attribute: {"value": value}
                                    for attribute, value in attrs.items()
                                }
                                for target, attrs in targets.items()
                            }
                        }
                    }
                    for source, targets in batch.items()
                }
            }
        }
        self._post(
            payload,
            stage,
            batch_number,
            sum(len(targets) for targets in batch.values()),
        )


def restpp_response_error(
    response: requests.Response,
    expected_records: Optional[int] = None,
    record_kind: Optional[str] = None,
) -> Optional[str]:
    try:
        body = response.json()
    except ValueError:
        return None
    if not isinstance(body, dict):
        return None
    errors: List[str] = []
    if body.get("error") is True:
        errors.append(str(body.get("message") or "RESTPP returned error=true"))
    results = body.get("results")
    if isinstance(results, list):
        for result in results:
            if isinstance(result, dict) and result.get("error"):
                errors.append(str(result.get("message") or result["error"]))
            if isinstance(result, dict) and expected_records is not None:
                suffix = "vertices" if record_kind == "vertices" else "edges"
                accepted = result.get(f"accepted_{suffix}")
                affected = result.get(f"affected_{suffix}")
                if isinstance(accepted, int) and isinstance(affected, int):
                    submitted = accepted + affected
                elif isinstance(accepted, int):
                    submitted = accepted
                else:
                    continue
                if submitted < expected_records:
                    details = {
                        key: result.get(key)
                        for key in (
                            "accepted_vertices",
                            "affected_vertices",
                            "accepted_edges",
                            "affected_edges",
                            "error",
                            "code",
                            "message",
                        )
                        if key in result
                    }
                    errors.append(
                        f"RESTPP accepted/affected {submitted} {suffix}; "
                        f"expected {expected_records}; details={details}"
                    )
    return "; ".join(errors) or None


class LoaderStageError(RuntimeError):
    def __init__(self, stage: str, batch_number: int, attempts: int, cause: Exception):
        self.stage = stage
        self.batch_number = batch_number
        self.attempts = attempts
        super().__init__(
            f"Stage {stage!r} batch {batch_number} failed after {attempts} request(s): {cause}"
        )


class ProgressCheckpoint:
    def __init__(self, path: Path, signature: Dict[str, Any]):
        self.path = path
        self.signature = signature
        self.completed: Dict[str, int] = {}
        if path.exists():
            with path.open(encoding="utf-8") as handle:
                saved = json.load(handle)
            if saved.get("signature") == signature and not saved.get("complete", False):
                self.completed = {
                    stage: int(batch) for stage, batch in saved.get("completed", {}).items()
                }
                print(f"Resuming from checkpoint: {path}")
            else:
                print("Checkpoint does not match this load scope; starting a fresh run.")

    def is_completed(self, stage: str, batch_number: int) -> bool:
        return batch_number <= self.completed.get(stage, 0)

    def mark_completed(self, stage: str, batch_number: int) -> None:
        self.completed[stage] = batch_number
        self._save(complete=False)

    def mark_load_complete(self) -> None:
        self._save(complete=True)

    def _save(self, complete: bool) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        contents = {
            "signature": self.signature,
            "completed": self.completed,
            "complete": complete,
        }
        descriptor, temporary_path = tempfile.mkstemp(
            prefix=f"{self.path.name}.", suffix=".tmp", dir=self.path.parent
        )
        try:
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(contents, handle, sort_keys=True)
                handle.flush()
                os.fsync(handle.fileno())
            for attempt in range(4):
                try:
                    os.replace(temporary_path, self.path)
                    break
                except PermissionError:
                    if attempt == 3:
                        raise
                    time.sleep(0.1 * (2 ** attempt))
        except Exception:
            if os.path.exists(temporary_path):
                os.unlink(temporary_path)
            raise


def chunks(items: Iterable[Tuple[str, Dict[str, Any]]], size: int) -> Iterator[List[Tuple[str, Dict[str, Any]]]]:
    batch: List[Tuple[str, Dict[str, Any]]] = []
    for item in items:
        batch.append(item)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def load_data(
    loader: RestppLoader,
    write_limit: Optional[int] = None,
    checkpoint: Optional[ProgressCheckpoint] = None,
) -> None:
    checkpoint = checkpoint or ProgressCheckpoint(
        ROOT / ".hhgoa_fraud_loader_checkpoint.json",
        checkpoint_signature(write_limit, loader.batch_size),
    )
    transaction_rows = iter_unique_transaction_rows()
    if write_limit is not None:
        transaction_rows = itertools.islice(transaction_rows, write_limit)

    customer_ids: Set[str] = set()
    for row in transaction_rows:
        customer_id = nonempty(row.get("customer_id"))
        if customer_id:
            customer_ids.add(customer_id)
    transaction_rows = iter_unique_transaction_rows()
    case_rows = iter_case_records(ScanStats())
    if write_limit is not None:
        transaction_rows = itertools.islice(transaction_rows, write_limit)
        case_rows = itertools.islice(case_rows, write_limit)
    for _, row in case_rows:
        customer_id = nonempty(row.get("customer_id"))
        if customer_id:
            customer_ids.add(customer_id)

    _run_vertex_stage(
        loader,
        checkpoint,
        "vertices:Customer",
        (
            (
                customer_id,
                {"customer_id": customer_id},
            )
            for customer_id in sorted(customer_ids)
        ),
    )

    transaction_vertex_records = (
        (
            transaction_id,
            clean_attributes(
                {
                    "transaction_id": transaction_id,
                }
            ),
        )
        for row in (
            itertools.islice(iter_unique_transaction_rows(), write_limit)
            if write_limit is not None
            else iter_unique_transaction_rows()
        )
        if (transaction_id := nonempty(row.get("TransactionID")))
    )
    _run_vertex_stage(
        loader, checkpoint, "vertices:Transaction", transaction_vertex_records
    )

    seen_case_ids: Set[str] = set()
    case_rows = iter_case_records(ScanStats())
    if write_limit is not None:
        case_rows = itertools.islice(case_rows, write_limit)
    def case_vertex_records() -> Iterator[Tuple[str, Dict[str, Any]]]:
        for _, row in case_rows:
            case_id = nonempty(row.get("case_id"))
            if not case_id or case_id in seen_case_ids:
                continue
            seen_case_ids.add(case_id)
            yield case_id, clean_attributes(
                {
                    "case_id": case_id,
                }
            )

    _run_vertex_stage(loader, checkpoint, "vertices:FraudCase", case_vertex_records())

    def initiated_records() -> Iterator[Tuple[str, Dict[str, Any]]]:
        transaction_rows = iter_unique_transaction_rows()
        if write_limit is not None:
            transaction_rows = itertools.islice(transaction_rows, write_limit)
        for row in transaction_rows:
            customer_id = nonempty(row.get("customer_id"))
            transaction_id = nonempty(row.get("TransactionID"))
            if customer_id and transaction_id:
                yield customer_id, {
                    "target_id": transaction_id,
                    "attributes": {},
                }

    _run_edge_stage(
        loader,
        checkpoint,
        "edges:Customer-INITIATED-Transaction",
        "INITIATED",
        "Transaction",
        initiated_records(),
    )

    def involved_records() -> Iterator[Tuple[str, Dict[str, Any]]]:
        seen_case_ids: Set[str] = set()
        case_rows = iter_case_records(ScanStats())
        if write_limit is not None:
            case_rows = itertools.islice(case_rows, write_limit)
        for _, row in case_rows:
            case_id = nonempty(row.get("case_id"))
            customer_id = nonempty(row.get("customer_id"))
            if not case_id or not customer_id or case_id in seen_case_ids:
                continue
            seen_case_ids.add(case_id)
            yield customer_id, {
                "target_id": case_id,
                "attributes": {},
            }

    _run_edge_stage(
        loader,
        checkpoint,
        "edges:Customer-INVOLVED_IN-FraudCase",
        "INVOLVED_IN",
        "FraudCase",
        involved_records(),
    )
    checkpoint.mark_load_complete()


def checkpoint_signature(write_limit: Optional[int], batch_size: int) -> Dict[str, Any]:
    source_files = ("transactions.csv", "case_pack.csv", "closed_cases_history.csv")
    return {
        "graph": TARGET_GRAPH,
        "write_limit": write_limit,
        "batch_size": batch_size,
        "sources": {
            name: {"size": csv_path(name).stat().st_size, "mtime_ns": csv_path(name).stat().st_mtime_ns}
            for name in source_files
        },
    }


def _run_vertex_stage(
    loader: RestppLoader,
    checkpoint: ProgressCheckpoint,
    stage: str,
    records: Iterable[Tuple[str, Dict[str, Any]]],
) -> None:
    for batch_number, batch in enumerate(chunks(records, loader.batch_size), start=1):
        if checkpoint.is_completed(stage, batch_number):
            print(
                f"stage={stage} batch={batch_number} records_attempted=0 "
                "records_successfully_submitted=0 failures=0 elapsed=0.00s checkpoint=skipped"
            )
            continue
        loader.post_vertices(stage.split(":", 1)[1], dict(batch), stage, batch_number)
        checkpoint.mark_completed(stage, batch_number)


def _run_edge_stage(
    loader: RestppLoader,
    checkpoint: ProgressCheckpoint,
    stage: str,
    edge_type: str,
    target_type: str,
    records: Iterable[Tuple[str, Dict[str, Any]]],
) -> None:
    for batch_number, batch in enumerate(chunks(records, loader.batch_size), start=1):
        if checkpoint.is_completed(stage, batch_number):
            print(
                f"stage={stage} batch={batch_number} records_attempted=0 "
                "records_successfully_submitted=0 failures=0 elapsed=0.00s checkpoint=skipped"
            )
            continue
        edges: Dict[str, Dict[str, Dict[str, Any]]] = {}
        for source, record in batch:
            edges.setdefault(source, {})[record["target_id"]] = record["attributes"]
        loader.post_edges(
            "Customer", edge_type, target_type, edges, stage, batch_number
        )
        checkpoint.mark_completed(stage, batch_number)


def main() -> int:
    args = parse_args()
    if args.batch_size <= 0:
        raise SystemExit("--batch-size must be greater than zero.")
    if args.write_limit is not None and args.write_limit <= 0:
        raise SystemExit("--write-limit must be greater than zero.")
    try:
        host, secret = require_configuration(require_secret=not args.dry_run)
        stats = scan_sources()
        report(stats)
        if args.dry_run:
            print("Dry run complete; no TigerGraph writes performed.")
            return 0
        load_data(
            RestppLoader(host, secret, args.batch_size),
            args.write_limit,
            ProgressCheckpoint(
                args.checkpoint_file,
                checkpoint_signature(args.write_limit, args.batch_size),
            ),
        )
        print("TigerGraph upserts completed.")
        return 0
    except (FileNotFoundError, RuntimeError, requests.RequestException, OSError, ValueError) as exc:
        print(f"Loader failed safely: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
