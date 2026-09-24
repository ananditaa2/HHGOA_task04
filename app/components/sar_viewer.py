"""
FinCEN SAR Report Viewer Component
Displays regulatory Suspicious Activity Reports (SARs) with narrative viewer and copy utility.
"""

from typing import Dict, List, Any
import streamlit as st


def render_sar_view(case_data: Dict[str, Any]):
    sar = case_data.get("sar", {})
    is_filed = sar.get("file", False)
    cid = case_data.get("case_id", "HHG-001")

    st.markdown("""
        <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-size: 15px; color: #FEE101; margin-bottom: 10px; font-weight: 800; text-transform: uppercase;">
            📋 REGULATORY COMPLIANCE: FINCEN SUSPICIOUS ACTIVITY REPORT (SAR)
        </div>
    """, unsafe_allow_html=True)

    if not is_filed:
        st.markdown("""
            <div style="background: #051A0E; border: 1.5px solid rgba(254, 225, 1, 0.3); border-radius: 8px; padding: 16px; color: #F8F9FA; font-family: 'Inter', sans-serif; font-size: 13.5px; line-height: 1.6;">
                <span style="color: #00FFA3; font-weight: 700;">[NO SAR REQUIRED]</span> This case does not cross the $1,000 regulatory filing threshold, nor does it involve a multi-card device syndicate or organized structuring ring.
            </div>
        """, unsafe_allow_html=True)
        return

    reason = sar.get("reason", "")
    narrative = sar.get("narrative", "")
    jurisdiction = sar.get("jurisdiction", "FinCEN (US)")
    deadline = sar.get("filing_deadline_days", 30)

    st.markdown(f"""
        <div style="background: #051A0E; border: 2px solid #FF0080; border-radius: 10px; padding: 18px; margin-bottom: 16px; box-shadow: 0 0 24px rgba(255, 0, 128, 0.25); font-family: 'Inter', sans-serif;">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px; border-bottom: 1px solid rgba(255, 0, 128, 0.35); padding-bottom: 10px;">
                <span style="color: #FF0080; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 14px;">🚨 MANDATORY BSA/AML FILING ACTIVE</span>
                <span style="background: #FF0080; color: #FFFFFF; font-family: 'Plus Jakarta Sans', sans-serif; font-size: 11px; padding: 3px 10px; border-radius: 4px; font-weight: 800;">{jurisdiction}</span>
            </div>
            
            <div style="font-size: 13.5px; color: #F8F9FA; margin-bottom: 10px; line-height: 1.5;">
                <span style="color: #FEE101; font-weight: 700;">TRIGGER REASON:</span> {reason}
            </div>

            <div style="display: flex; gap: 24px; font-size: 13px; color: #FEE101; margin-bottom: 14px;">
                <div><span>Filing Deadline:</span> <span style="color: #FFF; font-weight: 700;">{deadline} Days</span></div>
                <div><span>Review Tier:</span> <span style="color: #FF0080; font-weight: 700;">Level 2 Senior Officer</span></div>
            </div>

            <div style="background: #000000; border: 1px solid rgba(254, 225, 1, 0.35); border-radius: 8px; padding: 16px; font-size: 13.5px; line-height: 1.7; color: #F8F9FA; max-height: 240px; overflow-y: auto;">
                <div style="color: #FEE101; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; margin-bottom: 8px; border-bottom: 1px dashed rgba(254, 225, 1, 0.25); padding-bottom: 6px; font-size: 13px;">
                    FINCEN FORM 111 - SECTION V SUSPICIOUS ACTIVITY NARRATIVE:
                </div>
                {narrative}
            </div>
        </div>
    """, unsafe_allow_html=True)
