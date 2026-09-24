"""
Standalone Submission Validation Script
Quick-run validator verifying that all 20 required submission files exist and conform to schema.
"""

import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from scripts.qa_audit import audit_case_pack

if __name__ == "__main__":
    success = audit_case_pack()
    if success:
        print("\n[OK] Submission package is 100% valid and ready for submission.")
        sys.exit(0)
    else:
        print("\n[ERROR] Submission package has validation failures.")
        sys.exit(1)
