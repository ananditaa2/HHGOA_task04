"""Deploy TigerDetect's schema, loaders, queries, and smoke tests.

The script is intentionally explicit about the two deployment phases. GSQL
files are sent to the TigerGraph admin endpoint, while CSV upload remains a
normal loading-job operation on the target graph. Use ``--dry-run`` to print
the exact commands without changing a workspace.
"""

import argparse
import csv
import os
from pathlib import Path
from typing import Iterable

import requests

ROOT = Path(__file__).resolve().parent.parent
GSQL_DIR = ROOT / "gsql"

# First case-pack row (HHG-001) — used for smoke tests so the checks exercise
# vertices that actually exist in the loaded graph.
CASE_PACK = ROOT / "case_pack.csv"


def _first_case_pack_row() -> dict:
    if CASE_PACK.exists():
        with CASE_PACK.open(encoding="utf-8", newline="") as handle:
            for row in csv.DictReader(handle):
                return row
    return {}


def _host() -> str:
    return os.getenv("TG_HOST", "http://localhost:9000").rstrip("/")


def _headers() -> dict:
    token = os.getenv("TG_API_TOKEN", "")
    return {"Content-Type": "text/plain", **({"Authorization": f"Bearer {token}"} if token else {})}


def execute_gsql(statement: str, dry_run: bool = False) -> str:
    if dry_run:
        return "DRY RUN"
    response = requests.post(f"{_host()}:14240/gsqlserver/gsql", data=statement,
                             headers=_headers(), timeout=120)
    response.raise_for_status()
    return response.text


def run_files(paths: Iterable[Path], dry_run: bool = False) -> None:
    for path in paths:
        print(f"Installing {path.name}")
        result = execute_gsql(path.read_text(encoding="utf-8"), dry_run)
        if not dry_run:
            print(result[-500:])


def smoke_test(dry_run: bool = False) -> None:
    """INTERPRET-mode runs of the installed queries against real case-pack IDs."""
    row = _first_case_pack_row()
    card_id = row.get("card_id", "C00000-K1")
    customer_id = row.get("customer_id", "C00000")
    txn_id = row.get("flagged_txn_id", "T00000")
    pattern = row.get("trigger_type", "card_not_present_fraud")
    opened_at = (row.get("opened_at", "2016-12-01T00:00:00") or "").replace(" ", "T")
    checks = (
        f'INTERPRET QUERY -GSQL query_card_testing("{card_id}", 48)',
        f'INTERPRET QUERY -GSQL query_out_of_region("{customer_id}", "{txn_id}")',
        f'INTERPRET QUERY -GSQL query_similar_closed_cases("{pattern}", "{opened_at}", 3)',
    )
    for check in checks:
        print(f"Smoke test: {check}")
        if not dry_run:
            print(execute_gsql(check)[-300:])


def stream_csv(path: Path, vertex_type: str, primary_key: str,
               fields: Iterable[object], dry_run: bool = False, batch_size: int = 500) -> int:
    """Stream selected CSV columns to REST++ in bounded batches."""
    count = 0
    batch = {}
    selected = tuple((field, field) if isinstance(field, str) else field for field in fields)
    with path.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            key = row.get(primary_key, "")
            if not key:
                continue
            batch[key] = {target: row.get(source, "") for source, target in selected}
            count += 1
            if len(batch) >= batch_size:
                _upload_batch(vertex_type, batch, dry_run)
                batch = {}
    if batch:
        _upload_batch(vertex_type, batch, dry_run)
    print(f"Streamed {count:,} {vertex_type} rows from {path.name}")
    return count


def _upload_batch(vertex_type: str, batch: dict, dry_run: bool) -> None:
    if dry_run:
        return
    response = requests.post(
        f"{_host()}:9000/graph/{os.getenv('TG_GRAPH', 'FraudGraph')}/vertices/{vertex_type}",
        json=batch, headers={**_headers(), "Content-Type": "application/json"}, timeout=120)
    response.raise_for_status()


def activate_backend() -> None:
    env_file = ROOT / ".env"
    lines = env_file.read_text(encoding="utf-8").splitlines() if env_file.exists() else []
    replaced = False
    for index, line in enumerate(lines):
        if line.startswith("GRAPH_BACKEND_MODE="):
            lines[index] = "GRAPH_BACKEND_MODE=tigergraph"
            replaced = True
    if not replaced:
        lines.append("GRAPH_BACKEND_MODE=tigergraph")
    env_file.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--data-dir", type=Path, default=ROOT)
    parser.add_argument("--stream", action="store_true", help="Stream benchmark CSV vertices through REST++")
    parser.add_argument("--activate", action="store_true", help="Persist GRAPH_BACKEND_MODE=tigergraph in .env")
    args = parser.parse_args()
    run_files((GSQL_DIR / "schema.gsql", GSQL_DIR / "load_job.gsql",
               GSQL_DIR / "fraud_queries.gsql"), args.dry_run)
    if args.stream:
        stream_csv(args.data_dir / "closed_cases_history.csv", "ClosedCase", "case_id",
                   ("opened_at", "closed_at", "outcome", "pattern", "exposure_usd", "n_txns",
                    "actions_taken", "report_filed", "analyst_notes"), args.dry_run)
        stream_csv(args.data_dir / "transactions.csv", "Transaction", "TransactionID",
                   (("ts", "ts"), ("TransactionAmt", "amount"), ("channel", "channel"),
                    ("risk_score", "risk_score"), ("ProductCD", "product_cd")), args.dry_run)
    smoke_test(args.dry_run)
    if args.activate and not args.dry_run:
        activate_backend()
    if not args.dry_run:
        print("Deployment complete. Set GRAPH_BACKEND_MODE=tigergraph to use the live adapter.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())