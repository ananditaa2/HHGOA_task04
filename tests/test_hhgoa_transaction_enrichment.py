import pytest

from scripts import enrich_hhgoa_transaction as enrichment


class RecordingWriter:
    def __init__(self):
        self.payloads = []

    def upsert(self, payload):
        self.payloads.append(payload)


def test_transaction_attributes_preserve_source_mapping_and_omit_empty_values():
    attrs = enrichment.transaction_attributes(
        {
            "TransactionID": "3000093",
            "TransactionAmt": "17.17",
            "ts": "2016-07-02 01:01:12",
            "risk_score": "0.31",
            "channel": "online",
            "ProductCD": "C",
        },
        {
            "DeviceType": "mobile",
            "DeviceInfo": "",
            "id_15": "Unknown",
            "id_28": "New",
            "id_31": "mobile safari 11.0",
        },
    )

    assert attrs == {
        "transaction_id": "3000093",
        "amount": 17.17,
        "ts": "2016-07-02 01:01:12",
        "risk_score": 0.31,
        "channel": "online",
        "product_cd": "C",
        "device_type": "mobile",
        "id_15": "Unknown",
        "id_28": "New",
        "id_31": "mobile safari 11.0",
    }


def test_enrichment_links_transaction_and_customer_case_without_claiming_flagged_id(
    tmp_path, monkeypatch
):
    (tmp_path / "transactions.csv").write_text(
        "TransactionID,customer_id,TransactionAmt,ts,risk_score,channel,ProductCD\n"
        "3000093,C11923,17.17,2016-07-02 01:01:12,0.31,online,C\n",
        encoding="utf-8",
    )
    (tmp_path / "identity.csv").write_text(
        "TransactionID,DeviceType,DeviceInfo,id_15,id_28,id_31\n"
        "3000093,mobile,,Unknown,New,mobile safari 11.0\n",
        encoding="utf-8",
    )
    (tmp_path / "case_pack.csv").write_text(
        "case_id,flagged_txn_id,customer_id\nHHG-011,3583368,C11923\n",
        encoding="utf-8",
    )
    monkeypatch.setattr(enrichment, "ROOT", tmp_path)
    writer = RecordingWriter()

    result = enrichment.enrich("3000093", writer, "HHG-011")

    assert result == {
        "transaction_id": "3000093",
        "customer_id": "C11923",
        "attributes_written": [
            "amount",
            "channel",
            "device_type",
            "id_15",
            "id_28",
            "id_31",
            "product_cd",
            "risk_score",
            "transaction_id",
            "ts",
        ],
        "case_id_linked": "HHG-011",
    }
    assert writer.payloads[0]["vertices"]["Transaction"]["3000093"]["amount"] == {
        "value": 17.17
    }
    assert writer.payloads[1] == {
        "edges": {
            "Customer": {
                "C11923": {
                    "INITIATED": {"Transaction": {"3000093": {}}}
                }
            }
        }
    }
    assert writer.payloads[2]["vertices"]["FraudCase"]["HHG-011"] == {
        "case_id": {"value": "HHG-011"}
    }
    assert writer.payloads[3]["edges"]["Customer"]["C11923"]["INVOLVED_IN"] == {
        "FraudCase": {"HHG-011": {}}
    }
    assert all("3583368" not in repr(payload) for payload in writer.payloads)


def test_enrichment_refuses_case_for_another_customer(tmp_path, monkeypatch):
    (tmp_path / "transactions.csv").write_text(
        "TransactionID,customer_id,TransactionAmt,ts,risk_score,channel,ProductCD\n"
        "T1,C1,1.0,2020-01-01 00:00:00,0.1,online,C\n",
        encoding="utf-8",
    )
    (tmp_path / "identity.csv").write_text("TransactionID\n", encoding="utf-8")
    (tmp_path / "case_pack.csv").write_text(
        "case_id,flagged_txn_id,customer_id\nCASE-1,T2,C2\n", encoding="utf-8"
    )
    monkeypatch.setattr(enrichment, "ROOT", tmp_path)

    with pytest.raises(ValueError, match="not transaction customer"):
        enrichment.enrich("T1", RecordingWriter(), "CASE-1")
