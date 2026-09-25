from types import SimpleNamespace

import pytest

from src.graph.graph_adapter import GraphAdapter
from src.agents.base_agent import AgentContext
from src.agents.detective_agent import DetectiveAgent, _neighbor_identity
from src.graph.tigergraph_mcp_client import (
    EXPECTED_EDGES,
    EXPECTED_VERTICES,
    REQUIRED_READ_TOOLS,
    TigerGraphMCPClient,
    TigerGraphMCPError,
)


class FakeMCPClient:
    def __init__(self):
        self.calls = []

    def get_schema(self):
        self.calls.append(("schema",))
        return {"vertices": sorted(EXPECTED_VERTICES), "edges": sorted(EXPECTED_EDGES)}

    def get_customer(self, customer_id):
        self.calls.append(("customer", customer_id))
        return {"customer_id": customer_id}

    def get_transaction(self, transaction_id):
        self.calls.append(("transaction", transaction_id))
        return {"transaction_id": transaction_id, "amount": 10.5, "timestamp": "2016-01-01"}

    def get_customer_transactions(self, customer_id, limit=100):
        self.calls.append(("transactions", customer_id, limit))
        return [{"vertex_type": "Transaction", "vertex_id": "T1"}]

    def get_customer_cases(self, customer_id, limit=100):
        self.calls.append(("cases", customer_id, limit))
        return [{"vertex_type": "FraudCase", "vertex_id": "C1"}]

    def get_transaction_neighbors(self, transaction_id, limit=100):
        self.calls.append(("neighbors", transaction_id, limit))
        return [{"edge_type": "RELATED_TO", "vertex_type": "Transaction", "vertex_id": "T2"}]


@pytest.mark.parametrize(
    "text",
    [
        '{"ok": true}',
        '```json\n{"ok": true}\n```',
        '```\n{"ok": true}\n```',
        '```json\n{"ok": true}\n```\n\n**Suggestions:**\n1. Another MCP operation',
    ],
)
def test_decode_result_parses_plain_and_fenced_json(text):
    result = SimpleNamespace(
        content=[SimpleNamespace(text=text, type="text")],
        structuredContent=None,
    )
    assert TigerGraphMCPClient._decode_result(result) == {"ok": True}


def test_decode_result_preserves_non_json_text_after_trimming():
    result = SimpleNamespace(
        content=[SimpleNamespace(text="  not json \n", type="text")],
        structuredContent=None,
    )
    assert TigerGraphMCPClient._decode_result(result) == "not json"


def test_decode_result_prefers_structured_content():
    structured = {"success": True, "data": {"value": 1}}
    result = SimpleNamespace(
        content=[SimpleNamespace(text='{"ignored": true}', type="text")],
        structuredContent=structured,
    )
    assert TigerGraphMCPClient._decode_result(result) is structured


def test_schema_validation_requires_exact_deployed_schema():
    schema = {"vertices": sorted(EXPECTED_VERTICES), "edges": sorted(EXPECTED_EDGES)}
    assert TigerGraphMCPClient.validate_schema(schema) == schema
    assert TigerGraphMCPClient.validate_schema(
        {"data": {"schema": {"VertexTypes": [{"name": name} for name in EXPECTED_VERTICES],
                              "EdgeTypes": [{"name": name} for name in EXPECTED_EDGES]}}}
    )
    live_schema = {
        "data": {
            "graph_name": "HHGOA_Fraud",
            "schema": {
                "GraphName": "HHGOA_Fraud",
                "VertexTypes": [{"Name": name} for name in EXPECTED_VERTICES],
                "EdgeTypes": [{"Name": name} for name in EXPECTED_EDGES],
                "UDTs": [],
            },
            "vertex_type_count": len(EXPECTED_VERTICES),
            "edge_type_count": len(EXPECTED_EDGES),
        }
    }
    assert TigerGraphMCPClient.validate_schema(live_schema) == live_schema["data"]["schema"]
    with pytest.raises(TigerGraphMCPError):
        TigerGraphMCPClient.validate_schema({"vertices": [], "edges": []})


def test_required_tools_are_read_only_allowlist():
    assert REQUIRED_READ_TOOLS == {
        "tigergraph__get_graph_schema",
        "tigergraph__get_node",
        "tigergraph__get_neighbors",
    }
    assert not any(name.startswith("tigergraph__add_") for name in REQUIRED_READ_TOOLS)


def test_graph_adapter_normalizes_all_mcp_reads_without_mutation_calls():
    client = FakeMCPClient()
    adapter = GraphAdapter(mode="mcp", mcp_client=client)

    assert adapter.get_customer("C1") == {"customer_id": "C1"}
    assert adapter.get_transaction("T1")["transaction_id"] == "T1"
    assert adapter.get_customer_transactions("C1") == [
        {"vertex_type": "Transaction", "vertex_id": "T1"}
    ]
    assert adapter.get_customer_cases("C1") == [
        {"vertex_type": "FraudCase", "vertex_id": "C1"}
    ]
    assert adapter.get_transaction_neighbors("T1")[0]["edge_type"] == "RELATED_TO"
    assert not any(call[0] in {"add_node", "add_edge", "delete_node", "delete_edge"} for call in client.calls)


def test_detective_uses_mcp_transaction_and_relationship_evidence():
    client = FakeMCPClient()
    context = AgentContext(
        case_id="CASE-1",
        opened_at="2016-01-01",
        trigger_type="risk_score",
        customer_id="C1",
        card_id="legacy-card",
        flagged_txn_id="T1",
    )

    result = DetectiveAgent().run(context, GraphAdapter(mode="mcp", mcp_client=client))

    signals = {item["signal"] for item in result.evidence}
    assert "graph_transaction" in signals
    assert "graph_relationship" in signals
    assert any("INITIATED" in path for path in result.provenance_paths)


def test_detective_normalizes_native_tigergraph_neighbor_vertex_fields():
    neighbor = _neighbor_identity(
        {"v_id": "T2", "v_type": "Transaction", "attributes": {"transaction_id": "T2"}}
    )
    assert neighbor["vertex_id"] == "T2"
    assert neighbor["vertex_type"] == "Transaction"
