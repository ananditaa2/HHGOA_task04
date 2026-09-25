"""
System Configuration & Design System Tokens for TigerDetect
Styled with the official Hacker House Goa (hhgoa.com) Brand Kit
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Directories
BASE_DIR = Path(__file__).resolve().parent.parent
CASES_DIR = BASE_DIR / "cases"
GSQL_DIR = BASE_DIR / "gsql"
ASSETS_DIR = BASE_DIR / "assets"
SCRIPTS_DIR = BASE_DIR / "scripts"
SUBMISSION_DOCS_DIR = BASE_DIR / "submission_docs"

# Ensure directories exist
for directory in [CASES_DIR, GSQL_DIR, ASSETS_DIR, SUBMISSION_DOCS_DIR]:
    directory.mkdir(parents=True, exist_ok=True)

# Graph Engine Settings
GRAPH_BACKEND_MODE = os.getenv("GRAPH_BACKEND_MODE", "in_memory").lower()
TG_HOST = os.getenv("TG_HOST", "http://localhost:9000")
TG_USERNAME = os.getenv("TG_USERNAME", "tigergraph")
TG_PASSWORD = os.getenv("TG_PASSWORD", "tigergraph")
TG_GRAPH = os.getenv("TG_GRAPH") or os.getenv("TG_GRAPHNAME", "FraudGraph")
TG_SECRET = os.getenv("TG_SECRET", "")
TG_API_TOKEN = os.getenv("TG_API_TOKEN") or TG_SECRET

# Investigation & Risk Policy Constants
TIME_DECAY_HALF_LIFE_DAYS = 45.0  # Innovation 4: tau = 45 days
EVIDENCE_CONFLICT_THRESHOLD = 0.40  # Innovation 2: threshold for Rule R8
SAR_EXPOSURE_THRESHOLD = 1000.0  # FinCEN SAR mandatory threshold
CARD_TESTING_MICRO_LIMIT = 5.00  # Micro-auth boundary for Rule R5
CARD_TESTING_SPIKE_LIMIT = 100.00  # Follow-on spike boundary

# Hacker House Goa (hhgoa.com) Official Brand Kit Color Tokens
HH_COLORS = {
    "primary_green": "#0B6839",     # Deep Lush Goa Green (bg-brand-primary)
    "accent_yellow": "#FEE101",     # Radiant Hacker Marigold Yellow (bg-brand-accent)
    "brand_pink": "#FF0080",        # Electric Goa Devanagari Pink (bg-brand-pink)
    "brand_black": "#000000",       # Deep Obsidian Black (bg-brand-black)
    "brand_offwhite": "#FFFBE8",    # Warm Retro Offwhite (bg-brand-offwhite)
    "brand_white": "#FFFFFF",
    # Supporting functional palette
    "dark_forest_1": "#074424",
    "dark_forest_2": "#042A16",
    "card_bg": "#06341B",
    "border_yellow": "rgba(254, 225, 1, 0.35)",
    "border_green": "rgba(11, 104, 57, 0.45)",
    "glow_pink": "rgba(255, 0, 128, 0.4)",
    "glow_yellow": "rgba(254, 225, 1, 0.4)",
    "risk_low": "#00FFA3",
    "risk_medium": "#FEE101",
    "risk_high": "#FF0080",
}

# Typography
FONTS = {
    "headings": "Imbue, serif",
    "mono": "'Victor Mono', monospace, 'Courier New'",
}
