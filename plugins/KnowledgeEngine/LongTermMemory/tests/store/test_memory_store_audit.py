from __future__ import annotations

import json

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


@pytest.mark.asyncio
async def test_audit_entries_are_scoped_and_paginated_newest_first():
    plugin = FakeStoragePlugin()
    store = MemoryStore(plugin)

    first = await store.append_audit_entry(
        scope_key="scope-a",
        user_key="user-a",
        operation="remember",
        target_type="episode",
        target_id="ep-1",
        summary="first",
        query_id=1,
    )
    second = await store.append_audit_entry(
        scope_key="scope-a",
        user_key="user-a",
        operation="forget",
        target_type="episode",
        target_id="ep-2",
        summary="second",
        query_id=2,
    )
    await store.append_audit_entry(
        scope_key="scope-b",
        user_key="user-b",
        operation="remember",
        target_type="episode",
        target_id="ep-other",
        summary="other scope",
    )

    entries, total = await store.list_audit_entries("scope-a", limit=1, offset=0)
    exported = await store.export_audit_entries("scope-a")

    assert total == 2
    assert entries == [second]
    assert exported == [first, second]
    assert json.loads(plugin.storage["audit:scope-a"].decode("utf-8")) == [first, second]
    assert "ep-other" not in json.dumps(exported)
