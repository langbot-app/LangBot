from __future__ import annotations

import pytest

from components.knowledge_engine.memory_engine import LongTermMemoryEngine
from langbot_plugin.api.entities.builtin.rag.context import RetrievalContext
from store.memory_store import MemoryStore


class FakePlugin:
    def __init__(self, *, fail_hybrid: bool = False):
        self.memory_store = MemoryStore(self)
        self.fail_hybrid = fail_hybrid
        self.search_calls: list[dict] = []
        self.records = [
            {
                "id": "active-1",
                "metadata": {
                    "content": "Active memory",
                    "importance": "2",
                    "timestamp": "2026-01-01T00:00:00Z",
                    "user_key": "bot-1:group_1",
                    "status": "active",
                },
                "distance": 0.1,
            },
            {
                "id": "superseded-1",
                "metadata": {
                    "content": "Superseded memory",
                    "importance": "5",
                    "timestamp": "2026-01-02T00:00:00Z",
                    "user_key": "bot-1:group_1",
                    "status": "superseded",
                },
                "distance": 0.0,
            },
        ]

    async def invoke_embedding(self, _embedding_model_uuid: str, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    async def vector_search(self, collection_id, query_vector, top_k=5, filters=None, **_kwargs):
        self.search_calls.append(_kwargs)
        if _kwargs.get("search_type") == "hybrid" and self.fail_hybrid:
            raise RuntimeError("hybrid unavailable")
        return self.records[:top_k]


@pytest.mark.asyncio
async def test_engine_retrieve_excludes_non_active_episodes_by_default():
    engine = LongTermMemoryEngine()
    engine.plugin = FakePlugin()

    response = await engine.retrieve(
        RetrievalContext(
            query="memory",
            knowledge_base_id="kb-1",
            creation_settings={"embedding_model_uuid": "emb-1", "isolation": "session"},
            retrieval_settings={
                "top_k": 5,
                "session_name": "group_1",
                "bot_uuid": "bot-1",
            },
        )
    )

    assert [entry.id for entry in response.results] == ["active-1"]
    assert "Active memory" in (response.results[0].content[0].text or "")


@pytest.mark.asyncio
async def test_engine_retrieve_uses_hybrid_and_falls_back_to_vector():
    engine = LongTermMemoryEngine()
    plugin = FakePlugin(fail_hybrid=True)
    engine.plugin = plugin

    response = await engine.retrieve(
        RetrievalContext(
            query="memory",
            knowledge_base_id="kb-1",
            creation_settings={
                "embedding_model_uuid": "emb-1",
                "isolation": "session",
                "retrieval_strategy": "auto",
                "vector_weight": 0.6,
            },
            retrieval_settings={
                "top_k": 5,
                "session_name": "group_1",
                "bot_uuid": "bot-1",
            },
        )
    )

    assert [entry.id for entry in response.results] == ["active-1"]
    assert plugin.search_calls[0] == {
        "search_type": "hybrid",
        "query_text": "memory",
        "vector_weight": 0.6,
    }
    assert plugin.search_calls[1] == {}
