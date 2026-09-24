"""
Real-Data Loaders & Graph Builder
Loads the four provided CSV files — case_pack.csv, transactions.csv,
identity.csv, closed_cases_history.csv — as the single source of truth
(per README (2).md) and builds the in-memory graph from them.

No fabricated entities: every Customer, Card, Transaction, DeviceProfile,
BillingRegion and ClosedCase vertex in the graph corresponds to a real row
in the provided data. Transactions carry their real Vesta feature columns,
so card history statistics (amount baseline, product codes, merchant-velocity
proxies) are computed from the actual data instead of seed constants.
"""
import csv
import re
from pathlib import Path
from typing import Dict, List, Optional, Set

ROOT = Path(__file__).resolve().parent.parent.parent

# Generic DeviceInfo tokens that are NOT device fingerprints. In the real
# identity.csv these strings span hundreds of unrelated customers, so they can
# never serve as a shared-origin key for a device ring.
GENERIC_DEVICE_INFOS = {
    "", "windows", "trident/7.0", "ios device", "macos", "rv:11.0",
    "android", "chrome", "firefox", "safari", "edge", "linux", "other",
}


def is_specific_device(device_info: str) -> bool:
    d = (device_info or "").strip().lower()
    return bool(d) and d not in GENERIC_DEVICE_INFOS


# Valid pattern vocabulary exactly as defined by README (2).md
README_PATTERNS = {
    "card_testing",
    "card_not_present_fraud",
    "card_not_present_new_device",
    "out_of_region_use",
    "account_takeover",
    "undocumented",
    "none",
}

# Map of column groups we keep on Transaction vertices for evidence queries.
# Full Vesta columns stay available via raw_row for on-demand access.
_KEEP_TXN_COLS = [
    "TransactionID", "TransactionDT", "TransactionAmt", "ProductCD",
    "card1", "card2", "card3", "card4", "card5", "card6",
    "addr1", "addr2", "dist1", "dist2",
    "P_emaildomain", "R_emaildomain",
    "customer_id", "ts", "channel", "risk_score",
]


def _f(v) -> float:
    try:
        if v is None or v == "":
            return 0.0
        return float(v)
    except (TypeError, ValueError):
        return 0.0


def _norm_pattern(p: str) -> str:
    p = (p or "").strip().lower().replace("-", "_").replace(" ", "_")
    return p if p in README_PATTERNS else "undocumented"


class RealDataStore:
    """
    Holds the parsed CSV data and offers lookups for the agents.
    Loads lazily and caches so the 590k-row file is parsed once per process.
    """

    def __init__(self):
        self.case_pack: List[Dict[str, str]] = []
        self.closed_cases: List[Dict[str, str]] = []
        self._flagged: Dict[str, Dict[str, str]] = {}
        self._identity: Dict[str, Dict[str, str]] = {}
        self._card_history: Dict[str, List[Dict[str, str]]] = {}
        self._loaded = False

    # ------------------------------------------------------------------
    # Loading
    # ------------------------------------------------------------------
    def load(self) -> "RealDataStore":
        if self._loaded:
            return self
        self._load_case_pack()
        self._load_closed_cases()
        self._load_transactions()
        self._load_identity()
        self._loaded = True
        return self

    def _load_case_pack(self):
        with open(ROOT / "case_pack.csv", encoding="utf-8") as f:
            self.case_pack = [dict(r) for r in csv.DictReader(f)]

    def _load_closed_cases(self):
        with open(ROOT / "closed_cases_history.csv", encoding="utf-8") as f:
            self.closed_cases = [dict(r) for r in csv.DictReader(f)]
        for c in self.closed_cases:
            c["pattern"] = _norm_pattern(c.get("pattern", "none"))

    def _load_transactions(self):
        """Single streaming pass over transactions.csv.

        Captures the 20 flagged transactions and the full real history of the
        20 case customers (~32k rows of real data). Everything else streams by.
        """
        flagged_ids: Set[str] = {c["flagged_txn_id"] for c in self.case_pack}
        customer_ids: Set[str] = {c["customer_id"] for c in self.case_pack}

        with open(ROOT / "transactions.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tid = row.get("TransactionID", "")
                cust = row.get("customer_id", "")
                if tid in flagged_ids:
                    self._flagged[tid] = dict(row)
                if cust in customer_ids:
                    self._card_history.setdefault(cust, []).append(dict(row))

    def _load_identity(self):
        flagged_ids: Set[str] = {c["flagged_txn_id"] for c in self.case_pack}
        with open(ROOT / "identity.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                tid = row.get("TransactionID", "")
                if tid in flagged_ids:
                    self._identity[tid] = dict(row)

    # ------------------------------------------------------------------
    # Lookups
    # ------------------------------------------------------------------
    def get_flagged_txn(self, txn_id: str) -> Optional[Dict[str, str]]:
        self.load()
        return self._flagged.get(str(txn_id))

    def get_identity(self, txn_id: str) -> Optional[Dict[str, str]]:
        self.load()
        return self._identity.get(str(txn_id))

    def get_card_history(self, customer_id: str) -> List[Dict[str, str]]:
        self.load()
        return self._card_history.get(customer_id, [])

    def get_case_pack(self) -> List[Dict[str, str]]:
        self.load()
        return self.case_pack

    def get_closed_cases(self) -> List[Dict[str, str]]:
        self.load()
        return self.closed_cases

    def closed_cases_by_pattern(self) -> Dict[str, List[Dict[str, str]]]:
        self.load()
        by: Dict[str, List[Dict[str, str]]] = {}
        for c in self.closed_cases:
            by.setdefault(c.get("pattern", "none"), []).append(c)
        return by

    def device_neighbors(self, device_info: str, proxy: str = "", window_days: int = 45) -> List[Dict[str, str]]:
        """Real device-ring analysis: which OTHER customer cards transacted from
        the same device (matched on DeviceInfo, the README's device-profile key)
        within the window, based on identity.csv joined to transactions.csv.

        When the flagged transaction carries a proxy flag (id_23), the proxy flag
        is part of the shared-origin signature — DeviceInfo alone is a common
        consumer phone model; DeviceInfo + IP_PROXY:ANONYMOUS is the ring."""
        self.load()
        device_info = (device_info or "").strip()
        proxy = (proxy or "").strip()
        if not device_info:
            return []
        matches: List[Dict[str, str]] = []
        with open(ROOT / "identity.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if (row.get("DeviceInfo") or "").strip() != device_info:
                    continue
                if proxy and (row.get("id_23") or "").strip() != proxy:
                    continue
                matches.append(row)
        if not matches:
            return []
        tid_set = {m["TransactionID"] for m in matches}
        txns: Dict[str, Dict[str, str]] = {}
        with open(ROOT / "transactions.csv", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                if row.get("TransactionID", "") in tid_set:
                    txns[row["TransactionID"]] = dict(row)
        if not txns:
            return []
        import datetime
        ts_list = [txns[t]["ts"] for t in txns if txns[t].get("ts")]
        if not ts_list:
            return []
        latest_dt = datetime.datetime.fromisoformat(max(ts_list))
        out: List[Dict[str, str]] = []
        seen_cards: Set[str] = set()
        for t, row in txns.items():
            ts = row.get("ts", "")
            if not ts:
                continue
            if (latest_dt - datetime.datetime.fromisoformat(ts)).days > window_days:
                continue
            cust_id = row.get("customer_id", "")
            card_key = card_display_id(cust_id, row.get("card1", ""))
            if card_key in seen_cards:
                continue
            seen_cards.add(card_key)
            out.append({
                "customer_id": cust_id,
                "card_id": card_key,
                "txn_id": t,
                "ts": ts,
                "amount": row.get("TransactionAmt", ""),
                "risk_score": row.get("risk_score", ""),
                "channel": row.get("channel", ""),
            })
        return out

    @staticmethod
    def _device_str(id_row: Dict[str, str]) -> str:
        parts = [
            (id_row.get("DeviceInfo") or "").strip(),
            (id_row.get("id_30") or "").strip(),
            (id_row.get("id_31") or "").strip(),
            (id_row.get("id_33") or "").strip(),
        ]
        return " | ".join(p for p in parts if p)


# Module-level singleton
STORE = RealDataStore()


# ----------------------------------------------------------------------
# Card ID mapping
# ----------------------------------------------------------------------
def card_ids_for(customer_id: str, card1: str) -> List[str]:
    """Deterministically map (customer_id, card1) -> [Cxxxxx-Kn].

    The README states card IDs look like C01234-K1 (one customer can hold
    several cards). Real customer rows in transactions.csv are keyed by
    customer_id + card1; we enumerate the customer's distinct card1 values
    in first-seen order and assign K1, K2, ... consistently across the run.
    """
    store = STORE.load()
    seen: List[str] = []
    for row in store.get_card_history(customer_id):
        c1 = row.get("card1", "")
        if c1 and c1 not in seen:
            seen.append(c1)
    if card1 not in seen:
        seen.append(card1)
    idx = seen.index(card1) + 1
    return [f"{customer_id}-K{idx}"]


def card_display_id(customer_id: str, card1: str) -> str:
    """README-format card ID (Cxxxxx-Kn) for any customer, grounded in data:
    1. if closed_cases_history.csv pins the customer to exactly one card_id,
       use it (that is the bank's own numbering);
    2. else use the cached-history K-index mapping (exact for case-pack
       customers);
    3. else default to -K1."""
    store = STORE.load()
    known = {c.get("card_id", "") for c in store.closed_cases
             if c.get("customer_id") == customer_id and c.get("card_id")}
    known.discard("")
    if len(known) == 1:
        return next(iter(known))
    return card_ids_for(customer_id, card1)[0]


# ----------------------------------------------------------------------
# Graph builder: populates InMemoryGraphEngine purely from real CSV rows
# ----------------------------------------------------------------------
def build_graph_from_real_data(engine) -> RealDataStore:
    """Populate the in-memory graph engine from the four provided CSVs.

    Vertices/edges follow the README's suggested schema:
      Customer -OWNS-> Card -MADE-> Transaction
      Transaction -FROM_DEVICE-> DeviceProfile (online only, from identity.csv)
      Transaction -BILLED_IN-> BillingRegion (addr1)
      Transaction -NEXT-> Transaction (per card, ordered by ts)
      ClosedCase -ON_CARD-> Card
    """
    store = STORE.load()

    # --- Customers, cards, transactions, regions -----------------------
    cards: Dict[tuple, str] = {}        # (customer_id, card1) -> card_id
    card_txns: Dict[str, List[Dict[str, str]]] = {}

    # Stream all customer history rows we cached (real rows only).
    for cust_id, rows in store._card_history.items():
        # Customer vertex: home region = most frequent real addr1
        region_counts: Dict[str, int] = {}
        for r in rows:
            a1 = (r.get("addr1") or "").strip()
            if a1:
                region_counts[a1] = region_counts.get(a1, 0) + 1
        home_region = max(region_counts, key=region_counts.get) if region_counts else ""

        engine.add_vertex("Customer", cust_id, {
            "customer_id": cust_id,
            "home_region": home_region,
            "n_txns": len(rows),
        })

        # Cards
        ordered_card1: List[str] = []
        for r in rows:
            c1 = r.get("card1", "")
            if c1 and c1 not in ordered_card1:
                ordered_card1.append(c1)
        for i, c1 in enumerate(ordered_card1, 1):
            card_id = f"{cust_id}-K{i}"
            cards[(cust_id, c1)] = card_id
            engine.add_vertex("Card", card_id, {
                "card_id": card_id,
                "customer_id": cust_id,
                "card1": c1,
            })
            engine.add_edge("OWNS", "Customer", cust_id, "Card", card_id)

        # Transactions for this customer
        for r in rows:
            tid = r.get("TransactionID", "")
            c1 = r.get("card1", "")
            card_id = cards.get((cust_id, c1))
            if not card_id:
                continue
            txn_attrs = {k: r.get(k, "") for k in _KEEP_TXN_COLS}
            txn_attrs["amount"] = _f(r.get("TransactionAmt"))
            engine.add_vertex("Transaction", tid, txn_attrs)
            engine.add_edge("MADE", "Card", card_id, "Transaction", tid)
            a1 = (r.get("addr1") or "").strip()
            if a1:
                if engine.get_vertex("BillingRegion", a1) is None:
                    engine.add_vertex("BillingRegion", a1, {"region_code": a1})
                engine.add_edge("BILLED_IN", "Transaction", tid, "BillingRegion", a1)
            card_txns.setdefault(card_id, []).append(r)

    # --- Device profiles from identity.csv (flagged txns) ---------------
    for tid, idrow in store._identity.items():
        dstr = store._device_str(idrow)
        if not dstr:
            continue
        dev_id = "DEV-" + re.sub(r"[^A-Za-z0-9]+", "-", dstr)[:80]
        if engine.get_vertex("DeviceProfile", dev_id) is None:
            engine.add_vertex("DeviceProfile", dev_id, {
                "device_id": dev_id,
                "device_profile": dstr,
                "device_info": (idrow.get("DeviceInfo") or "").strip(),
                "device_type": (idrow.get("DeviceType") or "").strip(),
                "os": (idrow.get("id_30") or "").strip(),
                "browser": (idrow.get("id_31") or "").strip(),
                "screen": (idrow.get("id_33") or "").strip(),
                "id_15": (idrow.get("id_15") or "").strip(),
                "proxy": (idrow.get("id_23") or "").strip(),
            })
        if engine.get_vertex("Transaction", tid) is not None:
            engine.add_edge("FROM_DEVICE", "Transaction", tid, "DeviceProfile", dev_id)

    # --- NEXT edges per card ordered by ts ------------------------------
    for card_id, rows in card_txns.items():
        rows_sorted = sorted(rows, key=lambda r: r.get("ts", ""))
        for a, b in zip(rows_sorted, rows_sorted[1:]):
            engine.add_edge("NEXT", "Transaction", a["TransactionID"],
                            "Transaction", b["TransactionID"])

    # --- Closed cases ----------------------------------------------------
    for c in store.closed_cases:
        cc_id = c["case_id"]
        engine.add_vertex("ClosedCase", cc_id, {
            "case_id": cc_id,
            "customer_id": c.get("customer_id", ""),
            "card_id": c.get("card_id", ""),
            "opened_at": c.get("opened_at", ""),
            "closed_at": c.get("closed_at", ""),
            "outcome": c.get("outcome", ""),
            "pattern": c.get("pattern", "none"),
            "first_fraud_txn_id": c.get("first_fraud_txn_id", ""),
            "n_txns": c.get("n_txns", ""),
            "exposure_usd": _f(c.get("exposure_usd")),
            "connected_card_ids": c.get("connected_card_ids", ""),
            "actions_taken": c.get("actions_taken", ""),
            "report_filed": (c.get("report_filed", "") or "").strip().lower() == "yes",
            "analyst_notes": c.get("analyst_notes", ""),
        })
        card_id = c.get("card_id", "")
        if card_id and engine.get_vertex("Card", card_id) is not None:
            engine.add_edge("ON_CARD", "ClosedCase", cc_id, "Card", card_id)

    return store
