from __future__ import annotations

import pytest

from store.memory_store import MemoryStore


class FakeStoragePlugin:
    def __init__(self):
        self.storage: dict[str, bytes] = {}

    async def get_plugin_storage_keys(self) -> list[str]:
        return list(self.storage)

    async def get_plugin_storage(self, key: str) -> bytes:
        if key not in self.storage:
            raise KeyError(key)
        return self.storage[key]

    async def set_plugin_storage(self, key: str, data: bytes) -> None:
        self.storage[key] = data


class FakeVectorPlugin(FakeStoragePlugin):
    """Simulates a vector backend, optionally one that ignores metadata filters."""

    def __init__(self, *, leak: bool = False, delete_leak: bool = False):
        super().__init__()
        self.leak = leak
        self.delete_leak = delete_leak
        self.records: dict[str, dict] = {}
        self.deleted: list[str] = []

    async def invoke_embedding(self, _model, texts):
        return [[float(i + 1)] for i, _ in enumerate(texts)]

    async def vector_upsert(self, collection_id, vectors, ids, metadata=None, documents=None):
        for index, item_id in enumerate(ids):
            self.records[item_id] = {"id": item_id, "metadata": metadata[index]}

    async def vector_search(self, collection_id, query_vector, top_k=5, filters=None, **_kwargs):
        user_key = (filters or {}).get("user_key")
        items = list(self.records.values())
        if not self.leak and user_key:
            items = [it for it in items if it["metadata"].get("user_key") == user_key]
        return items[:top_k]

    async def vector_list(self, collection_id, filters=None, limit=20, offset=0):
        user_key = (filters or {}).get("user_key")
        items = list(self.records.values())
        if not self.leak and user_key:
            items = [it for it in items if it["metadata"].get("user_key") == user_key]
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
            ids = list(self.records)
            if not self.delete_leak and user_key:
                ids = [i for i in ids if self.records[i]["metadata"].get("user_key") == user_key]
            for item_id in ids:
                self.records.pop(item_id)
                self.deleted.append(item_id)
                count += 1
        return count


@pytest.mark.asyncio
async def test_probe_reports_ok_and_cleans_up_for_compliant_backend():
    plugin = FakeVectorPlugin()
    store = MemoryStore(plugin)

    result = await store.run_metadata_filter_probe("kb-1", "emb-1")

    assert result["status"] == "OK"
    details = " ".join(check["detail"] for check in result["checks"])
    assert "vector_search respects user_key metadata filter" in details
    # All temporary probe records are removed regardless of path.
    assert plugin.records == {}


@pytest.mark.asyncio
async def test_probe_flags_metadata_filter_leak():
    plugin = FakeVectorPlugin(leak=True)
    store = MemoryStore(plugin)

    result = await store.run_metadata_filter_probe("kb-1", "emb-1")

    assert result["status"] == "ERROR"
    statuses = {check["id"]: check["status"] for check in result["checks"]}
    assert statuses["search"] == "ERROR"
    assert plugin.records == {}


@pytest.mark.asyncio
async def test_injection_snapshot_round_trips_and_overwrites():
    plugin = FakeStoragePlugin()
    store = MemoryStore(plugin)

    assert await store.get_injection_snapshot("scope-a") is None

    await store.save_injection_snapshot("scope-a", {"injected": True, "block_count": 1})
    await store.save_injection_snapshot("scope-a", {"injected": False, "block_count": 0})

    snapshot = await store.get_injection_snapshot("scope-a")
    assert snapshot == {"injected": False, "block_count": 0}
    # Snapshots are isolated per scope.
    assert await store.get_injection_snapshot("scope-b") is None
