from __future__ import annotations

import json

import pytest

from components.tools.remember import Remember
from langbot_plugin.api.entities.builtin.provider.session import Session, LauncherTypes
from store.memory_store import MemoryStore


class FakeAPI:
    async def get_bot_uuid(self) -> str:
        return "bot-1"

    async def get_query_vars(self) -> dict:
        return {"sender_id": "u-1", "sender_name": "Alice"}

    async def list_pipeline_knowledge_bases(self) -> list[dict]:
        return [{"uuid": "kb-1"}]


class FakePlugin:
    def __init__(self):
        self.storage: dict[str, bytes] = {}
        self.memory_store = MemoryStore(self)
        self.plugin_runtime_handler = object()
        self.records: dict[str, dict] = {}

    async def get_plugin_storage_keys(self) -> list[str]:
        return list(self.storage)

    async def get_plugin_storage(self, key: str) -> bytes:
        if key not in self.storage:
            raise KeyError(key)
        return self.storage[key]

    async def set_plugin_storage(self, key: str, data: bytes) -> None:
        self.storage[key] = data

    async def invoke_embedding(self, _embedding_model_uuid: str, texts: list[str]) -> list[list[float]]:
        return [[1.0] for _ in texts]

    async def vector_upsert(self, collection_id, vectors, ids, metadata=None, documents=None):
        for index, item_id in enumerate(ids):
            self.records[item_id] = {"metadata": metadata[index], "document": documents[index]}


def _session() -> Session:
    return Session(launcher_type=LauncherTypes.GROUP, launcher_id="1")


@pytest.mark.asyncio
async def test_remember_writes_audit_entry(monkeypatch):
    monkeypatch.setattr("components.tools.remember.QueryBasedAPIProxy", lambda **_: FakeAPI())
    tool = Remember()
    plugin = FakePlugin()
    plugin.storage["kb_configs"] = json.dumps(
        {"kb-1": {"embedding_model_uuid": "emb-1", "isolation": "session"}}
    ).encode("utf-8")
    tool.plugin = plugin

    result = await tool.call(
        {"content": "User likes quiet summaries", "tags": ["preference"], "importance": 3},
        _session(),
        query_id=123,
    )

    assert result.startswith("Remembered:")
    entries = json.loads(plugin.storage["audit:bot-1:group_1"].decode("utf-8"))
    assert entries[0]["operation"] == "remember"
    assert entries[0]["target_type"] == "episode"
    assert entries[0]["user_key"] == "bot-1:group_1"
    assert entries[0]["sender_id"] == "u-1"
    assert entries[0]["query_id"] == 123
    assert "quiet summaries" in entries[0]["summary"]
