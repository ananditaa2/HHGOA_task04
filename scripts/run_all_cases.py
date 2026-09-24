"""
Batch Runner for the 20 Case-Pack Investigations (README (2).md pipeline)
Loads the four provided CSV files as the single source of truth
(case_pack.csv, transactions.csv, identity.csv, closed_cases_history.csv),
runs the multi-agent pipeline over all 20 cases, validates every output
against the README answer format, and writes cases/HHG-001.json .. HHG-020.json.
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

from src.config import CASES_DIR
from src.data.real_data import STORE, build_graph_from_real_data
from src.graph.graph_adapter import GraphAdapter
from src.agents.coordinator import InvestigationCoordinator
from src.utils.schema_validator import CaseSchemaValidator
from src.utils.metrics import calculate_case_pack_metrics


def run_all(output_dir: Path = CASES_DIR):
    print("=" * 70)
    print("[GOA] TIGERDETECT: 20-CASE BATCH RUNNER — REAL CSV DATA [GOA]")
    print("=" * 70)

    # 1. Graph engine populated purely from the provided CSV files
    adapter = GraphAdapter()
    build_graph_from_real_data(adapter.in_memory)
    print("[OK] Graph built from case_pack.csv + transactions.csv + identity.csv "
          "+ closed_cases_history.csv (no seed data).")

    # 2. Coordinator
    coordinator = InvestigationCoordinator(graph_adapter=adapter)
    print("[OK] Multi-Agent Coordinator online.")

    results = []
    validation_failures = 0

    # 3. Process each real case-pack row
    case_pack = STORE.get_case_pack()
    for i, case_spec in enumerate(case_pack, 1):
        cid = case_spec["case_id"]
        print(f"\n[{i:02d}/{len(case_pack)}] {cid} ({case_spec['trigger_type']})... ", end="", flush=True)

        result = coordinator.investigate(case_spec)

        valid, errors = CaseSchemaValidator.validate_case(result)
        if not valid:
            print("[SCHEMA ERRORS]")
            for err in errors:
                print(f"    - {err}")
            validation_failures += 1
        else:
            c = result["case"]
            sar_flag = "SAR" if result["sar"]["file"] else "no-sar"
            print(f"[OK] {c['verdict']} (p={c['fraud_probability']:.2f}, "
                  f"{c['pattern']}, ${c['exposure_usd']:,.2f}, {sar_flag})")

        with open(output_dir / f"{cid}.json", "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        results.append(result)

    print("\n" + "=" * 70)
    print("INVESTIGATION RUN SUMMARY (README answer format)")
    print("=" * 70)
    m = calculate_case_pack_metrics(results)
    print(f"Cases processed            : {m['total_cases']}")
    print(f"Fraud verdicts             : {m['fraud_cases']}")
    print(f"Legitimate verdicts        : {m['legitimate_cases']}")
    print(f"SARs filed                 : {m['sar_filings']}")
    print(f"Total exposure handled     : ${m['total_exposure_usd']:,.2f}")
    print(f"Initial -> final evolution : {m['evolution_count']}/{m['total_cases']}")
    print(f"Rules triggered            : {', '.join(m['rules_triggered'])}")
    print(f"Schema validation failures : {validation_failures}")
    print("=" * 70)

    if validation_failures == 0:
        print("[SUCCESS] ALL 20 CASE FILES GENERATED AND VALIDATED (README format).")
    else:
        print(f"[WARN] {validation_failures} case files have schema defects. Review above.")

    return results


if __name__ == "__main__":
    run_all()
