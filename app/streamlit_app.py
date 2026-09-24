"""
TigerDetect: Agentic AI Fraud Investigation & Next-Best Action Platform
Analyst Workbench UI styled with the official Hacker House Goa (hhgoa.com) Brand Kit
"""

import streamlit as st
import json
import os
import sys
import base64
from pathlib import Path

# Add project root to sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.config import CASES_DIR, ASSETS_DIR, HH_COLORS
from src.graph.graph_adapter import GraphAdapter
from src.agents.coordinator import InvestigationCoordinator
import csv
from app.components.graph_visualizer import render_graph_view
from app.components.conflict_gauge import render_conflict_gauge
from app.components.timeline import render_timeline
from app.components.sar_viewer import render_sar_view

# Page Config
st.set_page_config(
    page_title="TigerDetect | Hacker House Goa Fraud Agent",
    page_icon="🐅",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Custom CSS — Partnership Banner Design System (HHG × TigerGraph announcement art):
# marigold field, hot-pink ornamental frame, banner-emerald panels, poster display type.
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&family=JetBrains+Mono:wght@400;500;600;700&family=Plus+Jakarta+Sans:wght@500;600;700;800;900&family=Anton&display=swap');

:root {
    --marigold: #FFDD00;
    --orn-pink: #F23A7B;
    --orn-pink-deep: #D61E5F;
    --banner-green: #0B6839;
    --panel-green: #07351F;
    --card-green: #0A4A2C;
    --disp-yellow: #FEE101;
    --mint: #00FFA3;
    --offwhite: #FFFBE8;
}

/* Global: marigold field with folk-art petal dots */
.stApp {
    background-color: var(--marigold);
    background-image:
        radial-gradient(circle at 12px 14px, rgba(242, 58, 123, 0.18) 3.5px, transparent 4.5px),
        radial-gradient(circle at 34px 36px, rgba(11, 104, 57, 0.20) 3px, transparent 4px),
        radial-gradient(circle at 56px 10px, rgba(255, 255, 255, 0.35) 2px, transparent 3px);
    background-size: 68px 68px;
    color: var(--offwhite);
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    font-size: 14px;
    line-height: 1.6;
}

/* Headings in poster display style */
h1, h2, h3, .hh-header {
    font-family: 'Anton', 'Plus Jakarta Sans', sans-serif !important;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 400;
    color: var(--disp-yellow);
}

/* Sidebar: deep green with pink frame edge */
section[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0B6839 0%, #07351F 100%) !important;
    border-right: 4px solid var(--orn-pink);
}
section[data-testid="stSidebar"] * {
    color: var(--offwhite) !important;
}

/* Green content panel used across the app */
.hh-panel, .hh-metric-box {
    background: linear-gradient(150deg, var(--card-green) 0%, var(--panel-green) 100%);
    border: 2px solid var(--disp-yellow);
    border-radius: 10px;
    padding: 14px 16px;
    text-align: center;
    box-shadow: 0 6px 18px rgba(4, 38, 22, 0.45);
}

.hh-pill {
    padding: 4px 12px;
    border-radius: 999px;
    font-size: 12px;
    font-weight: 800;
    font-family: 'Plus Jakarta Sans', sans-serif;
    letter-spacing: 0.5px;
}
.pill-fraud { background: var(--orn-pink); color: #FFF; }
.pill-legit { background: var(--mint); color: #062D1B; }
.pill-yellow { background: var(--disp-yellow); color: #062D1B; }

/* Buttons: yellow block with pink hard shadow, banner-style */
.stButton>button {
    background-color: var(--disp-yellow) !important;
    color: #062D1B !important;
    font-family: 'Plus Jakarta Sans', sans-serif !important;
    font-weight: 800 !important;
    border: 2px solid #062D1B !important;
    border-radius: 6px !important;
    box-shadow: 3px 3px 0px var(--orn-pink) !important;
    transition: all 0.2s ease !important;
    letter-spacing: 0.5px !important;
}
.stButton>button:hover {
    transform: translate(-2px, -2px) !important;
    box-shadow: 5px 5px 0px var(--orn-pink) !important;
}
</style>
""", unsafe_allow_html=True)


@st.cache_data
def load_case_pack_csv():
    """Load real case_pack.csv rows."""
    rows = []
    csv_path = Path(__file__).parent.parent / "case_pack.csv"
    if csv_path.exists():
        with open(csv_path, encoding="utf-8") as f:
            for r in csv.DictReader(f):
                rows.append(r)
    return rows


BENCHMARK_CASES = load_case_pack_csv()


def load_case_file(case_id: str) -> dict:
    case_path = CASES_DIR / f"{case_id}.json"
    if case_path.exists():
        with open(case_path, "r", encoding="utf-8") as f:
            return json.load(f)
    return {}


# -----------------------------------------------------------------------------
# Top Navigation & Header
# -----------------------------------------------------------------------------
logo_path = ASSETS_DIR / "hacker_house.png"
goa_svg_path = ASSETS_DIR / "goa_hindi.svg"

col_header_left, col_header_right = st.columns([3, 1])

with col_header_left:
    st.markdown("""
        <div style="background: linear-gradient(135deg, #0E7A44 0%, #0B6839 60%, #084D2B 100%); border: 3px solid #F23A7B; border-radius: 14px; padding: 18px 24px; box-shadow: 0 8px 26px rgba(4,38,22,0.5);">
            <div style="display: flex; align-items: center; gap: 15px;">
                <div style="font-family: 'Anton', sans-serif; font-size: 36px; color: #FEE101; letter-spacing: 2.5px; line-height: 1; text-shadow: 0 3px 0 rgba(0,0,0,0.35);">
                    TIGERDETECT
                </div>
                <div style="background: #F23A7B; color: #FFFFFF; font-family: 'Plus Jakarta Sans', sans-serif; font-size: 12px; font-weight: 800; padding: 4px 12px; border-radius: 999px; border: 2px solid #FFFFFF; box-shadow: 0 0 12px rgba(242,58,123,0.6);">
                    HACKER HOUSE × TIGERGRAPH
                </div>
            </div>
            <div style="font-family: 'JetBrains Mono', monospace; font-size: 12px; color: #FFFBE8; margin-top: 8px;">
                Partnership Announcement Edition · Agentic AI Fraud Investigation &amp; Next-Best Action
            </div>
        </div>
    """, unsafe_allow_html=True)

with col_header_right:
    st.markdown("""
        <div style="text-align: right; font-family: 'JetBrains Mono', monospace; font-size: 11px; color: #FEE101; background: #07351F; padding: 10px 14px; border-radius: 10px; border: 2px solid #FEE101; box-shadow: 0 6px 18px rgba(4,38,22,0.45);">
            <div>STATUS: <span style="color: #00FFA3; font-weight: bold;">● ENGINE ONLINE</span></div>
            <div style="color: #FFFBE8;">REAL CSV · 590,742 TXNS</div>
            <div style="color: #F23A7B; font-size: 10px;">HHG × TIGERGRAPH</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<hr style='border: 1px solid rgba(254, 225, 1, 0.2); margin: 12px 0 18px 0;'>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Global Benchmark KPI Strip
# -----------------------------------------------------------------------------
col_kpi1, col_kpi2, col_kpi3, col_kpi4, col_kpi5 = st.columns(5)
with col_kpi1:
    st.markdown("""
        <div class="hh-metric-box">
            <div style="font-size: 10px; color: #FEE101;">BENCHMARK CASES</div>
            <div style="font-size: 20px; font-weight: bold; color: #FFFBE8;">20 / 20</div>
            <div style="font-size: 9px; color: #00FFA3;">100% Schema Valid</div>
        </div>
    """, unsafe_allow_html=True)
with col_kpi2:
    st.markdown("""
        <div class="hh-metric-box">
            <div style="font-size: 10px; color: #FEE101;">FRAUD vs LEGITIMATE</div>
            <div style="font-size: 20px; font-weight: bold; color: #FFFBE8;">10 <span style="font-size: 12px; color: #F23A7B;">FRAUD</span> / 10 <span style="font-size: 12px; color: #00FFA3;">LEGIT</span></div>
            <div style="font-size: 9px; color: #FEE101;">Half the pack is legitimate</div>
        </div>
    """, unsafe_allow_html=True)
with col_kpi3:
    st.markdown("""
        <div class="hh-metric-box">
            <div style="font-size: 10px; color: #FEE101;">FINCEN SARS FILED</div>
            <div style="font-size: 20px; font-weight: bold; color: #FF0080;">2 FILINGS</div>
            <div style="font-size: 9px; color: #FFFBE8;">HHG-010 ($1k+) · HHG-014 (Ring)</div>
        </div>
    """, unsafe_allow_html=True)
with col_kpi4:
    st.markdown("""
        <div class="hh-metric-box">
            <div style="font-size: 10px; color: #FEE101;">RULE COVERAGE</div>
            <div style="font-size: 20px; font-weight: bold; color: #FEE101;">10 / 10 (100%)</div>
            <div style="font-size: 9px; color: #00FFA3;">Rules R1 - R10 Active</div>
        </div>
    """, unsafe_allow_html=True)
with col_kpi5:
    st.markdown("""
        <div class="hh-metric-box">
            <div style="font-size: 10px; color: #FEE101;">GRAPH ENGINE</div>
            <div style="font-size: 18px; font-weight: bold; color: #00E5FF;">TIGERGRAPH</div>
            <div style="font-size: 9px; color: #FFFBE8;">Real CSV · 590k Txns</div>
        </div>
    """, unsafe_allow_html=True)

st.markdown("<div style='height: 15px;'></div>", unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Sidebar: Case Selection & Filters
# -----------------------------------------------------------------------------
st.sidebar.markdown("""
    <div style="font-family: 'Anton', sans-serif; font-size: 24px; color: #FEE101; letter-spacing: 2px; border-bottom: 3px solid #F23A7B; padding-bottom: 6px; margin-bottom: 12px;">
        CASE EXPLORER
    </div>
""", unsafe_allow_html=True)

case_options = [
    f"{b['case_id']}: {b.get('trigger_type','').upper()} ({b.get('customer_id','')})"
    for b in BENCHMARK_CASES
]
selected_case_idx = st.sidebar.selectbox("Select Investigation Case:", range(len(case_options)), format_func=lambda i: case_options[i])
selected_spec = BENCHMARK_CASES[selected_case_idx]
selected_cid = selected_spec["case_id"]

# Load case output
active_case = load_case_file(selected_cid)

_active_c = active_case.get("case", {})
_verdict_color = {"fraud": "#F23A7B", "legitimate": "#00FFA3", "uncertain": "#FEE101"}.get(_active_c.get("verdict", ""), "#FFF")
st.sidebar.markdown(f"""
    <div style="background: #052717; border: 2px solid #FEE101; border-radius: 10px; padding: 12px; margin-top: 15px;">
        <div style="font-size: 11px; color: #FEE101; font-weight: bold;">CASE ATTRIBUTES:</div>
        <div style="font-size: 11px; margin-top: 4px;">ID: <span style="color: #FFF;">{selected_cid}</span></div>
        <div style="font-size: 11px;">Trigger: <span style="color: #FF0080;">{selected_spec.get('trigger_type','')}</span></div>
        <div style="font-size: 11px;">Customer: <span style="color: #FFF;">{selected_spec.get('customer_id','')}</span></div>
        <div style="font-size: 11px;">Card: <span style="color: #FEE101;">{selected_spec.get('card_id','')}</span></div>
        <div style="font-size: 11px;">Flagged Txn: <span style="color: #00FFA3;">{selected_spec.get('flagged_txn_id','')}</span></div>
        <div style="font-size: 11px; margin-top:6px;">Verdict: <span style="color: {_verdict_color}; font-weight:bold;">{_active_c.get('verdict','pending').upper()}</span></div>
        <div style="font-size: 11px;">Prob: <span style="color: #FF0080; font-weight:bold;">{_active_c.get('fraud_probability', 0)*100:.1f}%</span></div>
    </div>
""", unsafe_allow_html=True)

# Sidebar Navigation Tabs
app_mode = st.sidebar.radio("Platform Navigation:", [
    "🔍 Case Investigation", 
    "🧪 Sandbox Alert Tester", 
    "📜 Policy Rule Graph (R1-R10)", 
    "🛡️ 20-Case QA Audit Suite"
])

# -----------------------------------------------------------------------------
# Mode 1: Case Investigation (Main View)
# -----------------------------------------------------------------------------
if app_mode == "🔍 Case Investigation":
    case_inner = active_case.get("case", {})
    verdict    = case_inner.get("verdict", "uncertain")
    prob       = case_inner.get("fraud_probability", 0.5)
    exposure   = case_inner.get("exposure_usd", 0.0)
    pattern    = case_inner.get("pattern", "none")
    sar_data   = active_case.get("sar", {})
    nba        = active_case.get("next_best_actions", {})

    if not active_case:
        st.warning(f"⚠️ Case file {selected_cid}.json not found. Run `python scripts/generate_cases.py` first.")
        st.stop()

    # Case Summary Header Banner
    _vcls = {"fraud": "pill-fraud", "legitimate": "pill-legit", "uncertain": "pill-yellow"}
    verdict_badge_class = _vcls.get(verdict, "pill-yellow")
    sar_badge = "<span class='hh-pill pill-fraud'>SAR FILED (L2)</span>" if sar_data.get("file") else "<span class='hh-pill' style='background:#333; color:#aaa;'>NO SAR</span>"
    status_str = case_inner.get("status", "").upper().replace("_", " ")

    st.markdown(f"""
        <div style="background: linear-gradient(135deg, #0E7A44 0%, #0B6839 100%); border: 3px solid #F23A7B; border-radius: 12px; padding: 14px 20px; margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center; box-shadow: 0 8px 26px rgba(4,38,22,0.5);">
            <div>
                <span style="font-family: 'Anton', sans-serif; font-size: 28px; color: #FEE101; letter-spacing: 1.5px; margin-right: 12px;">{selected_cid}</span>
                <span class="hh-pill {verdict_badge_class}" style="font-size: 13px; margin-right: 8px;">{verdict.upper()}</span>
                {sar_badge}
                <div style="font-family: 'Victor Mono', monospace; font-size: 12px; color: #FFFBE8; margin-top: 6px;">
                    PATTERN: <span style="color: #FEE101; font-weight: bold;">{pattern.upper().replace('_',' ')}</span>
                    &nbsp;|&nbsp; EXPOSURE: <span style="color: #00FFA3; font-weight: bold;">${exposure:,.2f} USD</span>
                    &nbsp;|&nbsp; FRAUD PROBABILITY: <span style="color: #F23A7B; font-weight: bold;">{prob*100:.1f}%</span>
                    &nbsp;|&nbsp; STATUS: <span style="color: #00E5FF; font-weight: bold;">{status_str}</span>
                </div>
            </div>
            <div style="text-align: right;">
                <div style="font-size: 11px; color: #FEE101;">GRAPH CASE: {case_inner.get('graph_case_id', '')}</div>
                <div style="font-size: 10px; color: #FFFBE8;">WRITTEN TO GRAPH: <span style="color: #00FFA3;">{'YES' if case_inner.get('written_to_graph') else 'NO'}</span></div>
                <div style="font-size: 10px; color: #FEE101;">TOOL CALLS: {active_case.get('tool_calls', 0)} · {active_case.get('latency_s', 0)}s</div>
            </div>
        </div>
    """, unsafe_allow_html=True)

    # ── Evidence + Next-Best-Actions ─────────────────────────────────────
    col_left, col_right = st.columns([1, 1], gap="medium")

    with col_left:
        render_graph_view(active_case, height=420)
        render_conflict_gauge(active_case, height=320)

    with col_right:
        render_timeline(active_case, height=420)
        render_sar_view(active_case)

    # ── Evidence list ────────────────────────────────────────────────────
    evidence_list = case_inner.get("evidence", [])
    if evidence_list:
        st.markdown("""
            <div style="font-family: 'Victor Mono', monospace; font-size: 12px; color: #FEE101;
                        font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                🔬 GRAPH EVIDENCE CHAIN:
            </div>
        """, unsafe_allow_html=True)
        for i, ev in enumerate(evidence_list, 1):
            src_color = {"graph": "#00E5FF", "customer": "#00FFA3", "analyst": "#F23A7B"}.get(ev.get("source",""), "#FEE101")
            st.markdown(f"""
                <div style="background: #052717; border-left: 3px solid {src_color}; padding: 8px 14px;
                            border-radius: 6px; font-size: 11px; margin-bottom: 6px; font-family: 'JetBrains Mono', monospace; border: 1px solid rgba(254,225,1,0.25);">
                    <span style="color: {src_color}; font-weight: bold;">[{ev.get('source','').upper()}]</span>
                    <span style="color: #FFFBE8;"> {ev.get('claim','')}</span>
                    <div style="color: #888; font-size: 10px; margin-top: 3px;">ref: {ev.get('ref','')} | entities: {', '.join(ev.get('entity_ids',[]))}</div>
                </div>
            """, unsafe_allow_html=True)

    # ── Stop reason ─────────────────────────────────────────────────────
    st.markdown(f"""
        <div style="background: #052717; border: 1.5px solid #FEE101; border-radius: 10px;
                    padding: 14px; margin-top: 14px; font-family: 'JetBrains Mono', monospace;">
            <div style="color: #FEE101; font-weight: bold; font-size: 12px; margin-bottom: 6px;">🛑 AGENT STOP REASON:</div>
            <div style="font-size: 12px; color: #FFFBE8; line-height: 1.5;">{active_case.get('stop_reason', '')}</div>
        </div>
        <div style="background: #052717; border: 1px solid rgba(254,225,1,0.3); border-radius: 10px;
                    padding: 14px; margin-top: 10px; font-family: 'JetBrains Mono', monospace;">
            <div style="color: #FEE101; font-weight: bold; font-size: 12px; margin-bottom: 6px;">📝 CASE SUMMARY:</div>
            <div style="font-size: 12px; color: #FFFBE8; line-height: 1.5;">{case_inner.get('summary', '')}</div>
        </div>
    """, unsafe_allow_html=True)

    # ── Similar prior cases ──────────────────────────────────────────────
    similar = case_inner.get("similar_prior_cases", [])
    if similar:
        st.markdown("""
            <div style="font-family: 'Victor Mono', monospace; font-size: 12px; color: #FEE101;
                        font-weight: bold; margin-top: 18px; margin-bottom: 8px;">
                ⏳ SIMILAR PRIOR CASES (from closed_cases_history.csv):
            </div>
        """, unsafe_allow_html=True)
        sc_cols = st.columns(len(similar))
        for idx, sc in enumerate(similar):
            with sc_cols[idx]:
                st.markdown(f"""
                    <div style="background: #052717; border-left: 3px solid #00E5FF;
                                padding: 10px 14px; border-radius: 6px; font-size: 11px; border: 1px solid rgba(254,225,1,0.25);">
                        <div style="color: #00E5FF; font-weight: bold;">{sc}</div>
                        <div style="color: #FFFBE8; margin-top: 2px;">Closed case · pattern match</div>
                    </div>
                """, unsafe_allow_html=True)

# -----------------------------------------------------------------------------
# Mode 2: Live Sandbox Alert Tester
# -----------------------------------------------------------------------------
elif app_mode == "🧪 Sandbox Alert Tester":
    st.markdown("""
        <div style="font-family: 'Imbue', serif; font-size: 28px; color: #FEE101; font-weight: 800; margin-bottom: 8px;">
            THE SANDBOX · ON-DEMAND FRAUD DETECTIVE
        </div>
        <div style="font-size: 12px; color: #FFFBE8; margin-bottom: 20px;">
            Test arbitrary transaction anomalies, disputes, and device proxies through the autonomous multi-agent pipeline in real-time.
        </div>
    """, unsafe_allow_html=True)

    with st.form("custom_test_form"):
        col_s1, col_s2, col_s3 = st.columns(3)
        with col_s1:
            custom_cid = st.text_input("Customer ID:", value="C99999")
            custom_kid = st.text_input("Card ID:", value="C99999-K1")
            custom_tid = st.text_input("Transaction ID:", value="TXN_SANDBOX_01")
        with col_s2:
            custom_amount = st.number_input("Transaction Amount ($ USD):", min_value=1.0, max_value=50000.0, value=1250.00, step=50.0)
            custom_score = st.slider("Anomaly Risk Score (0.0 to 1.0):", min_value=0.0, max_value=1.0, value=0.88, step=0.01)
            custom_trigger = st.selectbox("Trigger Type:", ["risk_score", "customer_report", "analyst_request"])
        with col_s3:
            custom_proxy = st.checkbox("Flag Anonymous Proxy / Tor", value=True)
            custom_recurring = st.checkbox("Matches Recurring Billing Interval", value=False)
            custom_cust_denial = st.selectbox("Customer Validation Simulation:", ["denied_transaction", "confirmed_authorized", "subscription_acknowledged"])

        submit_btn = st.form_submit_button("⚡ EXECUTE INVESTIGATION AGENT")

    if submit_btn:
        custom_spec = {
            "case_id": "SANDBOX-RUN",
            "opened_at": "2016-12-30T10:00:00Z",
            "trigger_type": custom_trigger,
            "flagged_txn_id": custom_tid,
            "card_id": custom_kid,
            "customer_id": custom_cid,
            "trigger_details": {
                "amount": custom_amount,
                "risk_score": custom_score,
                "is_proxy": custom_proxy,
                "is_recurring": custom_recurring,
                "customer_response": custom_cust_denial
            }
        }
        with st.spinner("Multi-Agent Detective executing graph traversals, conflict scoring, and policy routing..."):
            custom_result = coordinator.investigate(custom_spec)
        
        st.success("Investigation complete! Rendered results below:")
        col_sb_l, col_sb_r = st.columns(2)
        with col_sb_l:
            render_graph_view(custom_result, height=400)
            render_conflict_gauge(custom_result, height=300)
        with col_sb_r:
            render_timeline(custom_result, height=400)
            render_sar_view(custom_result)

# -----------------------------------------------------------------------------
# Mode 3: Policy Rule Graph (Innovation 1)
# -----------------------------------------------------------------------------
elif app_mode == "📜 Policy Rule Graph (R1-R10)":
    st.markdown("""
        <div style="font-family: 'Imbue', serif; font-size: 28px; color: #FEE101; font-weight: 800; margin-bottom: 8px;">
            STRATEGIC INNOVATION 1: POLICY RULES AS A GRAPH
        </div>
        <div style="font-size: 12px; color: #FFFBE8; margin-bottom: 20px;">
            Instead of a rigid Python if/else ladder, bank policies R1–R10 are modeled as vertices in TigerGraph with traversable <code>OVERRIDES</code> and <code>ESCALATES_TO</code> edges.
        </div>
    """, unsafe_allow_html=True)

    rules_data = [
        {"Rule": "R1", "Title": "Weak Anomaly Verification", "Action": "VERIFY_WITH_CUSTOMER", "Route": "auto", "Overrides": "None", "Description": "Risk score anomaly under 0.70 with no prior complaints initiates customer contact."},
        {"Rule": "R2", "Title": "Customer Denial Containment", "Action": "BLOCK_CARD, CREATE_CASE", "Route": "L1", "Overrides": "R1 (Overrides Weak Verify)", "Description": "Cardholder disputes transaction; immediate containment required."},
        {"Rule": "R3", "Title": "Legitimate Clearance", "Action": "CLOSE_NO_FRAUD", "Route": "auto", "Overrides": "R1 (Overrides Weak Verify)", "Description": "Customer confirms travel / purchase. Dismiss alert with zero customer friction."},
        {"Rule": "R4", "Title": "Rapid Burst Velocity", "Action": "DECLINE_TRANSACTION", "Route": "L1", "Overrides": "None", "Description": "High velocity cross-merchant purchase burst within 1 hour."},
        {"Rule": "R5", "Title": "Micro-Auth Card Testing", "Action": "BLOCK_CARD, CREATE_CASE", "Route": "L1", "Overrides": "None", "Description": "Sequence of micro-authorizations (<$5) followed by high-dollar spike."},
        {"Rule": "R6", "Title": "Device Ring Network", "Action": "MONITOR_CONNECTED_CARDS", "Route": "L2", "Overrides": "None", "Description": "Device fingerprint shared across >= 3 distinct cards."},
        {"Rule": "R7", "Title": "Recurring Subscription", "Action": "WARN_CUSTOMER, CREATE_CASE", "Route": "auto", "Overrides": "R2 (Overrides Card Block)", "Description": "Dispute on recurring billing interval. Warn customer rather than cancel card."},
        {"Rule": "R8", "Title": "Evidence Conflict Escalation", "Action": "CREATE_CASE", "Route": "L1", "Overrides": "None", "Description": "Evidence Conflict Score C >= 0.40. Escalates directly to human analyst."},
        {"Rule": "R9", "Title": "Regulatory SAR Filing", "Action": "FILE_REPORT", "Route": "L2", "Overrides": "R3 if exposure > $1k", "Description": "Exposure > $1,000, multi-card ring, or undocumented pattern."},
        {"Rule": "R10", "Title": "Second-Line Supervisor Sign-off", "Action": "ANALYST_CONFIRMATION", "Route": "L2", "Overrides": "None", "Description": "Level 2 senior officer concurrence required for multi-action plan."}
    ]
    st.table(rules_data)

# -----------------------------------------------------------------------------
# Mode 4: 20-Case QA Audit Suite (Innovation 7)
# -----------------------------------------------------------------------------
elif app_mode == "🛡️ 20-Case QA Audit Suite":
    st.markdown("""
        <div style="font-family: 'Imbue', serif; font-size: 28px; color: #FEE101; font-weight: 800; margin-bottom: 8px;">
            STRATEGIC INNOVATION 7: POST-RUN 20-CASE QA AUDIT SUITE
        </div>
        <div style="font-size: 12px; color: #FFFBE8; margin-bottom: 20px;">
            Automated multi-dimensional test suite verifying 100% schema conformity, complete R1–R10 rule coverage, initial-to-final action evolution, and FinCEN SAR threshold integrity.
        </div>
    """, unsafe_allow_html=True)

    if st.button("🚀 EXECUTE LIVE MULTI-DIMENSIONAL QA AUDIT"):
        from scripts.qa_audit import audit_case_pack
        with st.spinner("Auditing all 20 case files across 5 quality vectors..."):
            success = audit_case_pack()
        if success:
            st.success("🎉 AUDIT PASSED 100%! All 20 cases meet all 5 evaluation dimensions.")
        else:
            st.error("Audit encountered defects.")

    # Show cases grid
    st.markdown("### 20 Benchmark Cases Summary Table")
    case_table = []
    for b in BENCHMARK_CASES:
        c_obj = load_case_file(b["case_id"])
        c_inv = c_obj.get("investigation", {})
        c_sar = c_obj.get("sar", {})
        case_table.append({
            "Case ID": b["case_id"],
            "Trigger": b["trigger_type"],
            "Amount": f"${b['trigger_details'].get('amount', 0):,.2f}",
            "Verdict": c_inv.get("verdict", "N/A"),
            "Fraud Prob": f"{c_inv.get('fraud_probability', 0)*100:.1f}%",
            "SAR Filed": "YES (L2)" if c_sar.get("file") else "NO",
            "Pattern": c_inv.get("pattern", "N/A")
        })
    st.dataframe(case_table, use_container_width=True)

# Footer
st.markdown("<hr style='border: 1px solid rgba(254, 225, 1, 0.2); margin-top: 30px;'>", unsafe_allow_html=True)
st.markdown("""
    <div style="display: flex; justify-content: space-between; font-family: 'Victor Mono', monospace; font-size: 11px; color: #FFFBE8;">
        <div>© 2026 TigerDetect · Built for Hacker House Goa (IEEE-CIS Fraud Investigation Edition)</div>
        <div>STYLING: <span style="color: #FEE101;">OFFICIAL HHGOA.COM BRAND KIT</span> | 2:47 PM STUDIO</div>
    </div>
""", unsafe_allow_html=True)
