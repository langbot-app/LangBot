from __future__ import annotations

import pytest

from components.commands.memory import Memory
from langbot_plugin.api.entities.builtin.command.context import ExecuteContext
from langbot_plugin.api.entities.builtin.provider.session import Session, LauncherTypes


class FakeAPI:
    def __init__(self, active: bool = True):
        self.active = active

    async def get_bot_uuid(self) -> str:
        return "bot-1"

    async def get_query_vars(self) -> dict:
        return {}

    async def list_pipeline_knowledge_bases(self) -> list[dict]:
        return [{"uuid": "kb-1"}] if self.active else []


class FakeStore:
    def __init__(self, kb: tuple[str, dict] | None = None, plugin=None):
        self.kb = kb
        self.plugin = plugin

    async def get_kb_config(self):
        return self.kb

    async def resolve_user_context(self, session, bot_uuid: str = ""):
        if not self.kb:
            return "bot-1:group_1", "bot-1:group_1", None, "session", {}
        kb_id, config = self.kb
        return "bot-1:group_1", "bot-1:group_1", kb_id, config.get("isolation", "session"), config

    async def run_metadata_filter_probe(self, collection_id, embedding_model_uuid):
        # Delegate to the real probe so this test exercises the shared logic
        # that backs both !memory health and the memory console.
        from store.memory_store import MemoryStore

        return await MemoryStore(self.plugin).run_metadata_filter_probe(
            collection_id=collection_id,
            embedding_model_uuid=embedding_model_uuid,
        )


class FakePlugin:
    def __init__(self, *, leak: bool = False, delete_leak: bool = False):
        self.memory_store = FakeStore(
            ("kb-1", {"embedding_model_uuid": "emb-1", "isolation": "session"}),
            plugin=self,
        )
        self.plugin_runtime_handler = object()
        self.leak = leak
        self.delete_leak = delete_leak
        self.records: dict[str, dict] = {}
        self.deleted: list[str] = []

    async def get_plugin_storage_keys(self) -> list[str]:
        return []

    async def invoke_embedding(self, _embedding_model_uuid: str, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1)] for index, _ in enumerate(texts)]

    async def vector_upsert(self, collection_id, vectors, ids, metadata=None, documents=None):
        for index, item_id in enumerate(ids):
            self.records[item_id] = {
                "id": item_id,
                "metadata": metadata[index],
                "document": documents[index],
            }

    async def vector_search(self, collection_id, query_vector, top_k=5, filters=None, **_kwargs):
        user_key = (filters or {}).get("user_key")
        items = list(self.records.values())
        if not self.leak and user_key:
            items = [item for item in items if item["metadata"].get("user_key") == user_key]
        return items[:top_k]

    async def vector_list(self, collection_id, filters=None, limit=20, offset=0):
        user_key = (filters or {}).get("user_key")
        items = list(self.records.values())
        if not self.leak and user_key:
            items = [item for item in items if item["metadata"].get("user_key") == user_key]
        return {"items": items[offset: offset + limit], "total": len(items)}

    async def vector_delete(self, collection_id, file_ids=None, filters=None):
        count = 0
        if file_ids:
            for item_id in file_ids:
                if item_id in self.records:
                    self.records.pop(item_id)
                    self.deleted.append(item_id)
                    count += 1
        elif filters:
            user_key = filters.get("user_key")
            item_ids = list(self.records)
            if not self.delete_leak and user_key:
                item_ids = [
                    item_id
                    for item_id in item_ids
                    if self.records[item_id]["metadata"].get("user_key") == user_key
                ]
            for item_id in item_ids:
                self.records.pop(item_id)
                self.deleted.append(item_id)
                count += 1
        return count


def _context() -> ExecuteContext:
    return ExecuteContext(
        query_id=1,
        session=Session(launcher_type=LauncherTypes.GROUP, launcher_id="1"),
        command_text="memory health",
        full_command_text="!memory health",
        command="memory",
        crt_command="health",
        params=["health"],
        crt_params=[],
        privilege=0,
    )


async def _run_health(command: Memory) -> str:
    subcommand = command.registered_subcommands["health"].subcommand
    results = []
    async for item in subcommand(command, _context()):
        results.append(item.text or "")
    return "\n".join(results)


@pytest.mark.asyncio
async def test_memory_health_ok(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI(active=True))
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    output = await _run_health(command)

    assert "Result: OK" in output
    assert "vector_search respects user_key metadata filter" in output
    assert "vector_list respects user_key metadata filter" in output
    assert "vector_delete respects user_key metadata filter" in output
    assert plugin.records == {}
    assert len(plugin.deleted) == 2


@pytest.mark.asyncio
async def test_memory_health_detects_metadata_filter_leak(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI(active=True))
    command = Memory()
    plugin = FakePlugin(leak=True)
    command.plugin = plugin

    output = await _run_health(command)

    assert "Result: ERROR" in output
    assert "filter leaked another user_key result" in output
    assert plugin.records == {}


@pytest.mark.asyncio
async def test_memory_health_detects_metadata_filter_delete_leak(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI(active=True))
    command = Memory()
    plugin = FakePlugin(delete_leak=True)
    command.plugin = plugin

    output = await _run_health(command)

    assert "Result: ERROR" in output
    assert "vector_delete filter deleted more probe records than expected" in output
    assert plugin.records == {}


@pytest.mark.asyncio
async def test_memory_health_reports_missing_kb(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI(active=False))
    command = Memory()
    plugin = FakePlugin()
    plugin.memory_store = FakeStore(None)
    command.plugin = plugin

    output = await _run_health(command)

    assert "ERROR: no memory KB configured" in output
    assert "metadata filter probe skipped" in output
    assert "Result: ERROR" in output
    assert plugin.records == {}
