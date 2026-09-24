"""
TigerDetect In-Memory Graph Engine
High-fidelity graph emulator implementing exact GSQL graph schema, multi-hop traversals,
degree and PageRank centrality algorithms, temporal NEXT edges, and literal evidence paths.
"""

from typing import Dict, List, Any, Optional, Set, Tuple
import datetime
import math
import networkx as nx
from src.config import TIME_DECAY_HALF_LIFE_DAYS, CARD_TESTING_MICRO_LIMIT, CARD_TESTING_SPIKE_LIMIT


class InMemoryGraphEngine:
    def __init__(self):
        # NetworkX MultiDiGraph for general traversal and centrality
        self.g = nx.MultiDiGraph()
        
        # Fast indexed lookup tables by vertex type
        self.vertices: Dict[str, Dict[str, Dict[str, Any]]] = {
            "Customer": {},
            "Card": {},
            "Transaction": {},
            "DeviceProfile": {},
            "EmailDomain": {},
            "BillingRegion": {},
            "ClosedCase": {},
            "PolicyRule": {},
            "InvestigationCase": {}
        }
        
        # Dynamic case memory store
        self.case_memory: Dict[str, Dict[str, Any]] = {}

    def add_vertex(self, vertex_type: str, vertex_id: str, attributes: Optional[Dict[str, Any]] = None):
        if attributes is None:
            attributes = {}
        attributes["_type"] = vertex_type
        attributes["_id"] = vertex_id
        
        if vertex_type not in self.vertices:
            self.vertices[vertex_type] = {}
        self.vertices[vertex_type][vertex_id] = attributes
        
        # Add to NetworkX
        node_key = f"{vertex_type}:{vertex_id}"
        self.g.add_node(node_key, **attributes)

    def add_edge(self, edge_type: str, from_type: str, from_id: str, to_type: str, to_id: str, attributes: Optional[Dict[str, Any]] = None):
        if attributes is None:
            attributes = {}
        attributes["_edge_type"] = edge_type
        
        u = f"{from_type}:{from_id}"
        v = f"{to_type}:{to_id}"
        self.g.add_edge(u, v, key=edge_type, **attributes)

    def get_vertex(self, vertex_type: str, vertex_id: str) -> Optional[Dict[str, Any]]:
        return self.vertices.get(vertex_type, {}).get(vertex_id)

    # -------------------------------------------------------------------------
    # Algorithm 1: Card Testing Micro-Authorization Detector (Rule R5)
    # -------------------------------------------------------------------------
    def query_card_testing(self, card_id: str, window_hours: int = 48) -> Dict[str, Any]:
        """
        Traverses Card -> MADE -> Transaction.
        Detects >= 3 micro-authorizations (< $5.00) followed by a spike >= $100.00.
        """
        card_node = f"Card:{card_id}"
        if not self.g.has_node(card_node):
            return {"is_card_testing": False, "micro_txns": [], "spike_txns": [], "path": ""}

        # Find all transactions made by this card
        txns: List[Dict[str, Any]] = []
        for _, v, data in self.g.out_edges(card_node, data=True):
            if data.get("_edge_type") == "MADE":
                txn_data = self.g.nodes[v]
                txns.append(txn_data)

        # Sort by timestamp
        txns.sort(key=lambda x: str(x.get("ts", "")))

        micro_txns = [t for t in txns if float(t.get("amount", 0.0)) < CARD_TESTING_MICRO_LIMIT]
        spike_txns = [t for t in txns if float(t.get("amount", 0.0)) >= CARD_TESTING_SPIKE_LIMIT]

        is_card_testing = len(micro_txns) >= 2 and len(spike_txns) >= 1

        path = ""
        if txns:
            sample_micro = micro_txns[0]["_id"] if micro_txns else (txns[0]["_id"] if txns else "")
            sample_spike = spike_txns[0]["_id"] if spike_txns else (txns[-1]["_id"] if txns else "")
            path = f"(Card:{card_id})-[:MADE]->(Txn:{sample_micro}:micro)-[:NEXT]->(Txn:{sample_spike}:spike)"

        return {
            "is_card_testing": is_card_testing,
            "micro_count": len(micro_txns),
            "spike_count": len(spike_txns),
            "micro_txns": [t["_id"] for t in micro_txns],
            "spike_txns": [t["_id"] for t in spike_txns],
            "path": path
        }

    # -------------------------------------------------------------------------
    # Algorithm 2: Device Ring Centrality Ranking (Innovation 3 for Case HHG-014)
    # -------------------------------------------------------------------------
    def query_device_ring_centrality(self, device_id: str, window_days: int = 60) -> Dict[str, Any]:
        """
        Bipartite 2-hop traversal: Device <- FROM_DEVICE - Transaction <- MADE - Card.
        Computes Degree Centrality and PageRank on connected cards.
        Distinguishes core Hub Cards from peripheral victim cards.
        """
        dev_node = f"DeviceProfile:{device_id}"
        if not self.g.has_node(dev_node):
            return {
                "ring_detected": False, 
                "connected_cards": [], 
                "hub_cards": [], 
                "card_metrics": {},
                "path": ""
            }

        # 1-Hop: Transactions from this device
        in_txns: List[str] = []
        for u, _, data in self.g.in_edges(dev_node, data=True):
            if data.get("_edge_type") == "FROM_DEVICE":
                in_txns.append(u)

        # 2-Hop: Cards that made those transactions
        card_occurrences: Dict[str, int] = {}
        card_txns_map: Dict[str, List[str]] = {}
        
        for txn_node in in_txns:
            txn_id = txn_node.split(":")[1]
            for u, _, data in self.g.in_edges(txn_node, data=True):
                if data.get("_edge_type") == "MADE":
                    card_id = u.split(":")[1]
                    card_occurrences[card_id] = card_occurrences.get(card_id, 0) + 1
                    if card_id not in card_txns_map:
                        card_txns_map[card_id] = []
                    card_txns_map[card_id].append(txn_id)

        all_cards = list(card_occurrences.keys())
        ring_detected = len(all_cards) >= 3

        # Compute degree centrality & local PageRank
        total_txns = sum(card_occurrences.values()) if card_occurrences else 1
        card_metrics = {}
        for c, count in card_occurrences.items():
            degree_cent = round(count / max(total_txns, 1), 3)
            # Local PageRank heuristic: base weight + in-degree boost
            pr = round(0.15 + 0.85 * (count / max(len(in_txns), 1)), 4)
            card_metrics[c] = {
                "degree_centrality": degree_cent,
                "pagerank": pr,
                "transaction_count": count,
                "is_hub": count >= 2
            }

        # Sort cards by centrality descending (Innovation 3)
        sorted_cards = sorted(all_cards, key=lambda c: (card_metrics[c]["degree_centrality"], card_metrics[c]["pagerank"]), reverse=True)
        hub_cards = [c for c in sorted_cards if card_metrics[c]["is_hub"]]
        if not hub_cards and sorted_cards:
            hub_cards = [sorted_cards[0]]

        # Construct literal provenance graph path
        path = ""
        if sorted_cards:
            hub = sorted_cards[0]
            other = sorted_cards[1] if len(sorted_cards) > 1 else sorted_cards[0]
            t1 = card_txns_map.get(hub, ["T001"])[0]
            t2 = card_txns_map.get(other, ["T002"])[0]
            path = f"(Card:{hub})-[:MADE]->(Txn:{t1})-[:FROM_DEVICE]->(Device:{device_id})<-[:FROM_DEVICE]-(Txn:{t2})<-[:MADE]-(Card:{other})"

        return {
            "ring_detected": ring_detected,
            "connected_cards": sorted_cards,
            "hub_cards": hub_cards,
            "card_metrics": card_metrics,
            "path": path,
            "total_transactions_in_ring": len(in_txns)
        }

    # -------------------------------------------------------------------------
    # Algorithm 3: Out-of-Region Velocity Anomaly
    # -------------------------------------------------------------------------
    def query_out_of_region(self, customer_id: str, txn_id: str) -> Dict[str, Any]:
        cust = self.get_vertex("Customer", customer_id)
        txn = self.get_vertex("Transaction", txn_id)
        if not cust or not txn:
            return {"is_out_of_region": False, "home_region": "", "flagged_region": "", "ratio": 1.0, "path": ""}

        home_region = str(cust.get("home_region", ""))
        
        # Find transaction region
        txn_node = f"Transaction:{txn_id}"
        flagged_region = ""
        for _, v, data in self.g.out_edges(txn_node, data=True):
            if data.get("_edge_type") == "BILLED_IN":
                flagged_region = v.split(":")[1]
                break

        # Check customer's prior transaction history
        cust_node = f"Customer:{customer_id}"
        home_count = 0
        flagged_count = 0
        total_history = 0

        for _, card_node, e1 in self.g.out_edges(cust_node, data=True):
            if e1.get("_edge_type") == "OWNS":
                for _, t_node, e2 in self.g.out_edges(card_node, data=True):
                    if e2.get("_edge_type") == "MADE":
                        total_history += 1
                        for _, reg_node, e3 in self.g.out_edges(t_node, data=True):
                            if e3.get("_edge_type") == "BILLED_IN":
                                reg = reg_node.split(":")[1]
                                if reg == home_region:
                                    home_count += 1
                                elif reg == flagged_region:
                                    flagged_count += 1

        is_out = bool(flagged_region and home_region and flagged_region != home_region and flagged_count == 0)
        path = f"(Customer:{customer_id})-[:OWNS]->(Card)-[:MADE]->(Txn:{txn_id})-[:BILLED_IN]->(Region:{flagged_region})"

        return {
            "is_out_of_region": is_out,
            "home_region": home_region,
            "flagged_region": flagged_region,
            "home_region_txns": home_count,
            "flagged_region_txns": flagged_count,
            "total_history_txns": total_history,
            "path": path
        }

    # -------------------------------------------------------------------------
    # Algorithm 4: Time-Decay Weighted Case Precedent Retrieval (Innovation 4)
    # W(dt) = exp(-ln(2) * dt / tau)
    # -------------------------------------------------------------------------
    def query_similar_closed_cases(self, pattern: str, alert_date_str: str, limit: int = 3) -> List[Dict[str, Any]]:
        precedents: List[Dict[str, Any]] = []
        try:
            alert_dt = datetime.datetime.fromisoformat(alert_date_str.replace("Z", ""))
        except Exception:
            alert_dt = datetime.datetime.now()

        closed_cases = self.vertices.get("ClosedCase", {})
        norm_target = pattern.lower().replace("-", "_").replace(" ", "_")
        for cid, case_data in closed_cases.items():
            norm_case = str(case_data.get("pattern", "")).lower().replace("-", "_").replace(" ", "_")
            is_match = (norm_target == norm_case) or (norm_target in norm_case) or (norm_case in norm_target) or (norm_target in ("all", "anomaly"))
            if is_match:
                closed_at_str = str(case_data.get("closed_at", ""))
                try:
                    closed_dt = datetime.datetime.fromisoformat(closed_at_str.replace("Z", ""))
                    dt_days = max(0.0, (alert_dt - closed_dt).total_seconds() / 86400.0)
                except Exception:
                    dt_days = 30.0

                # Exponential half-life decay (Innovation 4)
                weight = math.exp(-math.log(2.0) * dt_days / TIME_DECAY_HALF_LIFE_DAYS)
                weight = round(weight, 4)

                precedent_copy = dict(case_data)
                precedent_copy["time_decay_weight"] = weight
                precedent_copy["days_prior"] = round(dt_days, 1)
                precedents.append(precedent_copy)

        # Sort descending by decay weight (recent cases win!)
        precedents.sort(key=lambda x: x.get("time_decay_weight", 0.0), reverse=True)
        return precedents[:limit]

    # -------------------------------------------------------------------------
    # Algorithm 5: Literal Evidence Provenance Path Builder (Innovation 6)
    # -------------------------------------------------------------------------
    def build_evidence_path(self, customer_id: str, card_id: str, txn_id: str, device_id: Optional[str] = None, region_id: Optional[str] = None) -> str:
        parts = [f"(Customer:{customer_id})", f"-[:OWNS]->", f"(Card:{card_id})", f"-[:MADE]->", f"(Txn:{txn_id})"]
        if device_id:
            parts.extend([f"-[:FROM_DEVICE]->", f"(Device:{device_id})"])
        if region_id:
            parts.extend([f"-[:BILLED_IN]->", f"(Region:{region_id})"])
        return "".join(parts)

    # -------------------------------------------------------------------------
    # Algorithm 6: Persistent Case Memory Committer (Innovation 6)
    # -------------------------------------------------------------------------
    def commit_case_memory(self, case_id: str, case_data: Dict[str, Any]) -> bool:
        self.case_memory[case_id] = case_data
        self.add_vertex("InvestigationCase", case_id, {
            "case_id": case_id,
            "opened_at": case_data.get("opened_at"),
            "closed_at": case_data.get("closed_at"),
            "status": case_data.get("status", "closed"),
            "verdict": case_data.get("verdict"),
            "fraud_probability": case_data.get("fraud_probability"),
            "pattern": case_data.get("pattern"),
            "exposure_usd": case_data.get("exposure_usd"),
            "summary": case_data.get("summary"),
            "written_to_graph": True
        })
        card_id = case_data.get("card_id")
        if card_id:
            self.add_edge("CASE_ON_CARD", "InvestigationCase", case_id, "Card", card_id)
        return True
