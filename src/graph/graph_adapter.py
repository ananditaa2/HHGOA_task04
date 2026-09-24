"""
Unified Graph Adapter
Provides seamless abstraction across Live TigerGraph and In-Memory Graph Simulator.
"""

from typing import Dict, List, Any, Optional
from src.config import GRAPH_BACKEND_MODE
from src.graph.in_memory_engine import InMemoryGraphEngine
from src.graph.tigergraph_client import TigerGraphClient
from src.graph.policy_graph import PolicyGraphEngine


class GraphAdapter:
    def __init__(self, mode: str = GRAPH_BACKEND_MODE):
        self.mode = mode
        self.in_memory = InMemoryGraphEngine()
        self.policy_graph = PolicyGraphEngine()
        self.tg_client = TigerGraphClient()
        self.is_live = False

        if self.mode == "tigergraph":
            self.is_live = self.tg_client.check_connection()

    def get_backend_info(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "is_live_connected": self.is_live,
            "engine": "TigerGraph Savanna" if self.is_live else "TigerGraph Fast Emulation Engine (In-Memory)"
        }

    # Proxy query calls
    def query_card_testing(self, card_id: str, window_hours: int = 48) -> Dict[str, Any]:
        if self.is_live:
            res = self.tg_client.run_gsql_query("query_card_testing", {"card_id": card_id, "window_hours": window_hours})
            if "error" not in res:
                return res
        return self.in_memory.query_card_testing(card_id, window_hours)

    def query_device_ring_centrality(self, device_id: str, window_days: int = 60) -> Dict[str, Any]:
        if self.is_live:
            res = self.tg_client.run_gsql_query("query_device_ring_centrality", {"device_id": device_id, "window_days": window_days})
            if "error" not in res:
                return res
        return self.in_memory.query_device_ring_centrality(device_id, window_days)

    def query_out_of_region(self, customer_id: str, txn_id: str) -> Dict[str, Any]:
        if self.is_live:
            res = self.tg_client.run_gsql_query("query_out_of_region", {"customer_id": customer_id, "txn_id": txn_id})
            if "error" not in res:
                return res
        return self.in_memory.query_out_of_region(customer_id, txn_id)

    def query_similar_closed_cases(self, pattern: str, alert_date_str: str, limit: int = 3) -> List[Dict[str, Any]]:
        return self.in_memory.query_similar_closed_cases(pattern, alert_date_str, limit)

    def evaluate_policy_graph(self, **kwargs) -> Dict[str, Any]:
        return self.policy_graph.evaluate_policy(**kwargs)

    def commit_case_memory(self, case_id: str, case_data: Dict[str, Any]) -> bool:
        return self.in_memory.commit_case_memory(case_id, case_data)
