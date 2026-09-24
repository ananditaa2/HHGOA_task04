"""Small, deterministic vector index for closed-case precedent retrieval.

The index deliberately uses only the Python standard library. It is suitable
for the benchmark and can be replaced by TigerGraph vector search in a live
deployment without changing the adapter contract.
"""

from collections import Counter
import hashlib
import math
import re
from typing import Any, Dict, Iterable, List


class LightweightVectorStore:
    def __init__(self, dimensions: int = 128):
        self.dimensions = dimensions
        self._documents: List[Dict[str, Any]] = []
        self._vectors: List[List[float]] = []

    def _embed(self, text: str) -> List[float]:
        values = [0.0] * self.dimensions
        tokens = re.findall(r"[a-z0-9_]+", text.lower())
        for token, count in Counter(tokens).items():
            digest = hashlib.blake2b(token.encode("utf-8"), digest_size=8).digest()
            index = int.from_bytes(digest, "big") % self.dimensions
            values[index] += 1.0 + math.log1p(count)
        norm = math.sqrt(sum(value * value for value in values))
        return [value / norm for value in values] if norm else values

    def add(self, document: Dict[str, Any], text: str) -> None:
        self._documents.append(document)
        self._vectors.append(self._embed(text))

    def add_many(self, documents: Iterable[Dict[str, Any]], text_fields: Iterable[str]) -> None:
        fields = tuple(text_fields)
        for document in documents:
            text = " ".join(str(document.get(field, "")) for field in fields)
            self.add(document, text)

    def search(self, query: str, limit: int = 3) -> List[Dict[str, Any]]:
        query_vector = self._embed(query)
        scored = []
        for document, vector in zip(self._documents, self._vectors):
            score = round(sum(left * right for left, right in zip(query_vector, vector)), 6)
            result = dict(document)
            result["vector_similarity"] = score
            scored.append(result)
        scored.sort(key=lambda item: item["vector_similarity"], reverse=True)
        return scored[:limit]

    def __len__(self) -> int:
        return len(self._documents)