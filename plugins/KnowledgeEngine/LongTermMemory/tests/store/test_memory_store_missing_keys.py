from __future__ import annotations

import json

import pytest

from components.knowledge_engine.memory_engine import LongTermMemoryEngine
from langbot_plugin.entities.io.errors import ActionCallError, ActionCallTimeoutError
from store.memory_store import MemoryStore


class HostStorage:
    def __init__(self, prefix="", error=None):
        self.storage = {}
        self.prefix = prefix
        self.error = error
        self.memory_store = MemoryStore(self)

    async def get_plugin_storage(self, key):
        if self.error is not None:
            raise self.error
        if key not in self.storage:
            raise ActionCallError(f"{self.prefix}Storage with key {key} not found")
        return self.storage[key]

    async def get_plugin_storage_keys(self):
        return list(self.storage)

    async def set_plugin_storage(self, key, value):
        self.storage[key] = value


@pytest.mark.asyncio
@pytest.mark.parametrize("prefix", ["", "ActionCallError: ", "ActionCallError: ActionCallError: "])
async def test_first_kb_creation_handles_host_missing_key(prefix):
    plugin = HostStorage(prefix=prefix)
    engine = LongTermMemoryEngine()
    engine.plugin = plugin
    config = {"embedding_model_uuid": "embedding-1", "isolation": "session"}

    await engine.on_knowledge_base_create("kb-1", config)

    assert json.loads(plugin.storage["kb_configs"]) == {"kb-1": config}
    assert await plugin.memory_store.get_kb_configs() == {"kb-1": config}
    with pytest.raises(ValueError, match="Only one memory knowledge base"):
        await engine.on_knowledge_base_create("kb-2", config)


@pytest.mark.asyncio
@pytest.mark.parametrize("error", [
    ActionCallError("Permission denied"),
    ActionCallError("Storage with key another_key not found"),
    ActionCallError("Denied: ActionCallError: Storage with key kb_configs not found"),
    ActionCallTimeoutError("Storage read timed out"),
])
async def test_storage_read_failures_are_not_empty_config(error):
    plugin = HostStorage(error=error)

    with pytest.raises(type(error)) as caught:
        await plugin.memory_store.get_kb_configs()

    assert caught.value is error
    assert plugin.storage == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("data", [b"{", b"\xff"])
async def test_corrupt_stored_config_is_not_empty_config(data):
    plugin = HostStorage()
    plugin.storage["kb_configs"] = data

    with pytest.raises(ValueError, match="corrupt JSON"):
        await plugin.memory_store.get_kb_configs()
