from __future__ import annotations

import json

import pytest

from components.knowledge_engine.memory_engine import LongTermMemoryEngine
from store.consolidation import proposal_key
from store.memory_store import MemoryStore


class DocumentPlugin:
    def __init__(self):
        self.records = {}
        self.storage = {}
        self.document_pages = []
        self.document_deletes = 0
        self.scope_pages = 0
        self.fail_summary_delete = False
        self.memory_store = MemoryStore(self)

    async def get_plugin_storage(self, key):
        return self.storage[key]

    async def get_plugin_storage_keys(self):
        return list(self.storage)

    async def set_plugin_storage(self, key, data):
        self.storage[key] = data

    def selected(self, filters):
        records = list(self.records.values())
        for condition in filters.get("$and", [filters]):
            for key, value in condition.items():
                records = [item for item in records if item["metadata"].get(key) == value]
        return records

    async def vector_list(self, collection_id, filters, limit, offset):
        assert collection_id == "kb"
        if "document_id" in filters:
            self.document_pages.append(offset)
        else:
            self.scope_pages += 1
        records = self.selected(filters)
        return {"items": records[offset : offset + limit], "total": len(records)}

    async def vector_delete(self, collection_id, filters):
        assert collection_id == "kb"
        records = self.selected(filters)
        if "document_id" in filters:
            self.document_deletes += 1
            assert "summary-a" not in self.records
            assert "summary-b" not in self.records
            assert json.loads(self.storage[proposal_key("kb", "a")]) == {}
            assert json.loads(self.storage[proposal_key("kb", "b")]) == {}
        elif self.fail_summary_delete:
            raise RuntimeError("summary deletion outcome unknown")
        for item in records:
            self.records.pop(item["id"])
        return len(records)


def record(plugin, episode_id, scope, *, document="", references=None):
    metadata = {
        "episode_id": episode_id,
        "content": f"Fact {episode_id}",
        "user_key": scope,
        "source": "import",
        "status": "active",
        "timestamp": "2026-01-01T00:00:00Z",
        "importance": "2",
        "sender_id": "alice",
    }
    if document:
        metadata["document_id"] = document
    if references is not None:
        metadata["source"] = "consolidation"
        metadata["consolidation_source_ids"] = json.dumps(references)
    plugin.records[episode_id] = {"id": episode_id, "metadata": metadata}


def setup_plugin():
    plugin = DocumentPlugin()
    for index in range(205):
        record(plugin, f"document-{index:03d}", "a" if index % 2 == 0 else "b", document="document")
    record(plugin, "summary-a", "a", references=["document-000"])
    record(plugin, "summary-b", "b", references=["document-001"])
    record(plugin, "other-scope-summary", "other", references=["document-000"])
    record(plugin, "unrelated-summary", "a", references=["outside-document"])
    record(plugin, "outside-document", "a", document="other-document")
    for scope, source in (("a", "document-000"), ("b", "document-001")):
        plugin.storage[proposal_key("kb", scope)] = json.dumps(
            {"source_ids": [source], "summary": "pending source fact"}
        ).encode()
    engine = LongTermMemoryEngine()
    engine.plugin = plugin
    return plugin, engine


@pytest.mark.asyncio
async def test_document_delete_invalidates_derived_memories_in_each_source_scope_before_sources():
    plugin, engine = setup_plugin()
    assert await engine.delete_document("kb", "document") is True
    assert plugin.document_pages == [0, 100, 200]
    assert plugin.document_deletes == 1
    assert plugin.scope_pages < 30
    assert set(plugin.records) == {"outside-document", "unrelated-summary", "other-scope-summary"}


@pytest.mark.asyncio
async def test_failed_derived_invalidation_never_deletes_document_sources():
    plugin, engine = setup_plugin()
    plugin.fail_summary_delete = True
    with pytest.raises(RuntimeError, match="summary deletion outcome"):
        await engine._delete_document_vectors("kb", "document")
    assert plugin.document_deletes == 0
    assert sum(item["metadata"].get("document_id") == "document" for item in plugin.records.values()) == 205
    assert "outside-document" in plugin.records
    assert "other-scope-summary" in plugin.records


@pytest.mark.asyncio
async def test_document_delete_fails_closed_when_backend_returns_another_document():
    plugin, engine = setup_plugin()
    original = plugin.vector_list

    async def unfiltered(*args, **kwargs):
        page = await original(*args, **kwargs)
        if "document_id" in kwargs["filters"]:
            return {"items": [plugin.records["outside-document"]], "total": 1}
        return page

    plugin.vector_list = unfiltered
    with pytest.raises(ValueError, match="outside the requested document"):
        await engine._delete_document_vectors("kb", "document")
    assert plugin.document_deletes == 0
    assert len(plugin.records) == 210
