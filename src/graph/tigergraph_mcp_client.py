"""Read-only TigerGraph MCP client for the deployed HHGOA_Fraud graph."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import Any, Dict, Iterable, List, Optional

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from src.config import TG_HOST, TG_SECRET, TG_GRAPH

LOGGER = logging.getLogger(__name__)

GRAPH_NAME = "HHGOA_Fraud"
REQUIRED_READ_TOOLS = frozenset(
    {"tigergraph__get_graph_schema", "tigergraph__get_node", "tigergraph__get_neighbors"}
)
EXPECTED_VERTICES = frozenset(
    {"Customer", "Account", "Transaction", "Device", "Merchant", "FraudCase"}
)
EXPECTED_EDGES = frozenset(
    {
        "OWNS",
        "INITIATED",
        "MADE",
        "SENT_TO",
        "PAID_TO",
        "USES",
        "ACCESSED_FROM",
        "CONNECTED_TO",
        "RELATED_TO",
        "INVOLVED_IN",
    }
)


class TigerGraphMCPError(RuntimeError):
    """Raised when the MCP server cannot provide a safe graph read."""


class TigerGraphMCPClient:
    """Synchronous facade over one long-lived asynchronous MCP stdio session."""

    def __init__(self, graph_name: str = GRAPH_NAME) -> None:
        configured_graph = os.getenv("TG_GRAPHNAME") or TG_GRAPH
        if graph_name != GRAPH_NAME or configured_graph != GRAPH_NAME:
            raise ValueError(f"Only {GRAPH_NAME} is supported, not {graph_name}")
        if not TG_HOST or not TG_SECRET:
            raise TigerGraphMCPError("TG_HOST and TG_SECRET are required for MCP access")

        self.graph_name = graph_name
        self._loop: Optional[asyncio.AbstractEventLoop] = None
        self._thread = threading.Thread(target=self._run, name="tigergraph-mcp", daemon=True)
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._startup_error: Optional[BaseException] = None
        self._session: Optional[ClientSession] = None
        self._thread.start()
        self._ready.wait()
        if self._startup_error is not None:
            raise TigerGraphMCPError("TigerGraph MCP startup failed") from self._startup_error

    def _run(self) -> None:
        try:
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
            self._loop.run_until_complete(self._serve())
        except BaseException as exc:
            self._startup_error = exc
            self._ready.set()
            LOGGER.error("TigerGraph MCP session failed")
        finally:
            if self._loop is not None:
                self._loop.close()

    async def _serve(self) -> None:
        env = {
            "TG_HOST": TG_HOST,
            "TG_SECRET": TG_SECRET,
            "TG_GRAPHNAME": self.graph_name,
        }
        parameters = StdioServerParameters(command="uvx", args=["tigergraph-mcp"], env=env)
        async with stdio_client(parameters) as streams:
            async with ClientSession(*streams) as session:
                self._session = session
                await session.initialize()
                tools = await session.list_tools()
                tool_names = {tool.name for tool in tools.tools}
                missing = REQUIRED_READ_TOOLS - tool_names
                if missing:
                    raise TigerGraphMCPError(
                        f"Required read tools are unavailable: {sorted(missing)}"
                    )
                schema = await self._call_async(
                    "tigergraph__get_graph_schema",
                    {"graph_name": self.graph_name},
                )
                self.validate_schema(schema)
                self._ready.set()
                while not self._stop.is_set():
                    await asyncio.sleep(0.1)
        self._session = None

    async def _call_async(self, name: str, arguments: Dict[str, Any]) -> Any:
        if self._session is None:
            raise TigerGraphMCPError("TigerGraph MCP session is not ready")
        result = await self._session.call_tool(name, arguments)
        if getattr(result, "isError", False):
            raise TigerGraphMCPError(f"TigerGraph MCP read failed for {name}")
        return self._decode_result(result)

    @staticmethod
    def _decode_result(result: Any) -> Any:
        structured = getattr(result, "structuredContent", None)
        if structured is not None:
            return structured
        for item in getattr(result, "content", []):
            text = getattr(item, "text", None)
            if text is not None:
                text = text.strip()
                if text.startswith("```"):
                    lines = text.splitlines()
                    opening = lines[0].strip().lower()
                    if opening in {"```", "```json"}:
                        closing_index = next(
                            (
                                index
                                for index, line in enumerate(lines[1:], start=1)
                                if line.strip() == "```"
                            ),
                            None,
                        )
                        if closing_index is not None:
                            text = "\n".join(lines[1:closing_index]).strip()
                try:
                    return json.loads(text)
                except (TypeError, json.JSONDecodeError):
                    return text
        return {}

    def _call(self, name: str, arguments: Dict[str, Any]) -> Any:
        if self._loop is None or not self._thread.is_alive():
            raise TigerGraphMCPError("TigerGraph MCP session is unavailable")
        future = asyncio.run_coroutine_threadsafe(
            self._call_async(name, arguments), self._loop
        )
        try:
            return future.result(timeout=60)
        except Exception as exc:
            raise TigerGraphMCPError(f"TigerGraph MCP read failed for {name}") from exc

    @staticmethod
    def _unwrap(payload: Any) -> Any:
        if isinstance(payload, dict) and "data" in payload:
            return payload["data"]
        return payload

    @classmethod
    def validate_schema(cls, schema: Any) -> Dict[str, Any]:
        payload = cls._unwrap(schema)
        if not isinstance(payload, dict):
            raise TigerGraphMCPError("TigerGraph schema response is not an object")
        if isinstance(payload.get("schema"), dict):
            payload = payload["schema"]

        vertices = cls._names(payload, ("vertices", "vertex_types", "VertexTypes"))
        edges = cls._names(payload, ("edges", "edge_types", "EdgeTypes"))
        if vertices != EXPECTED_VERTICES or edges != EXPECTED_EDGES:
            raise TigerGraphMCPError(
                "HHGOA_Fraud schema does not match the expected deployed schema"
            )
        return payload

    @staticmethod
    def _names(payload: Dict[str, Any], keys: Iterable[str]) -> frozenset[str]:
        values: Any = None
        for key in keys:
            if key in payload:
                values = payload[key]
                break
        if isinstance(values, dict):
            values = values.keys()
        if values is None or isinstance(values, (str, bytes)) or not hasattr(values, "__iter__"):
            return frozenset()
        names = set()
        for value in values:
            names.add(value if isinstance(value, str) else value.get("name") or value.get("Name", ""))
        return frozenset(name for name in names if name)

    def get_schema(self) -> Dict[str, Any]:
        payload = self._unwrap(self._call("tigergraph__get_graph_schema", {"graph_name": self.graph_name}))
        return payload.get("schema", payload) if isinstance(payload, dict) else {}

    def get_customer(self, customer_id: str) -> Dict[str, Any]:
        return self._get_node("Customer", customer_id)

    def get_transaction(self, transaction_id: str) -> Dict[str, Any]:
        return self._get_node("Transaction", transaction_id)

    def _get_node(self, vertex_type: str, vertex_id: str) -> Dict[str, Any]:
        result = self._unwrap(
            self._call(
                "tigergraph__get_node",
                {
                    "graph_name": self.graph_name,
                    "vertex_type": vertex_type,
                    "vertex_id": str(vertex_id),
                },
            )
        )
        return result if isinstance(result, dict) else {}

    def _neighbors(
        self,
        vertex_type: str,
        vertex_id: str,
        edge_type: Optional[str] = None,
        target_vertex_type: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        arguments: Dict[str, Any] = {
            "graph_name": self.graph_name,
            "vertex_type": vertex_type,
            "vertex_id": str(vertex_id),
            "limit": limit,
        }
        if edge_type:
            arguments["edge_type"] = edge_type
        if target_vertex_type:
            arguments["target_vertex_type"] = target_vertex_type
        result = self._unwrap(self._call("tigergraph__get_neighbors", arguments))
        if isinstance(result, dict):
            result = result.get("neighbors", result.get("vertices", []))
        return result if isinstance(result, list) else []

    def get_customer_transactions(self, customer_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return self._neighbors("Customer", customer_id, "INITIATED", "Transaction", limit)

    def get_customer_cases(self, customer_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return self._neighbors("Customer", customer_id, "INVOLVED_IN", "FraudCase", limit)

    def get_transaction_neighbors(self, transaction_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        return self._neighbors("Transaction", transaction_id, limit=limit)

    def close(self) -> None:
        if self._thread.is_alive() and self._loop is not None:
            self._stop.set()
            self._thread.join(timeout=5)

    def __enter__(self) -> "TigerGraphMCPClient":
        return self

    def __exit__(self, *_: Any) -> None:
        self.close()
