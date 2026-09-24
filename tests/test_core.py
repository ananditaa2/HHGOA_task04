from src.agents.coordinator import InvestigationCoordinator
from src.data.real_data import STORE
from src.graph.graph_adapter import GraphAdapter
from src.mcp.tigergraph_mcp import TigerGraphMCPServer
from src.utils.schema_validator import CaseSchemaValidator


def test_schema_validator_enforces_sar_and_verdict_rules():
    base = {
        "case_id": "HHG-TEST",
        "evidence_requests": [],
        "stop_reason": "test",
        "tool_calls": 0,
        "tokens": 0,
        "latency_s": 0.1,
        "case": {
            "status": "closed_fraud", "verdict": "fraud", "fraud_probability": 0.9,
            "pattern": "card_testing", "pattern_description": "",
            "affected_txn_ids": ["T1"], "first_suspicious_txn_id": "T1",
            "connected_card_ids": [], "connected_device_profiles": [],
            "exposure_usd": 1500.0, "evidence": [], "similar_prior_cases": [],
            "summary": "s", "written_to_graph": True, "graph_case_id": "CASE-2016-9999",
        },
        "next_best_actions": {"initial": [], "final": [
            {"action": "FILE_REPORT", "route": "L2", "reason": "R9 exposure $1500 exceeds the $1000 policy threshold."}
        ], "what_changed": "nothing"},
        "sar": {"file": True, "reason": "threshold", "narrative": "", "subjects": ["C1"],
                "total_amount_usd": 1500.0, "activity_dates": ["2016-12-01", "2016-12-05"]},
    }
    valid, errors = CaseSchemaValidator.validate_case(base)
    assert not valid
    assert any("narrative" in e for e in errors)

    base["sar"]["narrative"] = "A full SAR narrative with sufficient word count for the README six-to-twelve sentence self-standing requirement, describing the observed card testing cascade and the connected exposure."
    base["case"]["exposure_usd"] = 0.0
    valid, errors = CaseSchemaValidator.validate_case(base)
    assert not valid
    assert any("exposure_usd" in e for e in errors)


def test_narrative_agent_falls_back_without_llm(monkeypatch):
    from src.agents.narrative_agent import NarrativeAgent
    monkeypatch.setenv("NARRATIVE_LLM_ENABLED", "true")
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    text = NarrativeAgent().generate({"case": {"verdict": "fraud", "pattern": "card_testing",
                                               "exposure_usd": 123.45, "summary": "demo"}})
    assert "fraud" in text and "card_testing" in text


def test_qa_audit_passes_over_generated_case_pack():
    from scripts.qa_audit import audit_case_pack
    assert audit_case_pack() is True


def test_real_store_has_benchmark_data():
    assert len(STORE.get_case_pack()) == 20
    assert len(STORE.get_closed_cases()) == 5565
    assert STORE.get_flagged_txn(STORE.get_case_pack()[0]["flagged_txn_id"])


def test_vector_precedents_index_all_closed_cases():
    adapter = GraphAdapter()
    results = adapter.query_similar_closed_cases("card_not_present_fraud", "2016-12-31T00:00:00", 3)
    assert len(adapter.vector_store) == 5565
    assert len(results) == 3
    assert "vector_similarity" in results[0]


def test_coordinator_emits_valid_answer():
    result = InvestigationCoordinator(GraphAdapter()).investigate(STORE.get_case_pack()[0])
    assert result["case_id"] == STORE.get_case_pack()[0]["case_id"]
    assert result["case"]["written_to_graph"] is True
    assert result["analyst_narrative"]
    valid, errors = CaseSchemaValidator.validate_case(result)
    assert valid, errors


def test_all_mcp_tools_are_callable():
    server = TigerGraphMCPServer(GraphAdapter())
    tools = {tool["name"] for tool in server.list_tools()}
    assert len(tools) == 7
    assert server.call_tool("tigergraph_get_schema", {})["graph_name"] == "FraudGraph"
    assert server.call_tool("tigergraph_get_tool_info", {"tool_name": "tigergraph_get_schema"})["name"] == "tigergraph_get_schema"
    assert server.call_tool("tigergraph_execute_gsql", {"command": "PRINT 1"})["status"] == "EXECUTED"

    upsert = server.call_tool("tigergraph_upsert_vertex", {
        "vertex_type": "Customer", "vertex_id": "TEST", "attributes": {"customer_id": "TEST"}
    })
    assert upsert["status"] == "SUCCESS"
    neighbors = server.call_tool("tigergraph_get_neighbors", {
        "vertex_type": "Customer", "vertex_id": "TEST"
    })
    assert neighbors["vertex"] == "Customer:TEST"
    assert server.call_tool("tigergraph_run_installed_query", {
        "query_name": "similar_precedents", "params": {"pattern": "card_testing", "limit": 1}
    })["results"]
    assert server.call_tool("tigergraph_get_neighbors", {
        "vertex_type": "Transaction", "vertex_id": "not-present"
    })["neighbors_count"] == 0
    assert server.call_tool("tigergraph_upsert_edge", {
        "edge_type": "OWNS", "from_id": "Customer:TEST", "to_id": "Card:TEST-K1"
    })["status"] == "SUCCESS"


def test_deploy_script_supports_dry_run():
    from scripts.deploy_tigergraph import main
    import sys
    original = sys.argv
    try:
        sys.argv = ["deploy_tigergraph", "--dry-run"]
        assert main() == 0
    finally:
        sys.argv = original