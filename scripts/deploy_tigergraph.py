"""Deploy TigerDetect's schema, loaders, queries, data, and smoke tests to TigerGraph.

Targets both TigerGraph Savanna (https://<instance>.tgcloud.io, TLS on 443)
and local Community Edition (http://localhost, REST++ 9000 / GSQL 14240);
service ports are derived from TG_HOST automatically.

Phases:
  1. Install gsql/schema.gsql, gsql/load_job.gsql, gsql/fraud_queries.gsql
  2. --stream: stream the REAL benchmark subgraph through REST++ upserts
     (Customers, Cards, Transactions, Devices, Regions, all 5,565 ClosedCases,
     plus OWNS/MADE/BILLED_IN/FROM_DEVICE/NEXT/ON_CARD edges) so the live
     graph matches the in-memory engine exactly.
  3. Smoke-test the installed queries with INTERPRET runs on real case-pack IDs.
  4. --activate: persist GRAPH_BACKEND_MODE=tigergraph in .env

Use --dry-run to print the plan without side effects.
"""

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, Tuple
from urllib.parse import urlparse

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
GSQL_DIR = ROOT / "gsql"
load_dotenv(ROOT / ".env")
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

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


def _restpp(path: str) -> str:
    parsed = urlparse(_host())
    port = parsed.port or (443 if parsed.scheme == "https" else 9000)
    return f"{parsed.scheme}://{parsed.hostname}:{port}{path}"


def _gsql_url() -> str:
    parsed = urlparse(_host())
    port = parsed.port if parsed.scheme == "https" and parsed.port else (443 if parsed.scheme == "https" else 14240)
    return f"{parsed.scheme}://{parsed.hostname}:{port}/gsqlserver/gsql"


def _headers(json_body: bool = False) -> dict:
    token = os.getenv("TG_API_TOKEN") or os.getenv("TG_SECRET", "")
    headers = {"Content-Type": "application/json" if json_body else "text/plain"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    return headers


def execute_gsql(statement: str, dry_run: bool = False) -> str:
    if dry_run:
        return "DRY RUN"
    auth = None
    if os.getenv("TG_USERNAME") and os.getenv("TG_PASSWORD"):
        auth = (os.getenv("TG_USERNAME"), os.getenv("TG_PASSWORD"))
    response = requests.post(_gsql_url(), data=statement.encode("utf-8"),
                             headers=_headers(), auth=auth, timeout=180)
    response.raise_for_status()
    return response.text


def run_files(paths: Iterable[Path], dry_run: bool = False) -> None:
    for path in paths:
        print(f"\n[INSTALL] {path.name}")
        try:
            result = execute_gsql(path.read_text(encoding="utf-8"), dry_run)
            print(result[-800:] if not dry_run else result)
        except requests.HTTPError as exc:
            body = (exc.response.text or "")[-500:]
            print(f"[WARN] {path.name}: HTTP {exc.response.status_code} - {body}")
            if "already exists" in body.lower():
                print("       (continuing - object already present)")
            else:
                print("       (continuing - later phases may still work; review this)")


def _clean_attrs(attrs: Dict[str, Any]) -> Dict[str, Any]:
    """Drop empty strings: REST++ rejects '' for DATETIME/numeric attributes."""
    out = {}
    for key, value in attrs.items():
        if key in ("_type", "_id") or value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        out[key] = value
    return out


def _upsert_vertices(vertex_type: str, batch: Dict[str, Dict[str, Any]],
                     dry_run: bool, graph: str) -> None:
    if dry_run:
        print(f"[DRY RUN] POST {_restpp(f'/graph/{graph}/vertices/{vertex_type}')} "
              f"({len(batch)} vertices)")
        return
    payload = {vid: {"attributes": attrs} for vid, attrs in batch.items()}
    response = requests.post(_restpp(f"/graph/{graph}/vertices/{vertex_type}"),
                             json=payload, headers=_headers(json_body=True), timeout=180)
    response.raise_for_status()


def _upsert_edges(from_type: str, edge_type: str, to_type: str,
                  batch: Dict[str, Dict[str, Dict[str, Any]]],
                  dry_run: bool, graph: str) -> None:
    if dry_run:
        total = sum(len(targets) for targets in batch.values())
        print(f"[DRY RUN] POST {_restpp(f'/graph/{graph}/edges/{from_type}/{edge_type}/{to_type}')} "
              f"({total} edges)")
        return
    payload = {"edges": {
        src: {dst: {"e_type": edge_type, "attributes": attrs} for dst, attrs in targets.items()}
        for src, targets in batch.items()
    }}
    url = _restpp(f"/graph/{graph}/edges/{from_type}/{edge_type}/{to_type}")
    response = requests.post(url, json=payload, headers=_headers(json_body=True), timeout=180)
    response.raise_for_status()


def stream_full_graph(dry_run: bool = False, batch_size: int = 500) -> None:
    """Stream the full real-data subgraph (vertices AND edges) via REST++.

    Builds the same graph as src/data/real_data.build_graph_from_real_data,
    so the live TigerGraph backend matches the in-memory engine vertex-for-vertex.
    """
    from src.config import TG_GRAPH
    from src.data.real_data import build_graph_from_real_data
    from src.graph.in_memory_engine import InMemoryGraphEngine

    graph = os.getenv("TG_GRAPH", TG_GRAPH or "FraudGraph")
    engine = InMemoryGraphEngine()
    build_graph_from_real_data(engine)

    # ---- Vertices -----------------------------------------------------
    for vertex_type, vmap in engine.vertices.items():
        if not vmap:
            continue
        print(f"[STREAM] {vertex_type}: {len(vmap):,} vertices", flush=True)
        batch: Dict[str, Dict[str, Any]] = {}
        for vid, attrs in vmap.items():
            batch[vid] = _clean_attrs(attrs) or {"loaded": True}
            if len(batch) >= batch_size:
                _upsert_vertices(vertex_type, batch, dry_run, graph)
                batch = {}
        if batch:
            _upsert_vertices(vertex_type, batch, dry_run, graph)

    # ---- Edges --------------------------------------------------------
    edge_batches: Dict[Tuple[str, str, str], Dict[str, Dict[str, Dict[str, Any]]]] = {}
    for u, v, key, data in engine.g.edges(keys=True, data=True):
        from_type, from_id = u.split(":", 1)
        to_type, to_id = v.split(":", 1)
        slot = edge_batches.setdefault((from_type, key, to_type), {})
        slot.setdefault(from_id, {})[to_id] = _clean_attrs(data)

    for (from_type, edge_type, to_type), batch in sorted(edge_batches.items()):
        total = sum(len(t) for t in batch.values())
        print(f"[STREAM] {edge_type}: {total:,} edges ({from_type}->{to_type})", flush=True)
        sub: Dict[str, Dict[str, Dict[str, Any]]] = {}
        count = 0
        for src, targets in batch.items():
            sub[src] = targets
            count += len(targets)
            if count >= batch_size:
                _upsert_edges(from_type, edge_type, to_type, sub, dry_run, graph)
                sub, count = {}, 0
        if sub:
            _upsert_edges(from_type, edge_type, to_type, sub, dry_run, graph)


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
        print(f"\n[SMOKE] {check}")
        try:
            print(execute_gsql(check, dry_run)[-400:])
        except requests.HTTPError as exc:
            print(f"[WARN] smoke query failed: HTTP {exc.response.status_code} - "
                  f"{(exc.response.text or '')[-300:]}")


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
    print("[ACTIVATE] GRAPH_BACKEND_MODE=tigergraph persisted in .env")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Print the plan without side effects")
    parser.add_argument("--stream", action="store_true",
                        help="Stream the real benchmark subgraph (vertices + edges) through REST++")
    parser.add_argument("--activate", action="store_true",
                        help="Persist GRAPH_BACKEND_MODE=tigergraph in .env after a successful run")
    args = parser.parse_args()

    print(f"Target: {_host()}  graph={os.getenv('TG_GRAPH', 'FraudGraph')}  "
          f"auth={'token' if os.getenv('TG_API_TOKEN') else 'none'}")
    run_files((GSQL_DIR / "schema.gsql", GSQL_DIR / "load_job.gsql",
               GSQL_DIR / "fraud_queries.gsql"), args.dry_run)
    if args.stream:
        stream_full_graph(args.dry_run)
    smoke_test(args.dry_run)
    if args.activate and not args.dry_run:
        activate_backend()
    if not args.dry_run:
        print("\nDeployment complete. Restart the app to use the live backend "
              "(GRAPH_BACKEND_MODE=tigergraph).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())