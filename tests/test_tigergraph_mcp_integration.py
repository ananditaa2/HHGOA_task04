from types import SimpleNamespace

import pytest

from src.graph.graph_adapter import GraphAdapter
from src.agents.base_agent import AgentContext
from src.agents.detective_agent import DetectiveAgent, _neighbor_identity
from src.agents.conflict_evaluator import ConflictEvaluatorAgent
from src.agents.critic_agent import CriticAgent
from src.agents.evidence_simulator import EvidenceSimulatorAgent
from src.agents.policy_engine import PolicyEngineAgent
from src.data.real_data import STORE
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


class IdOnlyMCPClient(FakeMCPClient):
    def get_transaction(self, transaction_id):
        self.calls.append(("transaction", transaction_id))
        return {"transaction_id": transaction_id}

    def get_customer_transactions(self, customer_id, limit=100):
        self.calls.append(("transactions", customer_id, limit))
        return [{
            "v_id": "T2",
            "v_type": "Transaction",
            "attributes": {"transaction_id": "T2"},
        }]


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


def test_mcp_downstream_stages_do_not_read_local_graph_or_csv(monkeypatch):
    client = IdOnlyMCPClient()
    adapter = GraphAdapter(mode="mcp", mcp_client=client)

    def forbidden(*args, **kwargs):
        raise AssertionError("MCP mode must not read local graph/CSV data or invoke GSQL")

    monkeypatch.setattr(adapter.tg_client, "run_gsql_query", forbidden)
    monkeypatch.setattr(adapter.in_memory, "query_out_of_region", forbidden)
    monkeypatch.setattr(STORE, "get_card_history", forbidden)
    monkeypatch.setattr(STORE, "get_flagged_txn", forbidden)

    context = AgentContext(
        case_id="CASE-MCP",
        opened_at="2016-01-01",
        trigger_type="customer_report",
        trigger_details={"trigger_text": "Customer reported: I never made this purchase."},
        customer_id="C1",
        card_id="K1",
        flagged_txn_id="T1",
    )

    context = DetectiveAgent().run(context, adapter)
    context = ConflictEvaluatorAgent().run(context, adapter)
    assert context.uncertainty_level == "high"
    context = CriticAgent().run(context, adapter)
    context = PolicyEngineAgent().determine_initial_phase(context, adapter)
    context = EvidenceSimulatorAgent().run(context, adapter)

    unavailable = {
        evidence["value"]["signal"]
        for evidence in context.evidence
        if evidence.get("signal") == "graph_signal_unavailable"
    }
    assert {
        "transaction_amount",
        "transaction_timestamp",
        "transaction_risk_score",
        "out_of_region",
        "recurring_charge_history",
        "customer_amount_history",
    } <= unavailable
    assert context.simulated_responses[0]["status"] == "denied_transaction"
    assert context.simulated_responses[0]["responder"] == "case_record"
    assert "no customer was contacted" in context.simulated_responses[0]["message"]
    assert context.devil_advocate_verdict.startswith("UNABLE_TO_ASSESS_FROM_GRAPH")
    assert all(item.get("source") != "card_history" for item in context.evidence)


def test_mcp_adapter_never_runs_legacy_graph_queries_or_writes(monkeypatch):
    adapter = GraphAdapter(mode="mcp", mcp_client=FakeMCPClient())

    def forbidden(*args, **kwargs):
        raise AssertionError("MCP mode must not invoke the legacy TigerGraph client or local graph")

    monkeypatch.setattr(adapter.tg_client, "run_gsql_query", forbidden)
    monkeypatch.setattr(adapter.tg_client, "upsert_vertex", forbidden)
    monkeypatch.setattr(adapter.in_memory, "query_card_testing", forbidden)
    monkeypatch.setattr(adapter.in_memory, "query_device_ring_centrality", forbidden)
    monkeypatch.setattr(adapter.in_memory, "query_out_of_region", forbidden)

    for result in (
        adapter.query_card_testing("K1"),
        adapter.query_device_ring_centrality("D1"),
        adapter.query_out_of_region("C1", "T1"),
    ):
        assert result["available"] is False
        assert result["source"] == "tigergraph_mcp"
    assert adapter.query_similar_closed_cases("pattern", "2016-01-01") == []
    assert adapter.commit_case_memory("CASE-MCP", {"verdict": "SUSPICIOUS"}) is True
    assert "CASE-MCP" in adapter.in_memory.case_memory
