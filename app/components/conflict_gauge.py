"""
Evidence Conflict & Uncertainty Gauge (Strategic Innovation 2: Rule R8)
Visualizes evidence discordance, signal polarity breakdown, and Devil's Advocate hypotheses.
"""

from typing import Dict, List, Any
import streamlit.components.v1 as components


def render_conflict_gauge(case_data: Dict[str, Any], height: int = 340):
    inv = case_data.get("investigation", {})
    conflict_score = float(inv.get("conflict_score", 0.0))
    uncertainty = str(inv.get("uncertainty_level", "low")).upper()
    conflicting_signals = inv.get("conflicting_signals", [])
    devils_advocate = inv.get("devils_advocate", {})
    innocent_score = float(devils_advocate.get("innocent_score", 0.0))
    hypotheses = devils_advocate.get("hypotheses", [])

    # Color mapping
    gauge_color = "#FF0080" if conflict_score >= 0.40 else ("#FEE101" if conflict_score >= 0.20 else "#00FFA3")
    bar_width_pct = int(conflict_score * 100)

    # Format conflicting pairs HTML
    pairs_html = ""
    if conflicting_signals:
        for p in conflicting_signals[:3]:
            pairs_html += f"""
            <div style="background: rgba(255, 0, 128, 0.12); border-left: 3px solid #FF0080; padding: 8px 12px; margin-bottom: 8px; border-radius: 4px; font-family: 'Inter', sans-serif; font-size: 13px; line-height: 1.5; color: #FFFFFF;">
                <span style="color: #FF0080; font-weight: 700;">[CONFLICT]</span> {p.get('details', '')}
            </div>
            """
    else:
        pairs_html = """
        <div style="background: rgba(0, 255, 163, 0.12); border-left: 3px solid #00FFA3; padding: 8px 12px; border-radius: 4px; font-family: 'Inter', sans-serif; font-size: 13px; color: #FFFFFF;">
            No significant evidential discordance detected. Signals converge consistently.
        </div>
        """

    # Format Devil's Advocate HTML
    hypo_html = ""
    if hypotheses:
        hypo_html = f"""
        <div style="margin-top: 12px; font-family: 'Inter', sans-serif; font-size: 13px; color: #FEE101; background: #082817; padding: 10px 14px; border-radius: 6px; border: 1px solid rgba(254, 225, 1, 0.35); line-height: 1.55;">
            <div style="font-weight: 800; margin-bottom: 4px; color: #FEE101; font-family: 'Plus Jakarta Sans', sans-serif;">⚖️ DEVIL'S ADVOCATE ADVERSARIAL CRITIQUE:</div>
            <div style="color: #F8F9FA;">"{hypotheses[0]}"</div>
        </div>
        """

    html_content = f"""
    <div style="background: #051A0E; border: 2px solid #FEE101; border-radius: 12px; padding: 18px; box-shadow: 0 0 20px rgba(254, 225, 1, 0.15); color: #F8F9FA; font-family: 'Inter', sans-serif;">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
            <div style="font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 14px; color: #FEE101; text-transform: uppercase; letter-spacing: 0.5px;">
                📊 EVIDENCE CONFLICT METER (RULE R8)
            </div>
            <div style="background: {gauge_color}; color: #000000; font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 12px; padding: 3px 10px; border-radius: 4px;">
                UNCERTAINTY: {uncertainty}
            </div>
        </div>

        <div style="margin-bottom: 14px;">
            <div style="display: flex; justify-content: space-between; font-size: 13px; color: #F8F9FA; margin-bottom: 6px;">
                <span>Conflict Metric C:</span>
                <span style="font-weight: 700; color: #FEE101; font-family: 'JetBrains Mono', monospace;">{conflict_score:.3f} / 1.000</span>
            </div>
            <div style="width: 100%; height: 12px; background: #000000; border-radius: 6px; overflow: hidden; border: 1px solid rgba(254, 225, 1, 0.4);">
                <div style="width: {bar_width_pct}%; height: 100%; background: linear-gradient(90deg, #00FFA3 0%, #FEE101 50%, #FF0080 100%); transition: width 0.5s ease;"></div>
            </div>
            <div style="display: flex; justify-content: space-between; font-size: 10px; color: #D1D5DB; margin-top: 3px;">
                <span>0.00 (Harmonious)</span>
                <span style="color: #FF0080; font-weight: 700;">Threshold: 0.40</span>
                <span>1.00 (Severe Discordance)</span>
            </div>
        </div>

        {pairs_html}
        {hypo_html}
    </div>
    """
    components.html(html_content, height=height)
