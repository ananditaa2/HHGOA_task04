"""
Live TigerGraph Savanna & REST Client
Provides direct integration with TigerGraph Cloud and Community Edition.
"""

import requests
import json
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

    def check_connection(self) -> bool:
        try:
            resp = requests.get(f"{self.host}:9000/echo", timeout=3)
            return resp.status_code == 200
        except Exception:
            try:
                resp = requests.get(f"{self.host}/echo", timeout=3)
                return resp.status_code == 200
            except Exception:
                return False

    def run_gsql_query(self, query_name: str, params: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        if params is None:
            params = {}
        url = f"{self.host}:9000/query/{self.graph_name}/{query_name}"
        try:
            resp = requests.get(url, params=params, headers=self.headers, timeout=10)
            if resp.status_code == 200:
                data = resp.json()
                return data.get("results", [{}])[0]
            return {"error": f"HTTP {resp.status_code}: {resp.text}"}
        except Exception as e:
            return {"error": str(e)}

    def get_vertex_count(self) -> Dict[str, int]:
        url = f"{self.host}:9000/graph/{self.graph_name}/vertices"
        try:
            resp = requests.get(url, headers=self.headers, timeout=5)
            if resp.status_code == 200:
                return resp.json().get("results", {})
            return {}
        except Exception:
            return {}
