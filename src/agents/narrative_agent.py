"""Optional analyst narrative generation with a deterministic local fallback."""

import json
import os
from typing import Any, Dict

import requests


class NarrativeAgent:
    def generate(self, investigation: Dict[str, Any]) -> str:
        if os.getenv("NARRATIVE_LLM_ENABLED", "").lower() not in ("1", "true", "yes"):
            return self._fallback(investigation)
        api_key = os.getenv("OPENAI_API_KEY", "")
        if not api_key:
            return self._fallback(investigation)
        prompt = json.dumps({
            "verdict": investigation.get("case", {}).get("verdict"),
            "pattern": investigation.get("case", {}).get("pattern"),
            "summary": investigation.get("case", {}).get("summary"),
            "actions": investigation.get("next_best_actions", {}).get("final", []),
        })
        try:
            response = requests.post(
                os.getenv("NARRATIVE_LLM_URL", "https://api.openai.com/v1/chat/completions"),
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={"model": os.getenv("NARRATIVE_LLM_MODEL", "gpt-4o-mini"),
                      "temperature": 0, "messages": [{"role": "user", "content": prompt}]},
                timeout=20,
            )
            response.raise_for_status()
            return response.json()["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, requests.RequestException):
            return self._fallback(investigation)

    @staticmethod
    def _fallback(investigation: Dict[str, Any]) -> str:
        case = investigation.get("case", {})
        return (f"Analyst narrative: verdict {case.get('verdict', 'uncertain')} with pattern "
                f"{case.get('pattern', 'undocumented')}; exposure ${case.get('exposure_usd', 0):,.2f}. "
                f"Evidence summary: {case.get('summary', 'No summary available.')}")