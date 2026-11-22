from __future__ import annotations

import math
import hashlib
import os
import re
import uuid
from dataclasses import dataclass
from typing import Any, Optional

from qdrant_client import QdrantClient
from qdrant_client.models import (
    Distance,
    FieldCondition,
    Filter,
    MatchValue,
    PointStruct,
    VectorParams,
)

from agent.parser import CodeSymbol


@dataclass
class SearchResult:
    symbol_name: str
    symbol_type: str
    file_path: str
    start_line: int
    end_line: int
    raw_code: str
    score: float
    language: str


def _tokenize(text: str) -> list[str]:
    # Split camelCase and snake_case
    spaced = re.sub(r"([a-z])([A-Z])", r"\1 \2", text)
    tokens = re.findall(r"[a-zA-Z0-9_]+", spaced.lower())
    res = list(tokens)
    for tok in tokens:
        if len(tok) >= 3:
            for i in range(len(tok) - 2):
                res.append(tok[i : i + 3])
    return res


def _deterministic_dense_embed(text: str, dim: int = 384) -> list[float]:
    tokens = _tokenize(text)
    if not tokens:
        return [1.0 / math.sqrt(dim)] * dim

    vec = [0.0] * dim
    for tok in tokens:
        h = int(hashlib.md5(tok.encode("utf-8")).hexdigest(), 16)
        idx = h % dim
        sign = 1.0 if (h >> 1) & 1 else -1.0
        vec[idx] += sign * (1.0 + math.log(1 + len(tok)))

    norm = math.sqrt(sum(x * x for x in vec))
    if norm > 0:
        return [x / norm for x in vec]
    return [1.0 / math.sqrt(dim)] * dim


class VectorStore:
    def __init__(
        self,
        storage_path: str = "./qdrant_storage",
        collection_name: str = "codebase_chunks",
    ) -> None:
        self.storage_path = storage_path
        self.collection_name = collection_name
        self.vector_size = 384

        if storage_path == ":memory:":
            self.client = QdrantClient(":memory:")
        else:
            os.makedirs(storage_path, exist_ok=True)
            self.client = QdrantClient(path=storage_path)

        self._ensure_collection()

    def _ensure_collection(self) -> None:
        if not self.client.collection_exists(self.collection_name):
            self.client.create_collection(
                collection_name=self.collection_name,
                vectors_config=VectorParams(
                    size=self.vector_size,
                    distance=Distance.COSINE,
                ),
            )

    def _embed(self, text: str) -> list[float]:
        # FastEmbed fallback: offline deterministic dense embedding vectorizer
        return _deterministic_dense_embed(text, dim=self.vector_size)

    def index_symbols(
        self,
        workspace_id: str,
        symbols: list[CodeSymbol],
        file_path: str = "",
    ) -> int:
        if not symbols:
            return 0

        norm_path = file_path.replace("\\", "/")
        points: list[PointStruct] = []

        for sym in symbols:
            point_id = str(
                uuid.uuid5(
                    uuid.NAMESPACE_URL,
                    f"{workspace_id}:{norm_path}:{sym.name}:{sym.start_line}:{sym.end_line}",
                )
            )
            embed_text = f"{sym.name} {sym.name} {sym.symbol_type} {sym.signature}\n{sym.raw_code}"
            vector = self._embed(embed_text)

            payload = {
                "workspace_id": workspace_id,
                "symbol_name": sym.name,
                "symbol_type": sym.symbol_type,
                "file_path": norm_path,
                "start_line": sym.start_line,
                "end_line": sym.end_line,
                "signature": sym.signature,
                "raw_code": sym.raw_code,
                "language": sym.language,
            }

            points.append(PointStruct(id=point_id, vector=vector, payload=payload))

        for i in range(0, len(points), 100):
            batch = points[i : i + 100]
            self.client.upsert(collection_name=self.collection_name, points=batch)
        return len(points)

    def search(
        self,
        workspace_id: str,
        query: str,
        limit: int = 5,
        symbol_type: Optional[str] = None,
    ) -> list[SearchResult]:
        query_vector = self._embed(query)

        must_conditions: list[Any] = [
            FieldCondition(key="workspace_id", match=MatchValue(value=workspace_id))
        ]
        if symbol_type:
            must_conditions.append(
                FieldCondition(key="symbol_type", match=MatchValue(value=symbol_type))
            )

        query_filter = Filter(must=must_conditions)

        if hasattr(self.client, "query_points"):
            response = self.client.query_points(
                collection_name=self.collection_name,
                query=query_vector,
                query_filter=query_filter,
                limit=limit,
            )
            scored_points = response.points
        else:
            scored_points = self.client.search(
                collection_name=self.collection_name,
                query_vector=query_vector,
                query_filter=query_filter,
                limit=limit,
            )

        results: list[SearchResult] = []
        for pt in scored_points:
            payload = pt.payload or {}
            results.append(
                SearchResult(
                    symbol_name=str(payload.get("symbol_name", "")),
                    symbol_type=str(payload.get("symbol_type", "")),
                    file_path=str(payload.get("file_path", "")),
                    start_line=int(payload.get("start_line", 0)),
                    end_line=int(payload.get("end_line", 0)),
                    raw_code=str(payload.get("raw_code", "")),
                    score=float(pt.score if pt.score is not None else 0.0),
                    language=str(payload.get("language", "")),
                )
            )

        return results

    def close(self) -> None:
        if hasattr(self, "client") and hasattr(self.client, "close"):
            try:
                self.client.close()
            except Exception:
                pass

    def __enter__(self) -> VectorStore:
        return self

    def __exit__(self, exc_type: Any, exc_val: Any, exc_tb: Any) -> None:
        self.close()

