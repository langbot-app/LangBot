from __future__ import annotations

import json

import pytest

from components.tools.remember import Remember
from components.tools.recall_memory import RecallMemory
from components.tools.update_profile import UpdateProfile
from components.tools.forget import Forget
from langbot_plugin.api.entities.builtin.provider.session import Session, LauncherTypes
from store.memory_store import MemoryStore


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
            self.records[item_id] = {
                "id": item_id,
                "metadata": metadata[index],
                "document": documents[index],
                "score": 1.0,
            }

    async def vector_search(self, collection_id, query_vector, top_k=5, filters=None, **kwargs):
        return [item for item in self.records.values() if self._matches(item, filters)][:top_k]

    async def vector_list(self, collection_id, filters=None, limit=20, offset=0):
        items = [item for item in self.records.values() if self._matches(item, filters)]
        return {"items": items[offset : offset + limit], "total": len(items)}

    async def vector_delete(self, collection_id, file_ids=None, filters=None):
        ids = [
            key
            for key in (file_ids or self.records)
            if key in self.records and self._matches(self.records[key], filters)
        ]
        for key in ids:
            del self.records[key]
        return len(ids)

    @classmethod
    def _matches(cls, item, filters):
        if filters and "$and" in filters:
            return all(cls._matches(item, condition) for condition in filters["$and"])
        return all(item["metadata"].get(key) == value for key, value in (filters or {}).items())


def _session() -> Session:
    return Session(launcher_type=LauncherTypes.GROUP, launcher_id="1", bot_uuid="bot-1", sender_id="u-1")


@pytest.mark.asyncio
async def test_remember_writes_audit_entry():
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


@pytest.mark.asyncio
async def test_processor_memory_round_trip_and_scope_isolation():
    plugin = FakePlugin()
    plugin.storage["kb_configs"] = json.dumps(
        {"kb-1": {"embedding_model_uuid": "emb-1", "isolation": "session"}}
    ).encode()

    async def call(tool_class, params, session=None):
        tool = tool_class()
        tool.plugin = plugin
        return await tool.call(params, session or _session(), query_id=123)

    assert (await call(Remember, {"content": "Release on Friday"})).startswith("Remembered:")
    assert (
        await call(UpdateProfile, {"field": "preferences", "action": "add", "value": "concise replies"})
    ).startswith("Speaker profile updated.")
    recalled = json.loads(await call(RecallMemory, {"query": "release"}))
    assert recalled["episodes"][0]["content"] == "Release on Friday"
    assert "concise replies" in recalled["speaker_profile"]

    other_speaker = _session().model_copy(update={"sender_id": "u-2"})
    other = json.loads(await call(RecallMemory, {"query": "release"}, other_speaker))
    assert other["speaker_profile"] == ""
    assert other["episodes"][0]["content"] == "Release on Friday"

    for update in ({"launcher_id": "2"}, {"bot_uuid": "bot-2"}):
        assert (
            await call(RecallMemory, {"query": "release"}, _session().model_copy(update=update))
            == "No relevant memories found."
        )

    episode_id = recalled["episodes"][0]["id"]
    await call(Forget, {"episode_id": episode_id})
    assert json.loads(await call(RecallMemory, {"query": "release"}))["episodes"] == []


@pytest.mark.asyncio
async def test_processor_profile_recall_with_no_episodes():
    plugin = FakePlugin()
    plugin.storage["kb_configs"] = json.dumps(
        {"kb-1": {"embedding_model_uuid": "emb-1", "isolation": "session"}}
    ).encode()
    await plugin.memory_store.update_session_profile_field("bot-1:group_1", "notes", "set", "Release coordination")
    tool = RecallMemory()
    tool.plugin = plugin
    recalled = json.loads(await tool.call({"query": "group purpose"}, _session(), query_id=123))
    assert "Release coordination" in recalled["session_profile"]
    assert recalled["episodes"] == []


@pytest.mark.asyncio
async def test_forget_legacy_episode_preserves_other_scopes():
    plugin = FakePlugin()
    plugin.storage["kb_configs"] = json.dumps(
        {"kb-1": {"embedding_model_uuid": "emb-1", "isolation": "session"}}
    ).encode()

    # Model the legacy Host contract: file_ids address document metadata, not vector IDs.
    async def delete(collection_id, file_ids=None, filters=None):
        assert file_ids is None
        ids = [key for key, item in plugin.records.items() if plugin._matches(item, filters)]
        for key in ids:
            del plugin.records[key]
        return 0  # Chroma acknowledges deletion without returning a count.

    plugin.vector_delete = delete
    plugin.records = {
        "legacy": {"id": "legacy", "metadata": {"user_key": "bot-1:group_1", "content": "old fact"}},
        "other": {"id": "other", "metadata": {"user_key": "bot-2:group_1", "content": "other fact"}},
    }
    tool = Forget()
    tool.plugin = plugin
    assert await tool.call({"episode_id": "other"}, _session(), 123) == "No matching memory found in the current scope."
    assert await tool.call({"episode_id": "legacy"}, _session(), 123) == "Deleted episode legacy."
    assert set(plugin.records) == {"other"}


@pytest.mark.asyncio
async def test_forget_does_not_report_success_when_backend_keeps_record():
    plugin = FakePlugin()
    plugin.records["kept"] = {
        "id": "kept",
        "metadata": {"episode_id": "kept", "user_key": "bot-1:group_1", "content": "still here"},
    }

    async def no_delete(**kwargs):
        return 0

    plugin.vector_delete = no_delete
    with pytest.raises(RuntimeError, match="did not remove"):
        await plugin.memory_store.delete_episode_by_id("kb-1", "kept", "bot-1:group_1")
