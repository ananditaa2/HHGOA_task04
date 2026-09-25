"""
Graph Detective Agent (Multi-Hop Graph Traversals & Provenance Builder)
Works exclusively on the real CSV-derived graph built by
src.data.real_data.build_graph_from_real_data: card history comes from
transactions.csv, device and proxy signals from identity.csv, and the
device ring from the actual shared (DeviceInfo + proxy) population.
"""

from typing import Dict, List, Any, Optional
from src.agents.base_agent import BaseAgent, AgentContext
from src.data.real_data import STORE, card_ids_for, is_specific_device


CARD_TESTING_MICRO_LIMIT = 5.00
CARD_TESTING_SPIKE_LIMIT = 100.00


def _f(v, default=0.0) -> float:
    try:
        if v is None or v == "":
            return default
        return float(v)
    except (TypeError, ValueError):
        return default


def _vertex_attributes(value: Any) -> Dict[str, Any]:
    if not isinstance(value, dict):
        return {}
    attributes = value.get("attributes")
    if isinstance(attributes, dict):
        return {
            key: item.get("value") if isinstance(item, dict) and "value" in item else item
            for key, item in attributes.items()
        }
    return value


def _neighbor_identity(value: Dict[str, Any]) -> Dict[str, Any]:
    attrs = _vertex_attributes(value)
    return {
        "vertex_type": (
            value.get("vertex_type")
            or value.get("v_type")
            or value.get("type")
            or attrs.get("vertex_type", "")
        ),
        "vertex_id": (
            value.get("vertex_id")
            or value.get("v_id")
            or value.get("id")
            or attrs.get("vertex_id", "")
        ),
        "edge_type": value.get("edge_type") or value.get("edge", ""),
        "attributes": attrs,
    }


class DetectiveAgent(BaseAgent):
    def __init__(self):
        super().__init__(name="GraphDetectiveAgent")

    def run(self, context: AgentContext, graph: Any) -> AgentContext:
        cid = context.customer_id
        kid = context.card_id
        tid = context.flagged_txn_id

        graph_mode = bool(getattr(graph, "is_mcp", False))
        graph_customer: Dict[str, Any] = {}
        graph_initiated: List[Dict[str, Any]] = []
        graph_cases: List[Dict[str, Any]] = []
        graph_neighbors: List[Dict[str, Any]] = []
        if graph_mode:
            graph_customer = _vertex_attributes(graph.get_customer(cid) or {})
            graph_txn = _vertex_attributes(graph.get_transaction(tid) or {})
            if not graph_txn:
                raise RuntimeError(f"TigerGraph MCP returned no Transaction:{tid}")
            graph_initiated = graph.get_customer_transactions(cid, limit=100)
            graph_cases = graph.get_customer_cases(cid, limit=100)
            graph_neighbors = graph.get_transaction_neighbors(tid, limit=100)
            txn_row = {
                "TransactionID": graph_txn.get("transaction_id", tid),
                "TransactionAmt": graph_txn.get("amount", ""),
                "ts": graph_txn.get("timestamp", ""),
            }
            hist = [
                {
                    "TransactionID": _vertex_attributes(item).get("transaction_id", ""),
                    "TransactionAmt": _vertex_attributes(item).get("amount", ""),
                    "ts": _vertex_attributes(item).get("timestamp", ""),
                }
                for item in graph_initiated
            ]
        else:
            # 1. Primary transaction: real row from transactions.csv
            txn_row = STORE.get_flagged_txn(tid) or {}
            hist = STORE.get_card_history(cid)
        txn_amount = _f(txn_row.get("TransactionAmt"), 0.0) or _f(
            context.trigger_details.get("amount"), 0.0)
        risk_score = _f(txn_row.get("risk_score"), _f(
            context.trigger_details.get("risk_score"), 0.5))
        product = txn_row.get("ProductCD", "")
        channel = txn_row.get("channel", "online" if product != "W" else "in_person")
        addr1 = (txn_row.get("addr1") or "").strip()

        # 2. Identity record (device, OS, browser, proxy, New/Found) — real row
        id_row = {} if graph_mode else (STORE.get_identity(tid) or {})
        device_info = (id_row.get("DeviceInfo") or "").strip()
        proxy_flag = (id_row.get("id_23") or "").strip()
        id_15 = (id_row.get("id_15") or "").strip()
        device_profile = STORE._device_str(id_row) if id_row else ""

        # 3. Card history from real transactions.csv rows (spending baseline)
        prior = [r for r in hist if r.get("TransactionID") != tid]
        n_total = len(prior)
        n_online = sum(1 for r in prior if r.get("channel") == "online")
        amounts = [_f(r.get("TransactionAmt")) for r in prior]
        amounts.sort()
        mean_amt = (sum(amounts) / len(amounts)) if amounts else 0.0
        max_amt = amounts[-1] if amounts else 0.0
        p95_amt = amounts[max(0, int(0.95 * len(amounts)) - 1)] if amounts else 0.0
        outside_profile = bool(amounts) and txn_amount > 1.25 * p95_amt

        # --- Card testing scan on the REAL card timeline (README R5) --------
        testing = self._scan_card_testing(prior + ([txn_row] if txn_row else []),
                                          CARD_TESTING_MICRO_LIMIT,
                                          CARD_TESTING_SPIKE_LIMIT)

        # --- Device ring from the real identity population ------------------
        # A ring requires a SPECIFIC device model string + a proxy flag. Generic
        # DeviceInfo values ("Windows", "Trident/7.0", "iOS Device", ...) span
        # hundreds of unrelated customers in identity.csv and are not fingerprints.
        ring_cards: List[Dict[str, str]] = []
        if not graph_mode and device_info and proxy_flag and is_specific_device(device_info):
            ring_cards = STORE.device_neighbors(device_info, proxy_flag, window_days=45)

        # --- Out-of-region check on real addr1 history ----------------------
        region_stats = self._region_stats(hist, addr1, tid)

        evidence_list: List[Dict[str, Any]] = []
        provenance_paths: List[str] = []

        p_base = (
            f"(Customer:{cid})-[:INITIATED]->(Transaction:{tid})"
            if graph_mode
            else f"(Customer:{cid})-[:OWNS]->(Card:{kid})-[:MADE]->(Transaction:{tid})"
        )
        provenance_paths.append(p_base)
        if graph_mode:
            evidence_list.append({
                "source": "tigergraph_mcp",
                "signal": "graph_transaction",
                "value": {
                    "transaction_id": txn_row.get("TransactionID", tid),
                    "amount": txn_amount,
                    "timestamp": txn_row.get("ts", ""),
                },
                "weight": 0.0,
                "path": p_base,
                "description": "Transaction retrieved from HHGOA_Fraud through TigerGraph MCP.",
            })
            if graph_customer:
                evidence_list.append({
                    "source": "tigergraph_mcp",
                    "signal": "graph_customer",
                    "value": {"customer_id": graph_customer.get("customer_id", cid)},
                    "weight": 0.0,
                    "path": f"(Customer:{cid})",
                    "description": "Customer retrieved from HHGOA_Fraud through TigerGraph MCP.",
                })
            for raw_transaction in graph_initiated:
                transaction = _neighbor_identity(raw_transaction)
                transaction_id = transaction["vertex_id"]
                path = f"(Customer:{cid})-[:INITIATED]->(Transaction:{transaction_id})"
                provenance_paths.append(path)
                evidence_list.append({
                    "source": "tigergraph_mcp",
                    "signal": "graph_relationship",
                    "value": {
                        "edge_type": "INITIATED",
                        "source_type": "Customer",
                        "source_id": cid,
                        "target_type": "Transaction",
                        "target_id": transaction_id,
                    },
                    "weight": 0.0,
                    "path": path,
                    "description": "Customer transaction relationship retrieved from HHGOA_Fraud.",
                })
            if not graph_initiated:
                evidence_list.append({
                    "source": "tigergraph_mcp",
                    "signal": "graph_relationship_absent",
                    "value": {"edge_type": "INITIATED", "source_id": cid},
                    "weight": 0.0,
                    "path": f"(Customer:{cid})",
                    "description": "No initiated Transaction relationships were returned.",
                })
            for raw_neighbor in graph_neighbors:
                neighbor = _neighbor_identity(raw_neighbor)
                if neighbor["edge_type"]:
                    path = (
                        f"(Transaction:{tid})-[:{neighbor['edge_type']}]->"
                        f"({neighbor['vertex_type']}:{neighbor['vertex_id']})"
                    )
                    provenance_paths.append(path)
                    evidence_list.append({
                        "source": "tigergraph_mcp",
                        "signal": "graph_relationship",
                        "value": {
                            "edge_type": neighbor["edge_type"],
                            "source_type": "Transaction",
                            "source_id": tid,
                            "target_type": neighbor["vertex_type"],
                            "target_id": neighbor["vertex_id"],
                        },
                        "weight": 0.0,
                        "path": path,
                        "description": "Transaction relationship retrieved from HHGOA_Fraud.",
                    })
            if not graph_neighbors:
                evidence_list.append({
                    "source": "tigergraph_mcp",
                    "signal": "graph_relationship_absent",
                    "value": {"source_type": "Transaction", "source_id": tid},
                    "weight": 0.0,
                    "path": f"(Transaction:{tid})",
                    "description": "No transaction neighborhood relationships were returned.",
                })
            for raw_case in graph_cases:
                case = _neighbor_identity(raw_case)
                case_id = case["vertex_id"]
                path = f"(Customer:{cid})-[:INVOLVED_IN]->(FraudCase:{case_id})"
                provenance_paths.append(path)
                evidence_list.append({
                    "source": "tigergraph_mcp",
                    "signal": "graph_relationship",
                    "value": {
                        "edge_type": "INVOLVED_IN",
                        "source_type": "Customer",
                        "source_id": cid,
                        "target_type": "FraudCase",
                        "target_id": case_id,
                    },
                    "weight": 0.0,
                    "path": path,
                    "description": "Customer fraud-case relationship retrieved from HHGOA_Fraud.",
                })
            if not graph_cases:
                evidence_list.append({
                    "source": "tigergraph_mcp",
                    "signal": "graph_relationship_absent",
                    "value": {"edge_type": "INVOLVED_IN", "source_id": cid},
                    "weight": 0.0,
                    "path": f"(Customer:{cid})",
                    "description": "No involved FraudCase relationships were returned.",
                })
        evidence_list.append({
            "source": "transaction_alert",
            "signal": "risk_score_evaluation",
            "value": risk_score,
            "weight": 0.85 if risk_score >= 0.70 else 0.40,
            "path": p_base,
            "description": (f"Flagged transaction {tid}: ${txn_amount:,.2f}, ProductCD={product}, "
                            f"channel={channel}, billing region addr1={addr1 or 'n/a'}, "
                            f"bank risk score {risk_score:.2f} (real transactions.csv row).")
        })

        # Baseline evidence from the cardholder's real history
        if n_total > 0:
            ev_hist = {
                "source": "card_history",
                "signal": "historical_baseline",
                "value": {"n_prior": n_total, "mean_amt": round(mean_amt, 2),
                          "max_amt": round(max_amt, 2), "online_share": round(n_online / n_total, 2)},
                "weight": 0.6,
                "path": f"(Customer:{cid})-[:OWNS]->(Card:{kid})-[:MADE]->(Transaction)",
                "description": (f"Real history for {cid}: {n_total} prior transactions, mean ${mean_amt:,.2f}, "
                                f"max ${max_amt:,.2f}, {n_online} online. Flagged amount is "
                                f"{(txn_amount / mean_amt):.1f}x the cardholder mean." if mean_amt > 0 else
                                f"Real history for {cid}: {n_total} prior transactions.")
            }
            evidence_list.append(ev_hist)

        # Device / proxy evidence (identity.csv)
        if id_row:
            dev_path = f"(Transaction:{tid})-[:FROM_DEVICE]->(DeviceProfile:{device_info or 'unknown'})"
            provenance_paths.append(dev_path)
            is_anon = proxy_flag in ("IP_PROXY:ANONYMOUS", "IP_PROXY:HIDDEN", "anonymous", "hidden")
            evidence_list.append({
                "source": "device_fingerprint",
                "signal": "proxy_detection" if is_anon else "device_identity",
                "value": proxy_flag if is_anon else (device_profile or "standard"),
                "weight": 0.75 if is_anon else 0.30,
                "path": dev_path,
                "description": (f"identity.csv: device={device_info or 'unspecified'}, OS={id_row.get('id_30','') or 'n/a'}, "
                                f"browser={id_row.get('id_31','') or 'n/a'}, device status={id_15 or 'n/a'}, "
                                f"proxy={proxy_flag or 'none'}.")
            })
            if id_15.lower() == "new":
                evidence_list.append({
                    "source": "device_fingerprint",
                    "signal": "new_device",
                    "value": "New",
                    "weight": 0.55,
                    "path": dev_path,
                    "description": "Device marked New for this account (id_15=New) — consistent with pattern 3, not proof."
                })

        # Card testing evidence (real sequence scan)
        if testing["is_card_testing"]:
            path_ct = f"(Card:{kid})-[:MADE]->" + "-[:NEXT]->".join(
                f"(Transaction:{t})" for t in testing["sequence_ids"])
            provenance_paths.append(path_ct)
            evidence_list.append({
                "source": "temporal_velocity",
                "signal": "card_testing_sequence",
                "value": f"{len(testing['micro_ids'])} micros then ${testing['spike_amount']:,.2f}",
                "weight": 0.90,
                "path": path_ct,
                "description": (f"Real sequence on card {kid}: {len(testing['micro_ids'])} online authorizations under "
                                f"${CARD_TESTING_MICRO_LIMIT:.2f} ({', '.join('${:,.2f}'.format(a) for a in testing['micro_amounts'])}) "
                                f"followed by a ${testing['spike_amount']:,.2f} purchase — README pattern 1.")
            })

        # Device ring evidence (real shared-origin population)
        if len(ring_cards) >= 3:
            other_cards = [c["card_id"] for c in ring_cards if not c["card_id"].startswith(cid + "-")][:6]
            ring_scores = [_f(c.get("risk_score"), 0.5) for c in ring_cards]
            low_risk_share = sum(1 for s in ring_scores if s < 0.25) / max(len(ring_scores), 1)
            path_ring = (f"(Card:{kid})-[:MADE]->(Transaction:{tid})-[:FROM_DEVICE]->"
                         f"(DeviceProfile:{device_info})<-[:FROM_DEVICE]-(Transaction)<-[:MADE]-(Card)")
            provenance_paths.append(path_ring)
            evidence_list.append({
                "source": "graph_centrality",
                "signal": "shared_device_ring",
                "value": {"connected_cards": len(ring_cards), "examples": other_cards,
                          "low_risk_share": round(low_risk_share, 2)},
                "weight": 0.95,
                "path": path_ring,
                "description": (f"Real shared origin: device '{device_info}' with proxy '{proxy_flag}' appears on "
                                f"{len(ring_cards)} customer cards within 45 days (identity.csv joined to "
                                f"transactions.csv), including {', '.join(other_cards[:3]) if other_cards else 'n/a'}. "
                                f"{low_risk_share:.0%} of those transactions score below 0.25 — the bank model "
                                f"largely misses this pattern (README: some fraud scores near zero).")
            })

        # Out-of-region evidence
        if region_stats["is_out_of_region"]:
            path_reg = f"(Transaction:{tid})-[:BILLED_IN]->(BillingRegion:{addr1})"
            provenance_paths.append(path_reg)
            evidence_list.append({
                "source": "geolocation_graph",
                "signal": "out_of_region_spend",
                "value": {"flagged_region": addr1, "prior_txns_in_region": region_stats["prior_in_region"]},
                "weight": 0.70,
                "path": path_reg,
                "description": (f"Billing region {addr1} has no prior history on this card "
                                f"({region_stats['home_top']} dominates the cardholder's {n_total} prior transactions).")
            })
        elif addr1 and region_stats["prior_in_region"] > 0:
            evidence_list.append({
                "source": "geolocation_graph",
                "signal": "prior_region_history",
                "value": {"flagged_region": addr1, "prior_txns_in_region": region_stats["prior_in_region"]},
                "weight": 0.7,
                "path": f"(Transaction)-[:BILLED_IN]->(BillingRegion:{addr1})",
                "description": (f"Cardholder has {region_stats['prior_in_region']} prior real transactions in billing "
                                f"region {addr1} — the flagged region is established, not new (pattern 4 requires no history).")
            })

        # --- Pattern determination from real signals -------------------------
        affected_txns = [tid]
        exposure = txn_amount

        if testing["is_card_testing"]:
            primary_pattern = "card_testing"
            affected_txns = testing["sequence_ids"]
            exposure = round(sum([_f(r.get("TransactionAmt")) for r in
                                  [x for x in hist if x.get("TransactionID") in set(affected_txns)]] or [txn_amount]), 2)
        elif len(ring_cards) >= 3:
            primary_pattern = "undocumented"
        elif id_15.lower() == "new" and channel == "online":
            primary_pattern = "card_not_present_new_device"
        elif channel == "online":
            primary_pattern = "card_not_present_fraud"
        elif region_stats["is_out_of_region"]:
            primary_pattern = "out_of_region_use"
        else:
            primary_pattern = "out_of_region_use" if region_stats["is_out_of_region"] else "card_not_present_fraud"

        context.affected_txn_ids = affected_txns
        context.exposure_usd = round(exposure, 2)
        context.primary_pattern = primary_pattern
        context.evidence = evidence_list
        context.provenance_paths = provenance_paths

        # Expose ring data for downstream agents
        context.trigger_details = dict(context.trigger_details)
        context.trigger_details["device_info"] = device_info
        context.trigger_details["proxy_flag"] = proxy_flag
        context.trigger_details["id_15"] = id_15
        context.trigger_details["device_profile"] = device_profile
        context.trigger_details["ring_cards"] = [
            {"customer_id": c["customer_id"], "card_id": c["card_id"], "txn_id": c["txn_id"],
             "ts": c["ts"], "amount": c["amount"], "risk_score": c["risk_score"]}
            for c in ring_cards
        ]
        context.trigger_details["baseline"] = {
            "n_prior": n_total, "mean_amt": round(mean_amt, 2), "max_amt": round(max_amt, 2),
            "p95_amt": round(p95_amt, 2), "outside_profile": outside_profile,
            "n_online": n_online, "channel": channel, "product": product, "addr1": addr1,
        }
        context.trigger_details["region_stats"] = region_stats
        context.trigger_details["testing_scan"] = testing
        return context

    # ------------------------------------------------------------------
    @staticmethod
    def _scan_card_testing(rows: List[Dict[str, str]], micro_limit: float,
                           spike_limit: float) -> Dict[str, Any]:
        """README pattern 1: 3+ tiny online authorizations, then a larger purchase.
        Scans the card's real chronological timeline (micro window <= 60 min)."""
        import datetime
        online = []
        for r in rows:
            if (r.get("channel") or "") != "online":
                continue
            ts = r.get("ts", "")
            if not ts:
                continue
            online.append({"tid": r["TransactionID"], "ts": ts,
                           "amt": _f(r.get("TransactionAmt"))})
        online.sort(key=lambda x: x["ts"])

        micros: List[Dict[str, Any]] = []
        for i, t in enumerate(online):
            if t["amt"] >= micro_limit:
                continue
            window = [x for x in online[i + 1:]
                      if (datetime.datetime.fromisoformat(x["ts"]) -
                          datetime.datetime.fromisoformat(t["ts"])).total_seconds() <= 3600]
            window_micros = [x for x in window if x["amt"] < micro_limit]
            if len(window_micros) + 1 >= 3:
                spikes = [x for x in window if x["amt"] >= spike_limit]
                if spikes:
                    seq = [t["tid"]] + [x["tid"] for x in window_micros] + [spikes[0]["tid"]]
                    amounts = [t["amt"]] + [x["amt"] for x in window_micros]
                    return {
                        "is_card_testing": True,
                        "micro_ids": [t["tid"]] + [x["tid"] for x in window_micros],
                        "micro_amounts": amounts,
                        "spike_id": spikes[0]["tid"],
                        "spike_amount": spikes[0]["amt"],
                        "sequence_ids": seq,
                    }
        return {"is_card_testing": False, "micro_ids": [], "micro_amounts": [],
                "spike_id": "", "spike_amount": 0.0, "sequence_ids": []}

    @staticmethod
    def _region_stats(hist: List[Dict[str, str]], addr1: str, tid: str) -> Dict[str, Any]:
        from collections import Counter
        prior_regions = Counter((r.get("addr1") or "").strip()
                                for r in hist
                                if r.get("TransactionID") != tid and (r.get("addr1") or "").strip())
        prior_in_region = prior_regions.get(addr1, 0)
        home_top = prior_regions.most_common(1)[0][0] if prior_regions else ""
        return {
            "is_out_of_region": bool(addr1) and prior_in_region == 0 and len(prior_regions) > 0,
            "flagged_region": addr1,
            "prior_in_region": prior_in_region,
            "n_distinct_prior_regions": len(prior_regions),
            "home_top": home_top,
        }
