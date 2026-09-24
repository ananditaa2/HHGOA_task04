"""
Live TigerGraph Savanna & REST Client
Provides direct integration with TigerGraph Cloud and Community Edition.
"""

import requests
import json
from urllib.parse import urlparse
from typing import Dict, List, Any, Optional
from src.config import TG_HOST, TG_USERNAME, TG_PASSWORD, TG_GRAPH, TG_SECRET, TG_API_TOKEN


class TigerGraphClient:
    def __init__(
        self,
        host: str = TG_HOST,
        graph_name: str = TG_GRAPH,
        username: str = TG_USERNAME,
        password: str = TG_PASSWORD,
        secret: str = TG_SECRET,
        api_token: str = TG_API_TOKEN
    ):
        self.host = host.rstrip("/")
        self.graph_name = graph_name
        self.username = username
        self.password = password
        self.secret = secret
        self.api_token = api_token
        self.headers = {"Content-Type": "application/json"}
        if self.api_token:
            self.headers["Authorization"] = f"Bearer {self.api_token}"

        # Savanna / tgcloud hosts already embed the REST++ port (e.g.
        # https://your-instance.i.tgcloud.io:443), while plain hosts default
        # to the classic REST++ port 9000.
        parsed = urlparse(self.host)
        self.restpp_port = parsed.port or (443 if parsed.scheme == "https" else 9000)
        self.gsql_port = 443 if parsed.scheme == "https" else 14240

    def _restpp(self, path: str) -> str:
        parsed = urlparse(self.host)
        base = self.host if parsed.port else f"{self.host}:{self.restpp_port}"
        return f"{base}{path}"

    def _gsql(self) -> str:
        parsed = urlparse(self.host)
        if parsed.port and parsed.scheme != "https":
            base = f"{parsed.scheme}://{parsed.hostname}:{self.gsql_port}"
        else:
            base = self.host if parsed.port else f"{self.host}:{self.gsql_port}"
        return f"{base}/gsqlserver/gsql"

    def check_connection(self) -> bool:
        try:
            resp = requests.get(self._restpp("/echo"), timeout=3)
            return resp.status_code == 200
        except Exception:
            return False

    def run_gsql_query(self, query_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if params is None:
            params = {}
        url = self._restpp(f"/query/{self.graph_name}/{query_name}")
        try:
            resp = requests.get(url, params=params, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [{}])[0]
            return {"error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"error": str(e)}

    def get_vertex_count(self) -> Dict[str, int]:
        url = self._restpp(f"/graph/{self.graph_name}/vertices")
        try:
            resp = requests.get(url, headers=self.headers, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("results", {})
            return {}
        except Exception:
            return {}

    def get_vertex(self, vertex_type: str, vertex_id: str) -> Optional[Dict[str, Any]]:
        url = self._restpp(f"/graph/{self.graph_name}/vertices/{vertex_type}/{vertex_id}")
        try:
            resp = requests.get(url, headers=self.headers, timeout=10)
            if resp.status_code != 200:
                return None
            results = resp.json().get("results", [])
            return results[0] if results else None
        except Exception:
            return None

    def upsert_vertex(self, vertex_type: str, vertex_id: str, attributes: Dict[str, Any]) -> bool:
        url = self._restpp(f"/graph/{self.graph_name}/vertices/{vertex_type}/{vertex_id}")
        payload = {key: value for key, value in attributes.items() if key not in ("_id", "_type")}
        try:
            resp = requests.post(url, json=payload, headers=self.headers, timeout=10)
            return resp.status_code in (200, 201)
        except Exception:
            return False

    def execute_gsql(self, statement: str) -> Dict[str, Any]:
        """Execute an admin GSQL statement through the TigerGraph REST API."""
        url = self._gsql()
        try:
            resp = requests.post(url, data=statement, headers=self.headers, timeout=60)
            return {"status_code": resp.status_code, "body": resp.text}
        except Exception as exc:
            return {"status_code": 0, "body": str(exc)}
