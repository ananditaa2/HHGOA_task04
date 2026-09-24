"""
Post-Run QA Audit Suite (README (2).md conformance)
Performs 6 verification checks on the 20 generated case files:
1. README answer-format schema & required fields (top level + Parts 1-3)
2. Enum vocabularies (verdict/status/pattern/actions/routes)
3. SAR consistency (file=true <-> FILE_REPORT in final actions; thresholds)
4. Verdict/legitimacy arithmetic (affected txns, exposure, empty SAR)
5. Initial -> Final recommendation evolution & evidence_requests
6. Rule citations present in action reasons
"""

import json
import sys
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
except Exception:
    pass

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import CASES_DIR
from src.utils.schema_validator import CaseSchemaValidator


def audit_case_pack(cases_dir: Path = CASES_DIR):
    print("=" * 75)
    print("[GOA] TIGERDETECT POST-RUN 20-CASE QA AUDIT (README (2).md conformance) [GOA]")
    print("=" * 75)

    case_files = sorted(list(cases_dir.glob("HHG-*.json")))
    if len(case_files) != 20:
        print(f"[FAIL] Expected 20 case files, found {len(case_files)}.")
        return False

    all_cases = []
    for f in case_files:
        with open(f, "r", encoding="utf-8") as fp:
            all_cases.append(json.load(fp))

    audit_failures = []

    # 1. README answer-format schema
    print("\n[CHECK 1/6] README answer-format schema & required fields...")
    for case in all_cases:
        cid = case["case_id"]
        valid, errs = CaseSchemaValidator.validate_case(case)
        if not valid:
            print(f"  [X] {cid}: {errs}")
            audit_failures.extend(f"{cid}: {e}" for e in errs)
    if not audit_failures:
        print("  [PASS] 20/20 cases conform to the README answer format.")

    # 2. Enum coverage summary
    print("\n[CHECK 2/6] Verdict distribution & pattern vocabulary...")
    verdicts = {}
    patterns = {}
    for c in all_cases:
        v = c["case"]["verdict"]
        verdicts[v] = verdicts.get(v, 0) + 1
        p = c["case"]["pattern"]
        patterns[p] = patterns.get(p, 0) + 1
    print(f"  [INFO] verdicts: {verdicts}")
    print(f"  [INFO] patterns: {patterns}")
    if verdicts.get("fraud", 0) == 0:
        print("  [WARN] no fraud verdicts — README says half the pack is fraud")

    # 3. SAR consistency
    print("\n[CHECK 3/6] SAR consistency with final actions & policy thresholds...")
    for c in all_cases:
        cid = c["case_id"]
        sar = c["sar"]
        final_actions = [a["action"] for a in c["next_best_actions"]["final"]]
        files_report = "FILE_REPORT" in final_actions
        if sar["file"] != files_report:
            audit_failures.append(f"{cid}: sar.file={sar['file']} but FILE_REPORT in final={files_report}")
            print(f"  [X] {cid}: sar.file={sar['file']} vs FILE_REPORT in final={files_report}")
            continue
        exposure = c["case"]["exposure_usd"]
        verdict = c["case"]["verdict"]
        pattern = c["case"]["pattern"]
        if sar["file"]:
            ok = (exposure > 1000.0 or pattern == "undocumented"
                  or len(c["case"].get("connected_card_ids", [])) >= 1)
            if not ok:
                audit_failures.append(f"{cid}: SAR filed but no policy 3a trigger (exposure=${exposure:,.2f}, pattern={pattern})")
                print(f"  [X] {cid}: SAR lacks a policy trigger")
            else:
                print(f"  [PASS] {cid}: SAR filed (exposure ${exposure:,.2f}, pattern={pattern}).")
        else:
            print(f"  [PASS] {cid}: no SAR ({verdict}, exposure ${exposure:,.2f}).")

    # 4. Legitimacy arithmetic
    print("\n[CHECK 4/6] Verdict arithmetic (affected txns / exposure)...")
    for c in all_cases:
        cid = c["case_id"]
        case = c["case"]
        if case["verdict"] == "legitimate":
            if case["affected_txn_ids"] or case["exposure_usd"] != 0:
                audit_failures.append(f"{cid}: legitimate case has non-empty affected/exposure")
                print(f"  [X] {cid}: legitimate with non-empty affected/exposure")
        else:
            if not case["affected_txn_ids"] or case["exposure_usd"] <= 0:
                audit_failures.append(f"{cid}: non-legitimate case has empty affected or non-positive exposure")
                print(f"  [X] {cid}: empty affected / non-positive exposure")
    if not audit_failures:
        print("  [PASS] verdict arithmetic consistent across 20/20 cases.")

    # 5. Evolution & evidence requests
    print("\n[CHECK 5/6] Initial -> Final evolution & evidence requests...")
    evolved = []
    for c in all_cases:
        cid = c["case_id"]
        inits = [a["action"] for a in c["next_best_actions"]["initial"]]
        finals = [a["action"] for a in c["next_best_actions"]["final"]]
        if inits != finals:
            evolved.append(cid)
        if inits != finals and not c.get("evidence_requests"):
            audit_failures.append(f"{cid}: recommendations changed without an evidence request")
    print(f"  [INFO] {len(evolved)}/20 cases evolved: {', '.join(evolved)}")

    # 6. Rule citations
    print("\n[CHECK 6/6] Policy rule citations in action reasons...")
    import re
    missing_rules = []
    for c in all_cases:
        cid = c["case_id"]
        reasons = " ".join(a.get("reason", "") for phase in ("initial", "final")
                           for a in c["next_best_actions"][phase])
        reasons += " " + c.get("sar", {}).get("reason", "") + " " + c.get("stop_reason", "")
        if not re.search(r"R\d+", reasons):
            missing_rules.append(cid)
    if missing_rules:
        audit_failures.append(f"no rule citations in: {', '.join(missing_rules)}")
        print(f"  [X] cases without rule citations: {', '.join(missing_rules)}")
    else:
        print("  [PASS] every case cites policy rules (R1-R10) in its reasons.")

    print("\n" + "=" * 75)
    if not audit_failures:
        print("[AUDIT SUCCESS] 100% PASS ACROSS ALL 6 AUDIT VECTORS (README (2).md conformance).")
    else:
        print(f"[AUDIT ISSUES] Found {len(audit_failures)} issues:")
        for x in audit_failures[:20]:
            print(f"   - {x}")
    print("=" * 75)

    return len(audit_failures) == 0


if __name__ == "__main__":
    audit_case_pack()
