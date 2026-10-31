"""Deterministic local Host adapter for offline LangRAG benchmarks."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, field


EMBEDDING_DIM = 256


def tokenize(text: str) -> list[str]:
    """Tokenize English words and CJK text without external dependencies."""
    text = text.lower()
    tokens = re.findall(r"[a-z0-9_]+", text)

    for seq in re.findall(r"[\u4e00-\u9fff]+", text):
        tokens.extend(seq)
        tokens.extend(seq[i : i + 2] for i in range(max(len(seq) - 1, 0)))
        tokens.extend(seq[i : i + 3] for i in range(max(len(seq) - 2, 0)))

    return [token for token in tokens if token]


def embed_text(text: str, dim: int = EMBEDDING_DIM) -> list[float]:
    """Hashing-vector embedding that is deterministic across machines."""
    vector = [0.0] * dim
    for token in tokenize(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dim
        vector[index] += 1.0

    norm = math.sqrt(sum(value * value for value in vector))
    if not norm:
        return vector
    return [value / norm for value in vector]


def cosine_distance(left: list[float], right: list[float]) -> float:
    if not left or not right:
        return 1.0
    dot = sum(a * b for a, b in zip(left, right))
    return max(0.0, min(2.0, 1.0 - dot))


def lexical_distance(query: str, document: str) -> float:
    query_tokens = set(tokenize(query))
    if not query_tokens:
        return 1.0
    document_tokens = set(tokenize(document))
    overlap = len(query_tokens & document_tokens) / len(query_tokens)
    return 1.0 - overlap


def _as_value(search_type) -> str:
    return getattr(search_type, "value", search_type)


def _passes_filters(metadata: dict, filters: dict | None) -> bool:
    if not filters:
        return True

    for key, expected in filters.items():
        actual = metadata.get(key)
        if isinstance(expected, dict):
            if "$in" in expected and actual not in expected["$in"]:
                return False
            if "$eq" in expected and actual != expected["$eq"]:
                return False
        elif actual != expected:
            return False
    return True


@dataclass
class VectorRecord:
    id: str
    vector: list[float]
    metadata: dict
    document: str


@dataclass
class LocalBenchmarkPlugin:
    """Small deterministic substitute for LangBot Host capabilities."""

    collections: dict[str, dict[str, VectorRecord]] = field(default_factory=dict)
    storage: dict[str, bytes] = field(default_factory=dict)
    config: dict = field(default_factory=dict)
    embedding_calls: int = 0
    llm_calls: int = 0

    def get_config(self) -> dict:
        return self.config

    async def get_knowledge_file_stream(self, storage_path: str) -> bytes:
        return self.storage[storage_path]

    async def invoke_embedding(
        self,
        embedding_model_uuid: str,
        texts: list[str],
    ) -> list[list[float]]:
        self.embedding_calls += 1
        return [embed_text(text) for text in texts]

    async def vector_upsert(
        self,
        collection_id: str,
        vectors: list[list[float]],
        ids: list[str],
        metadata: list[dict],
        documents: list[str],
    ) -> None:
        collection = self.collections.setdefault(collection_id, {})
        for vector_id, vector, meta, document in zip(
            ids,
            vectors,
            metadata,
            documents,
        ):
            collection[vector_id] = VectorRecord(
                id=vector_id,
                vector=vector,
                metadata=dict(meta),
                document=document,
            )

    async def vector_search(
        self,
        collection_id: str,
        query_vector: list[float],
        top_k: int,
        filters: dict | None = None,
        search_type="vector",
        query_text: str = "",
        vector_weight: float | None = None,
    ) -> list[dict]:
        mode = _as_value(search_type)
        weight = 0.7 if vector_weight is None else float(vector_weight)
        results = []

        for record in self.collections.get(collection_id, {}).values():
            if not _passes_filters(record.metadata, filters):
                continue

            text = record.metadata.get("text", record.document)
            vector_dist = cosine_distance(query_vector, record.vector)
            text_dist = lexical_distance(query_text, text)

            if mode == "full_text":
                distance = text_dist
            elif mode == "hybrid":
                distance = weight * vector_dist + (1.0 - weight) * text_dist
            else:
                distance = vector_dist

            results.append(
                {
                    "id": record.id,
                    "metadata": dict(record.metadata),
                    "distance": distance,
                    "score": 1.0 - distance,
                }
            )

        results.sort(key=lambda item: (item["distance"], item["id"]))
        return results[:top_k]

    async def vector_get_by_ids(
        self,
        collection_id: str,
        ids: list[str],
    ) -> list[dict]:
        collection = self.collections.get(collection_id, {})
        result = []
        for vector_id in ids:
            record = collection.get(vector_id)
            if record:
                result.append(
                    {
                        "id": record.id,
                        "metadata": dict(record.metadata),
                        "document": record.document,
                    }
                )
        return result

    async def vector_delete(self, collection_id: str, file_ids: list[str]) -> int:
        collection = self.collections.get(collection_id, {})
        deleted = 0
        for vector_id, record in list(collection.items()):
            if record.metadata.get("file_id") in file_ids:
                del collection[vector_id]
                deleted += 1
        return deleted

    async def invoke_llm(self, llm_uuid: str, messages: list) -> object:
        self.llm_calls += 1
        prompt = messages[-1].content if messages else ""
        if not isinstance(prompt, str):
            prompt = str(prompt)
        return _LLMResponse(_local_llm_response(prompt))

    async def invoke_rerank(
        self,
        rerank_model_uuid: str,
        query: str,
        documents: list[str],
        top_k: int | None = None,
        extra_args: dict | None = None,
    ) -> list[dict]:
        ranked = sorted(
            enumerate(documents[:64]),
            key=lambda item: (lexical_distance(query, item[1]), item[0]),
        )
        if top_k is not None:
            ranked = ranked[:top_k]
        return [
            {
                "index": index,
                "relevance_score": 1.0 / (1.0 + lexical_distance(query, text)),
            }
            for index, text in ranked
        ]

    def vector_count(self, collection_id: str) -> int:
        return len(self.collections.get(collection_id, {}))


class _LLMResponse:
    def __init__(self, content: str):
        self.content = content


def _local_llm_response(prompt: str) -> str:
    if "Output exactly" in prompt and '"q": "question"' in prompt:
        return _qa_response(prompt)
    if "generate" in prompt and "different search queries" in prompt:
        return _multi_query_response(prompt)
    if "General question:" in prompt:
        query = _extract_after(prompt, "Specific question:").splitlines()[0].strip()
        return f"{query} 的背景 原理 使用场景"
    if "Passage:" in prompt and "Question:" in prompt:
        query = _extract_after(prompt, "Question:").splitlines()[0].strip()
        return f"{query}。相关资料通常会说明定义、机制、配置和适用场景。"
    if "Ranking:" in prompt and "Candidates:" in prompt:
        return _rerank_response(prompt)
    return ""


def _extract_after(text: str, marker: str) -> str:
    if marker not in text:
        return ""
    return text.split(marker, 1)[1].strip()


def _qa_response(prompt: str) -> str:
    n_match = re.search(r"generate\s+(\d+)\s+question-answer", prompt, re.I)
    n = int(n_match.group(1)) if n_match else 1
    chunk = _extract_after(prompt, "Text:")
    if "\n\nOutput exactly" in chunk:
        chunk = chunk.split("\n\nOutput exactly", 1)[0]
    answer = re.sub(r"\s+", " ", chunk).strip()[:220]
    pairs = [
        {
            "q": f"这段内容说明了什么？ {answer[:40]}",
            "a": answer,
        }
        for _ in range(n)
    ]
    return json.dumps(pairs, ensure_ascii=False)


def _multi_query_response(prompt: str) -> str:
    n_match = re.search(r"generate\s+(\d+)\s+different search queries", prompt, re.I)
    n = int(n_match.group(1)) if n_match else 3
    query = _extract_after(prompt, "User question:").splitlines()[0].strip()
    variants = [
        query,
        f"{query} 原理 配置",
        f"{query} 使用场景 检索",
    ]
    return "\n".join(variants[:n])


def _rerank_response(prompt: str) -> str:
    query = _extract_after(prompt, "Query:").splitlines()[0].strip()
    candidate_block = _extract_after(prompt, "Candidates:")
    if "\n\nRanking:" in candidate_block:
        candidate_block = candidate_block.split("\n\nRanking:", 1)[0]

    candidates: list[tuple[int, str]] = []
    for line in candidate_block.splitlines():
        match = re.match(r"\[(\d+)\]\s*(.*)", line)
        if match:
            candidates.append((int(match.group(1)), match.group(2)))

    ranked = sorted(
        candidates,
        key=lambda item: (lexical_distance(query, item[1]), item[0]),
    )
    return ",".join(str(index) for index, _ in ranked)
