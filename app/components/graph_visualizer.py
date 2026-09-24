"""
Graph Visualizer Component for Streamlit
Renders interactive SVG / PyVis graph topology with neon path highlighting (Innovation 6)
and Hacker House Goa color tokens.
"""

from typing import Dict, List, Any, Optional
import streamlit as nx_st
import streamlit.components.v1 as components
import json


def render_graph_view(case_data: Dict[str, Any], height: int = 480):
    """
    Renders an interactive HTML5 Canvas / SVG graph visualization highlighting the evidence path.
    """
    cid = case_data.get("case_id", "HHG-001")
    trig = case_data.get("trigger", {})
    inv = case_data.get("investigation", {})
    paths = inv.get("provenance_paths", [])
    primary_path = paths[0] if paths else ""
    verdict = inv.get("verdict", "FRAUD")
    pattern = inv.get("pattern", "card_not_present_anomaly")

    cust_id = trig.get("customer_id", "C12382")
    card_id = trig.get("card_id", "C12382-K1")
    txn_id = trig.get("flagged_txn_id", "3514030")
    
    # Check if ring case
    is_ring = pattern == "device_ring_compromise" or cid == "HHG-014"

    # SVG / HTML graph with glowing neon effects
    node_color_card = "#FEE101"   # Hacker yellow
    node_color_cust = "#FFFBE8"   # Offwhite
    node_color_txn = "#FF0080" if verdict == "FRAUD" else "#00FFA3"  # Pink for fraud, green for legit
    node_color_dev = "#00E5FF"    # Electric cyan for device

    extra_nodes_html = ""
    extra_edges_html = ""

    if is_ring:
        extra_nodes_html = """
        <!-- Connected Ring Cards -->
        <g class="node hub" transform="translate(480, 220)">
            <circle r="22" fill="#FF0080" stroke="#FEE101" stroke-width="3" filter="url(#glow)"/>
            <text dy="5" text-anchor="middle" fill="#FFFFFF" font-family="'Victor Mono', monospace" font-size="10" font-weight="bold">HUB:K1</text>
        </g>
        <g class="node" transform="translate(620, 140)">
            <circle r="18" fill="#042A16" stroke="#FEE101" stroke-width="2"/>
            <text dy="4" text-anchor="middle" fill="#FEE101" font-family="'Victor Mono', monospace" font-size="9">C08721</text>
        </g>
        <g class="node" transform="translate(620, 220)">
            <circle r="18" fill="#042A16" stroke="#FEE101" stroke-width="2"/>
            <text dy="4" text-anchor="middle" fill="#FEE101" font-family="'Victor Mono', monospace" font-size="9">C04912</text>
        </g>
        <g class="node" transform="translate(620, 300)">
            <circle r="18" fill="#042A16" stroke="#FEE101" stroke-width="2"/>
            <text dy="4" text-anchor="middle" fill="#FEE101" font-family="'Victor Mono', monospace" font-size="9">C11034</text>
        </g>
        <!-- Ring Edges -->
        <line x1="480" y1="220" x2="350" y2="220" stroke="#FF0080" stroke-width="3" stroke-dasharray="4" filter="url(#glow)"/>
        <line x1="350" y1="220" x2="620" y2="140" stroke="#FEE101" stroke-width="2" opacity="0.8"/>
        <line x1="350" y1="220" x2="620" y2="220" stroke="#FEE101" stroke-width="2" opacity="0.8"/>
        <line x1="350" y1="220" x2="620" y2="300" stroke="#FEE101" stroke-width="2" opacity="0.8"/>
        """

    svg_content = f"""
    <div style="background: #042A16; border: 2px solid #FEE101; border-radius: 12px; padding: 15px; position: relative; overflow: hidden; box-shadow: 0 0 25px rgba(254, 225, 1, 0.15);">
        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 10px; border-bottom: 1px solid rgba(254,225,1,0.2); padding-bottom: 8px;">
            <div style="font-family: 'Victor Mono', monospace; font-size: 13px; color: #FEE101; text-transform: uppercase; letter-spacing: 1px;">
                ⚡ LITERAL GRAPH PROVENANCE PATH (INNOVATION 6)
            </div>
            <div style="background: #FF0080; color: #FFF; font-family: 'Victor Mono', monospace; font-size: 11px; padding: 2px 8px; border-radius: 4px; font-weight: bold;">
                {verdict}
            </div>
        </div>

        <div style="font-family: 'Victor Mono', monospace; font-size: 11px; color: #FFFBE8; background: #074424; padding: 8px 12px; border-radius: 6px; margin-bottom: 12px; word-break: break-all; border-left: 3px solid #FEE101;">
            <span style="color: #FEE101; font-weight: bold;">PATH:</span> {primary_path or '(Customer)-[:OWNS]->(Card)-[:MADE]->(Txn)'}
        </div>

        <svg viewBox="0 0 760 380" style="width: 100%; height: 340px; background: #000000; border-radius: 8px; border: 1px solid rgba(254,225,1,0.2);">
            <defs>
                <filter id="glow" x="-20%" y="-20%" width="140%" height="140%">
                    <feGaussianBlur stdDeviation="4" result="blur" />
                    <feComposite in="SourceGraphic" in2="blur" operator="over" />
                </filter>
                <marker id="arrow" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#FEE101" />
                </marker>
                <marker id="arrow-pink" viewBox="0 0 10 10" refX="22" refY="5" markerWidth="6" markerHeight="6" orient="auto-start-reverse">
                    <path d="M 0 0 L 10 5 L 0 10 z" fill="#FF0080" />
                </marker>
            </defs>

            <!-- Grid background lines -->
            <pattern id="grid" width="30" height="30" patternUnits="userSpaceOnUse">
                <path d="M 30 0 L 0 0 0 30" fill="none" stroke="rgba(11, 104, 57, 0.25)" stroke-width="0.5"/>
            </pattern>
            <rect width="100%" height="100%" fill="url(#grid)" />

            <!-- Edge 1: Customer -> Card -->
            <line x1="80" y1="120" x2="210" y2="120" stroke="#FEE101" stroke-width="2.5" marker-end="url(#arrow)" filter="url(#glow)"/>
            <text x="145" y="110" text-anchor="middle" fill="#FEE101" font-family="'Victor Mono', monospace" font-size="10">OWNS</text>

            <!-- Edge 2: Card -> Transaction -->
            <line x1="210" y1="120" x2="350" y2="120" stroke="{node_color_txn}" stroke-width="3" marker-end="url(#arrow-pink)" filter="url(#glow)"/>
            <text x="280" y="110" text-anchor="middle" fill="{node_color_txn}" font-family="'Victor Mono', monospace" font-size="10">MADE</text>

            <!-- Edge 3: Transaction -> Device -->
            <line x1="350" y1="120" x2="350" y2="220" stroke="#00E5FF" stroke-width="2.5" marker-end="url(#arrow)"/>
            <text x="375" y="175" text-anchor="start" fill="#00E5FF" font-family="'Victor Mono', monospace" font-size="10">FROM_DEVICE</text>

            <!-- Edge 4: Transaction -> Region -->
            <line x1="350" y1="120" x2="480" y2="60" stroke="#FFFBE8" stroke-width="2" stroke-dasharray="3" marker-end="url(#arrow)"/>
            <text x="420" y="80" text-anchor="middle" fill="#FFFBE8" font-family="'Victor Mono', monospace" font-size="10">BILLED_IN</text>

            {extra_edges_html}

            <!-- Node 1: Customer -->
            <g class="node" transform="translate(80, 120)">
                <circle r="22" fill="#074424" stroke="#FFFBE8" stroke-width="2.5"/>
                <text dy="5" text-anchor="middle" fill="#FFFBE8" font-family="'Victor Mono', monospace" font-size="9" font-weight="bold">{cust_id[:7]}</text>
                <text dy="36" text-anchor="middle" fill="#FFFBE8" font-family="'Victor Mono', monospace" font-size="10">Customer</text>
            </g>

            <!-- Node 2: Card -->
            <g class="node" transform="translate(210, 120)">
                <circle r="24" fill="#074424" stroke="#FEE101" stroke-width="3" filter="url(#glow)"/>
                <text dy="5" text-anchor="middle" fill="#FEE101" font-family="'Victor Mono', monospace" font-size="9" font-weight="bold">{card_id[:8]}</text>
                <text dy="38" text-anchor="middle" fill="#FEE101" font-family="'Victor Mono', monospace" font-size="10">Card</text>
            </g>

            <!-- Node 3: Flagged Transaction -->
            <g class="node" transform="translate(350, 120)">
                <circle r="26" fill="{node_color_txn}" stroke="#FFFFFF" stroke-width="3" filter="url(#glow)"/>
                <text dy="5" text-anchor="middle" fill="#000000" font-family="'Victor Mono', monospace" font-size="10" font-weight="bold">TXN</text>
                <text dy="40" text-anchor="middle" fill="{node_color_txn}" font-family="'Victor Mono', monospace" font-size="10" font-weight="bold">${case_data.get('investigation', {}).get('exposure_usd', 0):,.2f}</text>
            </g>

            <!-- Node 4: Device Profile -->
            <g class="node" transform="translate(350, 220)">
                <circle r="20" fill="#074424" stroke="#00E5FF" stroke-width="2.5"/>
                <text dy="4" text-anchor="middle" fill="#00E5FF" font-family="'Victor Mono', monospace" font-size="9">DEV</text>
                <text dy="34" text-anchor="middle" fill="#00E5FF" font-family="'Victor Mono', monospace" font-size="10">DeviceProfile</text>
            </g>

            <!-- Node 5: Billing Region -->
            <g class="node" transform="translate(480, 60)">
                <circle r="18" fill="#074424" stroke="#FFFBE8" stroke-width="2"/>
                <text dy="4" text-anchor="middle" fill="#FFFBE8" font-family="'Victor Mono', monospace" font-size="9">REG</text>
                <text dy="32" text-anchor="middle" fill="#FFFBE8" font-family="'Victor Mono', monospace" font-size="10">Region</text>
            </g>

            {extra_nodes_html}
        </svg>

        <div style="display: flex; gap: 15px; margin-top: 10px; font-family: 'Victor Mono', monospace; font-size: 11px; color: #FFFBE8;">
            <div><span style="color: #FEE101;">●</span> Card Entity</div>
            <div><span style="color: #FF0080;">●</span> Fraud Flagged Txn</div>
            <div><span style="color: #00FFA3;">●</span> Cleared Benign Txn</div>
            <div><span style="color: #00E5FF;">●</span> Device Profile</div>
            <div><span style="color: #FFFBE8;">●</span> Customer / Region</div>
        </div>
    </div>
    """
    components.html(svg_content, height=height)
