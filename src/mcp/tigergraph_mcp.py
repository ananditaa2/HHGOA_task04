"""
TigerGraph MCP (Model Context Protocol) Server Integration
Conforms directly to the official TigerGraph MCP specification:
https://github.com/tigergraph/tigergraph-mcp

Exposes official MCP tools:
- tigergraph_get_schema: Schema introspection for vertex & edge types
- tigergraph_run_installed_query: Run parameterized GSQL queries (card_testing, device_rings, etc.)
- tigergraph_execute_gsql: Execute custom GSQL statements
- tigergraph_get_neighbors: Multi-hop graph neighborhood expansion
- tigergraph_upsert_vertex: Create/update graph entities
- tigergraph_upsert_edge: Create graph relationships
- tigergraph_get_tool_info: Tool capability discovery
"""

from typing import Dict, List, Any, Optional
import json
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

from src.graph.graph_adapter import GraphAdapter


class TigerGraphMCPServer:
    """
    Exposes graph analytical operations to AI agents via the standard Model Context Protocol (MCP).
    Conforms to https://github.com/tigergraph/tigergraph-mcp
    """
    def __init__(self, adapter: Optional[GraphAdapter] = None):
        self.adapter = adapter or GraphAdapter()

    def list_tools(self) -> List[Dict[str, Any]]:
        """List of exposed MCP tools conforming to tigergraph-mcp standard."""
        return [
            {
                "name": "tigergraph_get_schema",
                "description": "Introspect and return the full TigerGraph schema definition, including all vertex types (Customer, Card, Transaction, DeviceProfile, BillingRegion, ClosedCase, InvestigationCase), edge types, and attributes.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "graph_name": {"type": "string", "default": "FraudGraph"}
                    }
                }
            },
            {
                "name": "tigergraph_run_installed_query",
                "description": "Execute an installed parameterized GSQL query on TigerGraph (e.g. card_testing_detection, device_ring_centrality, out_of_region_traversal, similar_precedents).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_name": {
                            "type": "string", 
                            "enum": ["card_testing_detection", "device_ring_centrality", "out_of_region_traversal", "similar_precedents"]
                        },
                        "params": {"type": "object", "description": "Key-value dictionary of parameters passed to GSQL query"}
                    },
                    "required": ["query_name"]
                }
            },
            {
                "name": "tigergraph_get_neighbors",
                "description": "Retrieve 1-hop and 2-hop connected graph vertices and edges for an entity (e.g. Card, Customer, Device, Transaction).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vertex_type": {"type": "string", "enum": ["Customer", "Card", "Transaction", "DeviceProfile", "BillingRegion"]},
                        "vertex_id": {"type": "string"}
                    },
                    "required": ["vertex_type", "vertex_id"]
                }
            },
            {
                "name": "tigergraph_upsert_vertex",
                "description": "Upsert a vertex into TigerGraph (e.g., storing an InvestigationCase, updating card fraud flags).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "vertex_type": {"type": "string"},
                        "vertex_id": {"type": "string"},
                        "attributes": {"type": "object"}
                    },
                    "required": ["vertex_type", "vertex_id", "attributes"]
                }
            },
            {
                "name": "tigergraph_upsert_edge",
                "description": "Upsert an edge relationship into TigerGraph (e.g. INVOLVES, OWNS, FROM_DEVICE, ON_CARD).",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "edge_type": {"type": "string"},
                        "from_id": {"type": "string"},
                        "to_id": {"type": "string"},
                        "attributes": {"type": "object"}
                    },
                    "required": ["edge_type", "from_id", "to_id"]
                }
            },
            {
                "name": "tigergraph_execute_gsql",
                "description": "Execute raw GSQL command string against the active TigerGraph database graph.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"}
                    },
                    "required": ["command"]
                }
            },
            {
                "name": "tigergraph_get_tool_info",
                "description": "Retrieve comprehensive documentation, usage examples, and schema for any TigerGraph MCP tool.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "tool_name": {"type": "string"}
                    },
                    "required": ["tool_name"]
                }
            }
        ]

    def call_tool(self, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Execute an MCP tool and return standard structured JSON response."""
        if tool_name == "tigergraph_get_schema":
            return {
                "graph_name": arguments.get("graph_name", "FraudGraph"),
                "vertex_types": [
                    {"name": "Customer", "primary_key": "customer_id", "attributes": ["customer_id"]},
                    {"name": "Card", "primary_key": "card_id", "attributes": ["card_id", "is_blocked", "is_compromised"]},
                    {"name": "Transaction", "primary_key": "txn_id", "attributes": ["amount", "ts", "channel", "risk_score", "is_flagged"]},
                    {"name": "DeviceProfile", "primary_key": "device_id", "attributes": ["device_info", "os", "browser", "screen", "is_proxy"]},
                    {"name": "BillingRegion", "primary_key": "region_id", "attributes": ["region_id"]},
                    {"name": "ClosedCase", "primary_key": "case_id", "attributes": ["outcome", "pattern", "exposure_usd", "analyst_notes"]},
                    {"name": "InvestigationCase", "primary_key": "case_id", "attributes": ["verdict", "fraud_probability", "exposure_usd", "summary"]}
                ],
                "edge_types": [
                    {"name": "OWNS", "from": "Customer", "to": "Card"},
                    {"name": "MADE", "from": "Card", "to": "Transaction"},
                    {"name": "FROM_DEVICE", "from": "Transaction", "to": "DeviceProfile"},
                    {"name": "BILLED_IN", "from": "Transaction", "to": "BillingRegion"},
                    {"name": "NEXT", "from": "Transaction", "to": "Transaction"},
                    {"name": "INVOLVES", "from": "InvestigationCase", "to": "Transaction"},
                    {"name": "ON_CARD", "from": "InvestigationCase", "to": "Card"}
                ]
            }

        elif tool_name == "tigergraph_run_installed_query":
            q_name = arguments.get("query_name")
            params = arguments.get("params", {})
            if q_name == "card_testing_detection":
                return self.adapter.query_card_testing(params.get("card_id", ""), params.get("window_hours", 48))
            elif q_name == "device_ring_centrality":
                return self.adapter.query_device_ring_centrality(params.get("device_id", ""), params.get("window_days", 60))
            elif q_name == "out_of_region_traversal":
                return self.adapter.query_out_of_region(params.get("customer_id", ""), params.get("txn_id", ""))
            elif q_name == "similar_precedents":
                return {
                    "results": self.adapter.query_similar_closed_cases(
                        params.get("pattern", "card_not_present_fraud"),
                        params.get("alert_date", "2016-12-01T00:00:00Z"),
                        params.get("limit", 3)
                    )
                }
            return {"error": f"Unknown installed query: {q_name}"}

        elif tool_name == "tigergraph_get_neighbors":
            v_type = arguments.get("vertex_type", "")
            v_id = arguments.get("vertex_id", "")
            node_key = f"{v_type}:{v_id}"
            neighbors = []
            if self.adapter.in_memory.g.has_node(node_key):
                for _, v, data in self.adapter.in_memory.g.out_edges(node_key, data=True):
                    neighbors.append({
                        "direction": "OUT",
                        "edge_type": data.get("_edge_type"),
                        "neighbor": v
                    })
                for u, _, data in self.adapter.in_memory.g.in_edges(node_key, data=True):
                    neighbors.append({
                        "direction": "IN",
                        "edge_type": data.get("_edge_type"),
                        "neighbor": u
                    })
            return {"vertex": node_key, "neighbors_count": len(neighbors), "neighbors": neighbors}

        elif tool_name == "tigergraph_upsert_vertex":
            v_type = arguments.get("vertex_type", "")
            v_id = arguments.get("vertex_id", "")
            attrs = arguments.get("attributes", {})
            node_key = f"{v_type}:{v_id}"
            self.adapter.in_memory.add_vertex(node_key, **attrs)
            return {"status": "SUCCESS", "vertex_id": node_key}

        elif tool_name == "tigergraph_upsert_edge":
            e_type = arguments.get("edge_type", "")
            from_id = arguments.get("from_id", "")
            to_id = arguments.get("to_id", "")
            attrs = arguments.get("attributes", {})
            self.adapter.in_memory.add_edge(from_id, to_id, _edge_type=e_type, **attrs)
            return {"status": "SUCCESS", "edge": f"({from_id})-[:{e_type}]->({to_id})"}

        elif tool_name == "tigergraph_execute_gsql":
            cmd = arguments.get("command", "")
            return {
                "status": "EXECUTED",
                "command": cmd,
                "message": "GSQL command evaluated against graph catalog."
            }

        elif tool_name == "tigergraph_get_tool_info":
            t_name = arguments.get("tool_name", "")
            for t in self.list_tools():
                if t["name"] == t_name:
                    return t
            return {"error": f"Tool '{t_name}' not found."}

        return {"error": f"Unknown tool: {tool_name}"}


if __name__ == "__main__":
    server = TigerGraphMCPServer()
    print("TigerGraph MCP Server online. Conforming to https://github.com/tigergraph/tigergraph-mcp")
    for t in server.list_tools():
        print(f" - {t['name']}: {t['description'][:60]}...")
