"""
Unified Graph Adapter
Provides seamless abstraction across Live TigerGraph and In-Memory Graph Simulator.
"""

from typing import Dict, List, Any, Optional
from src.config import GRAPH_BACKEND_MODE
from src.graph.in_memory_engine import InMemoryGraphEngine
from src.graph.tigergraph_client import TigerGraphClient
from src.graph.policy_graph import PolicyGraphEngine
from src.data.real_data import STORE
from src.rag.vector_store import LightweightVectorStore
from src.graph.tigergraph_mcp_client import TigerGraphMCPClient


class GraphAdapter:
    def __init__(self, mode: str = GRAPH_BACKEND_MODE, mcp_client: Any = None):
        self.mode = mode
        self.in_memory = InMemoryGraphEngine()
        self.policy_graph = PolicyGraphEngine()
        self.tg_client = TigerGraphClient()
        self.is_live = False
        self.vector_store = LightweightVectorStore()
        self._vectors_loaded = False
        self.mcp_client = mcp_client
        self.is_mcp = mode == "mcp"

        if self.is_mcp:
            self.mcp_client = self.mcp_client or TigerGraphMCPClient()
            self.is_live = True
        elif self.mode == "tigergraph":
            self.is_live = self.tg_client.check_connection()

    def get_backend_info(self) -> Dict[str, Any]:
        return {
            "mode": self.mode,
            "is_live_connected": self.is_live,
            "engine": "TigerGraph Savanna" if self.is_live else "TigerGraph Fast Emulation Engine (In-Memory)"
        }

    # Proxy query calls
    def query_card_testing(self, card_id: str, window_hours: int = 48) -> Dict[str, Any]:
        if self.is_mcp:
            return self._mcp_signal_unavailable(
                "card_testing",
                "The deployed graph does not expose transaction amount and timestamp attributes.",
            )
        if self.is_live:
            res = self.tg_client.run_gsql_query("query_card_testing", {"card_id": card_id, "window_hours": window_hours})
            if "error" not in res:
                return res
        return self.in_memory.query_card_testing(card_id, window_hours)

    def query_device_ring_centrality(self, device_id: str, window_days: int = 60) -> Dict[str, Any]:
        if self.is_mcp:
            return self._mcp_signal_unavailable(
                "device_ring",
                "The deployed graph does not expose device-profile vertices or attributes.",
            )
        if self.is_live:
            res = self.tg_client.run_gsql_query("query_device_ring_centrality", {"device_id": device_id, "window_days": window_days})
            if "error" not in res:
                return res
        return self.in_memory.query_device_ring_centrality(device_id, window_days)

    def query_out_of_region(self, customer_id: str, txn_id: str) -> Dict[str, Any]:
        if self.is_mcp:
            return self._mcp_signal_unavailable(
                "out_of_region",
                "The deployed graph does not expose billing-region or transaction-history attributes.",
            )
        if self.is_live:
            res = self.tg_client.run_gsql_query("query_out_of_region", {"customer_id": customer_id, "txn_id": txn_id})
            if "error" not in res:
                return res
        return self.in_memory.query_out_of_region(customer_id, txn_id)

    def query_similar_closed_cases(self, pattern: str, alert_date_str: str, limit: int = 3) -> List[Dict[str, Any]]:
        if self.is_mcp:
            return []
        self._load_vectors()
        query = f"pattern {pattern} alert_date {alert_date_str}"
        results = self.vector_store.search(query, limit)
        if results:
            return results
        return self.in_memory.query_similar_closed_cases(pattern, alert_date_str, limit)

    def _load_vectors(self) -> None:
        if self._vectors_loaded:
            return
        closed_cases = STORE.get_closed_cases()
        for case in closed_cases:
            self.vector_store.add(
                case,
                " ".join(str(case.get(field, "")) for field in (
                    "outcome", "pattern", "actions_taken", "analyst_notes", "txn_ids"
                )),
            )
            graph_case = self.in_memory.get_vertex("ClosedCase", case.get("case_id", ""))
            if graph_case is not None:
                graph_case["embedding_dimensions"] = self.vector_store.dimensions
                graph_case["embedding_indexed"] = True
        self._vectors_loaded = True

    def get_transaction(self, txn_id: str) -> Optional[Dict[str, Any]]:
        """Return a transaction from the local graph or live TigerGraph."""
        if self.is_mcp:
            return self.mcp_client.get_transaction(str(txn_id))
        local = self.in_memory.get_vertex("Transaction", str(txn_id))
        if local:
            return local
        if self.is_live:
            result = self.tg_client.get_vertex("Transaction", str(txn_id))
            if result:
                return result
        return None

    def get_customer(self, customer_id: str) -> Optional[Dict[str, Any]]:
        if self.is_mcp:
            return self.mcp_client.get_customer(str(customer_id))
        return self.in_memory.get_vertex("Customer", str(customer_id))

    def get_customer_transactions(self, customer_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        if self.is_mcp:
            return self.mcp_client.get_customer_transactions(str(customer_id), limit)
        return []

    def get_customer_cases(self, customer_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        if self.is_mcp:
            return self.mcp_client.get_customer_cases(str(customer_id), limit)
        return []

    def get_transaction_neighbors(self, txn_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        if self.is_mcp:
            return self.mcp_client.get_transaction_neighbors(str(txn_id), limit)
        return []

    @staticmethod
    def _mcp_signal_unavailable(signal: str, reason: str) -> Dict[str, Any]:
        return {
            "available": False,
            "source": "tigergraph_mcp",
            "signal": signal,
            "reason": reason,
        }

    def close(self) -> None:
        if self.is_mcp and self.mcp_client is not None:
            self.mcp_client.close()

    def evaluate_policy_graph(self, **kwargs) -> Dict[str, Any]:
        return self.policy_graph.evaluate_policy(**kwargs)

    def commit_case_memory(self, case_id: str, case_data: Dict[str, Any]) -> bool:
        committed = self.in_memory.commit_case_memory(case_id, case_data)
        if self.is_live and not self.is_mcp:
            self.tg_client.upsert_vertex("InvestigationCase", case_id, {
                "case_id": case_id,
                "status": case_data.get("status", "closed"),
                "verdict": case_data.get("verdict", ""),
                "fraud_probability": case_data.get("fraud_probability", 0.0),
                "pattern": case_data.get("pattern", ""),
                "exposure_usd": case_data.get("exposure_usd", 0.0),
                "summary": case_data.get("summary", ""),
                "written_to_graph": True,
            })
        return committed
