"""
Investigation Progression Timeline Component
Visualizes the multi-stage agentic workflow: Intake -> Graph Detective -> Conflict -> Evidence Step-up -> Final Action.
"""

from typing import Dict, List, Any
import streamlit.components.v1 as components


def render_timeline(case_data: Dict[str, Any], height: int = 440):
    case_inner = case_data.get("case", {})
    nba        = case_data.get("next_best_actions", {})
    inits      = nba.get("initial", [])
    finals     = nba.get("final", [])
    ev_reqs    = case_data.get("evidence_requests", [])

    inits_str  = ", ".join([f"{a['action']} ({a['route']})" for a in inits])  or "None"
    finals_str = ", ".join([f"{a['action']} ({a['route']})" for a in finals]) or "None"
    ev_msg     = ev_reqs[0].get("assumed_response", "No step-up required.") if ev_reqs else "No step-up required."
    changed    = nba.get("what_changed", "")
    stop       = case_data.get("stop_reason", "")

    trigger_type = case_data.get("trigger_type") or ""
    flagged_id   = case_inner.get("affected_txn_ids", [""])[0] if case_inner.get("affected_txn_ids") else case_data.get("case_id", "")
    pattern      = case_inner.get("pattern", "none")
    exposure     = case_inner.get("exposure_usd", 0.0)
    n_affected   = len(case_inner.get("affected_txn_ids", []))
    verdict      = case_inner.get("verdict", "uncertain")

    html_content = f"""
    <div style="background: #051A0E; border: 2px solid #FEE101; border-radius: 12px; padding: 20px; box-shadow: 0 0 20px rgba(254, 225, 1, 0.15); color: #F8F9FA; font-family: 'Inter', sans-serif;">
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 14px; font-weight: 800; color: #FEE101; text-transform: uppercase; letter-spacing: 0.5px; margin-bottom: 16px; border-bottom: 1px solid rgba(254,225,1,0.25); padding-bottom: 8px;">
            ⏱️ AGENTIC INVESTIGATION TIMELINE & PROGRESSION
        </div>

        <div style="position: relative; padding-left: 26px; border-left: 2px dashed rgba(254,225,1,0.4); margin-left: 10px;">
            <!-- Stage 1 -->
            <div style="position: relative; margin-bottom: 18px;">
                <div style="position: absolute; left: -34px; top: 1px; width: 15px; height: 15px; border-radius: 50%; background: #FEE101; box-shadow: 0 0 8px #FEE101;"></div>
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; color: #FEE101; font-weight: 800; font-size: 12.5px; text-transform: uppercase;">1. ALERT TRIGGER INTAKE</div>
                <div style="font-size: 13px; color: #F8F9FA; margin-top: 3px; line-height: 1.5;">
                    Trigger: <span style="color: #FF0080; font-weight: 700;">{trigger_type.upper() or 'UNKNOWN'}</span>
                    &nbsp;|&nbsp; Flagged Txn: <b style="font-family: 'JetBrains Mono'; color: #00FFA3;">{flagged_id}</b>
                    &nbsp;|&nbsp; Verdict: <span style="color: #FEE101;">{verdict.upper()}</span>
                </div>
            </div>

            <!-- Stage 2 -->
            <div style="position: relative; margin-bottom: 18px;">
                <div style="position: absolute; left: -34px; top: 1px; width: 15px; height: 15px; border-radius: 50%; background: #00FFA3; box-shadow: 0 0 8px #00FFA3;"></div>
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; color: #00FFA3; font-weight: 800; font-size: 12.5px; text-transform: uppercase;">2. MULTI-HOP GRAPH TRAVERSAL & ANOMALY SCAN</div>
                <div style="font-size: 13px; color: #F8F9FA; margin-top: 3px; line-height: 1.5;">
                    Pattern: <span style="color: #FEE101; font-weight: 700;">{pattern.upper().replace('_',' ')}</span>
                    &nbsp;|&nbsp; Affected Txns: <b>{n_affected}</b>
                    &nbsp;|&nbsp; Exposure: <span style="color: #00FFA3; font-weight: 700;">${exposure:,.2f} USD</span>
                </div>
            </div>

            <!-- Stage 3 -->
            <div style="position: relative; margin-bottom: 18px;">
                <div style="position: absolute; left: -34px; top: 1px; width: 15px; height: 15px; border-radius: 50%; background: #FF0080; box-shadow: 0 0 8px #FF0080;"></div>
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; color: #FF0080; font-weight: 800; font-size: 12.5px; text-transform: uppercase;">3. INITIAL ACTIONS & STEP-UP EVIDENCE REQUEST</div>
                <div style="font-size: 13px; color: #F8F9FA; margin-top: 3px; line-height: 1.5;">
                    Initial Recommendations: <span style="color: #FEE101; font-weight: 600;">{inits_str}</span>
                </div>
            </div>

            <!-- Stage 4 -->
            <div style="position: relative; margin-bottom: 18px;">
                <div style="position: absolute; left: -34px; top: 1px; width: 15px; height: 15px; border-radius: 50%; background: #00E5FF; box-shadow: 0 0 8px #00E5FF;"></div>
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; color: #00E5FF; font-weight: 800; font-size: 12.5px; text-transform: uppercase;">4. EVIDENCE CORROBORATION & SIMULATION</div>
                <div style="font-size: 13px; color: #F8F9FA; margin-top: 3px; line-height: 1.5;">
                    Response Signal: <i>"{ev_msg}"</i>
                </div>
            </div>

            <!-- Stage 5 -->
            <div style="position: relative;">
                <div style="position: absolute; left: -34px; top: 1px; width: 15px; height: 15px; border-radius: 50%; background: #00FFA3; box-shadow: 0 0 8px #00FFA3;"></div>
                <div style="font-family: 'Plus Jakarta Sans', sans-serif; color: #00FFA3; font-weight: 800; font-size: 12.5px; text-transform: uppercase;">5. FINAL NEXT-BEST ACTIONS & SAR FILING</div>
                <div style="font-size: 13px; color: #F8F9FA; margin-top: 3px; line-height: 1.5;">
                    Final Plan: <span style="color: #00FFA3; font-weight: 700;">{finals_str}</span>
                </div>
            </div>
        </div>
    </div>
    """
    components.html(html_content, height=height)
