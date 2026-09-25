import json

import pytest
import requests

from scripts import load_hhgoa_fraud as loader_module


class RecordingLoader:
    def __init__(self, batch_size=2):
        self.batch_size = batch_size
        self.vertex_calls = []
        self.edge_calls = []

    def post_vertices(self, vertex_type, batch, stage, batch_number):
        self.vertex_calls.append((vertex_type, batch, stage, batch_number))

    def post_edges(self, from_type, edge_type, to_type, batch, stage, batch_number):
        self.edge_calls.append((from_type, edge_type, to_type, batch, stage, batch_number))


def _response(status_code):
    response = requests.Response()
    response.status_code = status_code
    response._content = b""
    response.url = "https://example.invalid/restpp/graph/HHGOA_Fraud"
    return response


def _json_response(body):
    response = _response(200)
    response._content = json.dumps(body).encode("utf-8")
    response.headers["Content-Type"] = "application/json"
    return response


def test_vertex_and_edge_stages_batch_and_resume_from_checkpoint(tmp_path, capsys):
    path = tmp_path / "checkpoint.json"
    signature = {"batch_size": 2, "write_limit": None}
    checkpoint = loader_module.ProgressCheckpoint(path, signature)
    values = [(f"id-{i}", {"value": i}) for i in range(5)]
    fake = RecordingLoader(batch_size=2)

    loader_module._run_vertex_stage(fake, checkpoint, "vertices:Transaction", values)
    assert [len(call[1]) for call in fake.vertex_calls] == [2, 2, 1]

    resumed = loader_module.ProgressCheckpoint(path, signature)
    loader_module._run_vertex_stage(fake, resumed, "vertices:Transaction", values)
    assert len(fake.vertex_calls) == 3
    saved = json.loads(path.read_text(encoding="utf-8"))
    assert saved["completed"]["vertices:Transaction"] == 3
    assert "checkpoint=skipped" in capsys.readouterr().out

    edge_records = [
        (f"customer-{i}", {"target_id": f"txn-{i}", "attributes": {"amount": i}})
        for i in range(5)
    ]
    loader_module._run_edge_stage(
        fake, resumed, "edges:init", "INITIATED", "Transaction", edge_records
    )
    assert [sum(map(len, call[3].values())) for call in fake.edge_calls] == [2, 2, 1]


def test_http_499_retries_with_finite_exponential_backoff(monkeypatch, capsys):
    responses = iter([499, 499, 200])
    sleeps = []

    def post(*args, **kwargs):
        return _response(next(responses))

    monkeypatch.setattr(loader_module.requests, "post", post)
    monkeypatch.setattr(loader_module.time, "sleep", sleeps.append)
    client = loader_module.RestppLoader("https://example.invalid", "secret-value", 2)

    client.post_vertices("Transaction", {"T1": {"transaction_id": "T1"}}, "transactions", 4)

    assert sleeps == [1, 2]
    output = capsys.readouterr().out
    assert "stage=transactions batch=4" in output
    assert "retries=2" in output
    assert "secret-value" not in output


def test_http_499_failure_reports_stage_batch_and_stops_after_max_retries(
    monkeypatch, capsys
):
    calls = []
    sleeps = []

    def post(*args, **kwargs):
        calls.append(1)
        return _response(499)

    monkeypatch.setattr(loader_module.requests, "post", post)
    monkeypatch.setattr(loader_module.time, "sleep", sleeps.append)
    client = loader_module.RestppLoader("https://example.invalid", "secret-value", 1)

    with pytest.raises(loader_module.LoaderStageError, match="transactions.*batch 7"):
        client.post_vertices("Transaction", {"T1": {"transaction_id": "T1"}}, "transactions", 7)

    assert len(calls) == loader_module.MAX_RETRIES + 1
    assert sleeps == [1, 2, 4]
    output = capsys.readouterr().out
    assert "records_successfully_submitted=0 failures=1" in output
    assert "secret-value" not in output


def test_http_success_with_restpp_error_body_is_not_counted_as_submitted(monkeypatch):
    monkeypatch.setattr(
        loader_module.requests,
        "post",
        lambda *args, **kwargs: _json_response({"error": True, "message": "invalid attribute"}),
    )
    client = loader_module.RestppLoader("https://example.invalid", "secret-value", 1)

    with pytest.raises(loader_module.LoaderStageError, match="invalid attribute"):
        client.post_vertices("Transaction", {"T1": {"transaction_id": "T1"}}, "transactions", 2)


def test_http_success_with_partial_restpp_acceptance_fails(monkeypatch):
    monkeypatch.setattr(
        loader_module.requests,
        "post",
        lambda *args, **kwargs: _json_response(
            {
                "error": False,
                "results": [
                    {
                        "accepted_vertices": 0,
                        "affected_vertices": 0,
                        "accepted_edges": 0,
                    }
                ],
            }
        ),
    )
    client = loader_module.RestppLoader("https://example.invalid", "secret-value", 1)

    with pytest.raises(loader_module.LoaderStageError, match="accepted/affected 0 vertices"):
        client.post_vertices("Transaction", {"T1": {"transaction_id": "T1"}}, "transactions", 3)


def test_existing_upserted_vertices_count_as_successful_submission(monkeypatch, capsys):
    monkeypatch.setattr(
        loader_module.requests,
        "post",
        lambda *args, **kwargs: _json_response(
            {
                "error": False,
                "results": [
                    {
                        "accepted_vertices": 0,
                        "affected_vertices": 1,
                        "accepted_edges": 0,
                    }
                ],
            }
        ),
    )
    client = loader_module.RestppLoader("https://example.invalid", "secret-value", 1)

    client.post_vertices("Customer", {"C1": {"customer_id": "C1"}}, "customers", 1)

    assert "records_successfully_submitted=1" in capsys.readouterr().out


def test_checkpoint_retries_windows_replace_permission_error(tmp_path, monkeypatch):
    target = tmp_path / "checkpoint.json"
    checkpoint = loader_module.ProgressCheckpoint(target, {"batch_size": 1})
    original_replace = loader_module.os.replace
    attempts = []

    def replace(source, destination):
        attempts.append(1)
        if len(attempts) == 1:
            raise PermissionError("temporary file lock")
        original_replace(source, destination)

    monkeypatch.setattr(loader_module.os, "replace", replace)
    monkeypatch.setattr(loader_module.time, "sleep", lambda _: None)

    checkpoint.mark_completed("transactions", 1)

    assert len(attempts) == 2
    assert json.loads(target.read_text(encoding="utf-8"))["completed"]["transactions"] == 1


def test_full_load_batches_fraud_cases_and_edges(tmp_path, monkeypatch):
    (tmp_path / "transactions.csv").write_text(
        "TransactionID,customer_id,TransactionAmt,ts\n"
        "T1,C1,10,2020-01-01\n"
        "T2,C2,20,2020-01-02\n"
        "T3,C3,30,2020-01-03\n",
        encoding="utf-8",
    )
    (tmp_path / "case_pack.csv").write_text(
        "case_id,customer_id,opened_at,trigger_type,risk_score\n"
        "CASE-1,C1,2020-01-01,risk,0.8\n",
        encoding="utf-8",
    )
    (tmp_path / "closed_cases_history.csv").write_text(
        "case_id,customer_id,opened_at,pattern,outcome\n"
        "HIST-1,C2,2020-01-02,pattern-a,fraud\n"
        "HIST-2,C3,2020-01-03,pattern-b,review\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(loader_module, "ROOT", tmp_path)
    fake = RecordingLoader(batch_size=2)
    checkpoint = loader_module.ProgressCheckpoint(
        tmp_path / "progress.json", {"batch_size": 2, "write_limit": None}
    )

    loader_module.load_data(fake, checkpoint=checkpoint)

    fraud_case_batches = [call for call in fake.vertex_calls if call[0] == "FraudCase"]
    assert [len(call[1]) for call in fraud_case_batches] == [2, 1]
    assert all(set(record) == {"customer_id"} for kind, batch, *_ in fake.vertex_calls if kind == "Customer" for record in batch.values())
    assert all(set(record) == {"transaction_id"} for kind, batch, *_ in fake.vertex_calls if kind == "Transaction" for record in batch.values())
    assert all(set(record) == {"case_id"} for _, batch, *_ in fraud_case_batches for record in batch.values())
    initiated_batches = [call for call in fake.edge_calls if call[1] == "INITIATED"]
    involved_batches = [call for call in fake.edge_calls if call[1] == "INVOLVED_IN"]
    assert [sum(map(len, call[3].values())) for call in initiated_batches] == [2, 1]
    assert [sum(map(len, call[3].values())) for call in involved_batches] == [2, 1]
    assert all(not attrs for calls in (initiated_batches, involved_batches) for call in calls for targets in call[3].values() for attrs in targets.values())
    assert json.loads((tmp_path / "progress.json").read_text(encoding="utf-8"))["complete"]
