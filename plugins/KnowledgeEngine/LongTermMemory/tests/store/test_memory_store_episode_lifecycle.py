from __future__ import annotations

import pytest

from store.memory_store import MemoryStore


class FakeVectorPlugin:
    def __init__(self, *, fail_hybrid: bool = False):
        self.records: dict[str, dict] = {}
        self.upserts: list[tuple[str, dict]] = []
        self.fail_hybrid = fail_hybrid
        self.search_calls: list[dict] = []
        self.delete_calls: list[dict] = []

    async def get_plugin_storage_keys(self) -> list[str]:
        return []

    async def invoke_embedding(self, _embedding_model_uuid: str, texts: list[str]) -> list[list[float]]:
        return [[float(index + 1)] for index, _ in enumerate(texts)]

    async def vector_upsert(self, collection_id, vectors, ids, metadata=None, documents=None):
        for index, item_id in enumerate(ids):
            meta = dict(metadata[index])
            self.records[item_id] = {
                "id": item_id,
                "metadata": meta,
                "document": documents[index],
                "distance": 0.0,
                "score": 1.0,
            }
            self.upserts.append((item_id, meta))

    async def vector_search(self, collection_id, query_vector, top_k=5, filters=None, **_kwargs):
        self.search_calls.append(_kwargs)
        if _kwargs.get("search_type") == "hybrid" and self.fail_hybrid:
            raise RuntimeError("hybrid unavailable")
        return self._filtered(filters)[:top_k]

    async def vector_list(self, collection_id, filters=None, limit=20, offset=0):
        items = self._filtered(filters)
        return {"items": items[offset: offset + limit], "total": len(items)}

    async def vector_delete(self, collection_id, file_ids=None, filters=None):
        self.delete_calls.append({
            "collection_id": collection_id,
            "file_ids": file_ids,
            "filters": filters,
        })
        deleted = 0
        ids = set(file_ids or [])
        for item_id in list(self.records):
            if ids and item_id not in ids:
                continue
            if filters:
                scoped = self._filtered(filters)
                if item_id not in {item["id"] for item in scoped}:
                    continue
            self.records.pop(item_id, None)
            deleted += 1
        return deleted

    def _filtered(self, filters=None):
        items = list(self.records.values())
        if not filters:
            return items

        conditions = filters.get("$and") if isinstance(filters, dict) else None
        if conditions is None:
            conditions = [filters]

        for condition in conditions:
            for key, value in condition.items():
                if isinstance(value, dict):
                    continue
                items = [
                    item
                    for item in items
                    if item["metadata"].get(key) == value
                ]
        return items


def _record(
    item_id: str,
    *,
    user_key: str = "user-1",
    status: str | None = "active",
    content: str | None = None,
) -> dict:
    metadata = {
        "episode_id": item_id,
        "content": content or f"memory {item_id}",
        "tags": "",
        "importance": "2",
        "timestamp": "2026-01-01T00:00:00Z",
        "user_key": user_key,
        "source": "agent",
    }
    if status is not None:
        metadata["status"] = status
    return {
        "id": item_id,
        "metadata": metadata,
        "document": metadata["content"],
        "distance": 0.0,
        "score": 1.0,
    }


@pytest.mark.asyncio
async def test_add_episode_defaults_to_active_status():
    plugin = FakeVectorPlugin()
    store = MemoryStore(plugin)

    episode = await store.add_episode(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        user_key="user-1",
        content="User likes concise answers",
    )

    assert episode["status"] == "active"
    stored = next(iter(plugin.records.values()))
    assert stored["metadata"]["status"] == "active"


@pytest.mark.asyncio
async def test_search_and_list_default_to_active_and_legacy_records():
    plugin = FakeVectorPlugin()
    plugin.records = {
        "active-1": _record("active-1", status="active"),
        "legacy-1": _record("legacy-1", status=None),
        "superseded-1": _record("superseded-1", status="superseded"),
        "archived-1": _record("archived-1", status="archived"),
    }
    store = MemoryStore(plugin)

    search_results = await store.search_episodes(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        query="memory",
        user_key="user-1",
        top_k=10,
    )
    listed, total = await store.list_episodes(
        collection_id="kb-1",
        user_key="user-1",
        limit=10,
        offset=0,
    )

    assert {item["id"] for item in search_results} == {"active-1", "legacy-1"}
    assert {item["id"] for item in listed} == {"active-1", "legacy-1"}
    assert total == 2


@pytest.mark.asyncio
async def test_include_superseded_can_inspect_hidden_records():
    plugin = FakeVectorPlugin()
    plugin.records = {
        "active-1": _record("active-1", status="active"),
        "superseded-1": _record("superseded-1", status="superseded"),
    }
    store = MemoryStore(plugin)

    results = await store.search_episodes(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        query="memory",
        user_key="user-1",
        top_k=10,
        include_statuses=["active", "superseded"],
    )

    assert {item["id"] for item in results} == {"active-1", "superseded-1"}
    assert next(item for item in results if item["id"] == "superseded-1")["status"] == "superseded"


@pytest.mark.asyncio
async def test_explicit_replacement_marks_old_episode_status():
    plugin = FakeVectorPlugin()
    plugin.records = {
        "old-1": _record("old-1", status="active", content="User prefers tea"),
    }
    store = MemoryStore(plugin)

    await store.add_episode(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        user_key="user-1",
        content="Correction: user prefers coffee",
        tags=["correction"],
        supersedes=["old-1"],
    )

    assert plugin.records["old-1"]["metadata"]["status"] == "superseded"
    assert plugin.records["old-1"]["metadata"]["superseded_by"]


@pytest.mark.asyncio
async def test_update_episode_status_preserves_scope_and_metadata():
    plugin = FakeVectorPlugin()
    plugin.records = {
        "ep-1": _record("ep-1", status="active", content="Scoped memory"),
        "other": _record("other", user_key="user-2", status="active"),
    }
    store = MemoryStore(plugin)

    updated = await store.update_episode_status(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        episode_id="ep-1",
        user_key="user-1",
        status="archived",
    )
    missing = await store.update_episode_status(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        episode_id="other",
        user_key="user-1",
        status="archived",
    )

    assert updated is not None
    assert updated["status"] == "archived"
    assert plugin.records["ep-1"]["metadata"]["status"] == "archived"
    assert plugin.records["ep-1"]["metadata"]["content"] == "Scoped memory"
    assert plugin.records["other"]["metadata"]["status"] == "active"
    assert missing is None


@pytest.mark.asyncio
async def test_search_episodes_uses_hybrid_and_falls_back_to_vector():
    plugin = FakeVectorPlugin(fail_hybrid=True)
    plugin.records = {
        "ep-1": _record("ep-1", status="active", content="Hybrid fallback memory"),
    }
    store = MemoryStore(plugin)

    results = await store.search_episodes(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        query="Hybrid",
        user_key="user-1",
        retrieval_strategy="auto",
        vector_weight=0.6,
    )

    assert [item["id"] for item in results] == ["ep-1"]
    assert plugin.search_calls[0] == {
        "search_type": "hybrid",
        "query_text": "Hybrid",
        "vector_weight": 0.6,
    }
    assert plugin.search_calls[1] == {}


@pytest.mark.asyncio
async def test_search_episodes_exact_episode_id_does_not_depend_on_vector_similarity():
    plugin = FakeVectorPlugin()
    plugin.records = {
        "episode-special": _record("episode-special", status="active", content="Exact ID memory"),
        "other": _record("other", status="active", content="Other memory"),
    }
    store = MemoryStore(plugin)

    results = await store.search_episodes(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        query="episode-special",
        user_key="user-1",
        top_k=1,
        retrieval_strategy="vector",
    )

    assert [item["id"] for item in results] == ["episode-special"]


@pytest.mark.asyncio
async def test_export_episodes_by_user_includes_only_current_scope_and_statuses():
    plugin = FakeVectorPlugin()
    plugin.records = {
        "active-1": _record("active-1", user_key="user-1", status="active"),
        "archived-1": _record("archived-1", user_key="user-1", status="archived"),
        "other": _record("other", user_key="user-2", status="active"),
    }
    store = MemoryStore(plugin)

    exported = await store.export_episodes_by_user(
        collection_id="kb-1",
        user_key="user-1",
        include_statuses=["active", "archived"],
    )

    assert {item["id"] for item in exported} == {"active-1", "archived-1"}
    assert all(item["status"] in {"active", "archived"} for item in exported)


@pytest.mark.asyncio
async def test_import_episodes_for_user_forces_current_scope_and_new_ids():
    plugin = FakeVectorPlugin()
    plugin.records = {
        "external-id": _record("external-id", user_key="other-scope", status="active"),
    }
    store = MemoryStore(plugin)

    imported = await store.import_episodes_for_user(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        user_key="current-scope",
        episodes=[
            {
                "id": "external-id",
                "content": "Imported memory",
                "tags": ["migration"],
                "importance": 4,
                "timestamp": "2026-01-03T00:00:00Z",
                "user_key": "other-scope",
                "sender_id": "u-1",
                "sender_name": "Alice",
                "source": "backup",
                "status": "archived",
            }
        ],
        bot_uuid="bot-1",
    )

    imported_id = imported[0]["id"]
    assert imported_id != "external-id"
    assert imported[0]["imported_episode_id"] == "external-id"
    assert plugin.records["external-id"]["metadata"]["user_key"] == "other-scope"
    assert plugin.records[imported_id]["metadata"]["user_key"] == "current-scope"
    assert plugin.records[imported_id]["metadata"]["imported_episode_id"] == "external-id"
    assert plugin.records[imported_id]["metadata"]["status"] == "archived"


@pytest.mark.asyncio
async def test_delete_episodes_by_filters_is_scope_safe():
    plugin = FakeVectorPlugin()
    plugin.records = {
        "scoped-old": _record("scoped-old", user_key="user-1", status="archived"),
        "scoped-active": _record("scoped-active", user_key="user-1", status="active"),
        "other-old": _record("other-old", user_key="user-2", status="archived"),
    }
    store = MemoryStore(plugin)

    deleted, episode_ids = await store.delete_episodes_by_filters(
        collection_id="kb-1",
        user_key="user-1",
        include_statuses=["archived"],
    )

    assert deleted == 1
    assert episode_ids == ["scoped-old"]
    assert "scoped-old" not in plugin.records
    assert "scoped-active" in plugin.records
    assert "other-old" in plugin.records


@pytest.mark.asyncio
async def test_consolidation_preview_does_not_modify_records():
    plugin = FakeVectorPlugin()
    plugin.records = {
        "old-low": _record(
            "old-low",
            user_key="user-1",
            status="active",
            content="Older low importance memory",
        ),
        "hidden": _record("hidden", user_key="user-1", status="superseded"),
        "other": _record("other", user_key="user-2", status="superseded"),
    }
    plugin.records["old-low"]["metadata"]["importance"] = "1"
    plugin.records["old-low"]["metadata"]["timestamp"] = "2020-01-01T00:00:00Z"
    store = MemoryStore(plugin)

    preview = await store.preview_consolidation(
        collection_id="kb-1",
        user_key="user-1",
        min_age_days=7,
        max_candidates=20,
    )

    assert set(preview["candidate_episode_ids"]) == {"old-low", "hidden"}
    assert set(preview["episodes_to_archive"]) == {"hidden"}
    assert preview["summary_episode"] == ""
    assert plugin.records["old-low"]["metadata"]["status"] == "active"
    assert plugin.records["hidden"]["metadata"]["status"] == "superseded"
    assert "other" in plugin.records
    assert plugin.upserts == []


@pytest.mark.asyncio
async def test_apply_consolidation_archives_only_superseded_records():
    plugin = FakeVectorPlugin()
    plugin.records = {
        "old-low": _record(
            "old-low",
            user_key="user-1",
            status="active",
            content="Older low importance memory",
        ),
        "hidden": _record("hidden", user_key="user-1", status="superseded"),
        "other": _record("other", user_key="user-2", status="superseded"),
    }
    plugin.records["old-low"]["metadata"]["importance"] = "1"
    plugin.records["old-low"]["metadata"]["timestamp"] = "2020-01-01T00:00:00Z"
    store = MemoryStore(plugin)

    result = await store.apply_consolidation(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        user_key="user-1",
        min_age_days=7,
        max_candidates=20,
    )

    assert set(result["archived_episode_ids"]) == {"hidden"}
    assert plugin.records["old-low"]["metadata"]["status"] == "active"
    assert plugin.records["hidden"]["metadata"]["status"] == "archived"
    assert plugin.records["other"]["metadata"]["status"] == "superseded"
    assert result["summary_episode"] is None


class FakeStorageVectorPlugin(FakeVectorPlugin):
    def __init__(self):
        super().__init__()
        self.storage: dict[str, bytes] = {}

    async def get_plugin_storage_keys(self) -> list[str]:
        return list(self.storage)

    async def get_plugin_storage(self, key: str) -> bytes:
        if key not in self.storage:
            raise KeyError(key)
        return self.storage[key]

    async def set_plugin_storage(self, key: str, value: bytes) -> None:
        self.storage[key] = value


@pytest.mark.asyncio
async def test_memory_candidate_reject_remains_inspectable():
    plugin = FakeStorageVectorPlugin()
    store = MemoryStore(plugin)

    candidate = await store.append_memory_candidate(
        scope_key="scope-1",
        user_key="user-1",
        candidate_type="l2_episode",
        payload={"content": "Alice has a meeting tomorrow", "tags": ["candidate"]},
        reason="Temporal fact",
    )
    rejected = await store.reject_memory_candidate("scope-1", candidate["candidate_id"])
    pending, pending_total = await store.list_memory_candidates("scope-1")
    rejected_items, rejected_total = await store.list_memory_candidates(
        "scope-1",
        include_statuses=["rejected"],
    )

    assert rejected["status"] == "rejected"
    assert pending == []
    assert pending_total == 0
    assert rejected_total == 1
    assert rejected_items[0]["candidate_id"] == candidate["candidate_id"]


@pytest.mark.asyncio
async def test_accept_l2_candidate_uses_normal_episode_write_path():
    plugin = FakeStorageVectorPlugin()
    store = MemoryStore(plugin)
    candidate = await store.append_memory_candidate(
        scope_key="scope-1",
        user_key="user-1",
        candidate_type="l2_episode",
        payload={"content": "Alice has a meeting tomorrow", "tags": ["schedule"]},
        reason="Temporal fact",
        sender_id="u-1",
        sender_name="Alice",
    )

    accepted = await store.accept_memory_candidate(
        "scope-1",
        candidate["candidate_id"],
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        user_key="user-1",
        bot_uuid="bot-1",
    )

    assert accepted["status"] == "accepted"
    assert accepted["accepted_result"]["type"] == "episode"
    episode = accepted["accepted_result"]["episode"]
    assert episode["source"] == "candidate"
    assert episode["sender_id"] == "u-1"
    assert episode["id"] in plugin.records


@pytest.mark.asyncio
@pytest.mark.parametrize("tag", ["correction", "fact-update", "clarification"])
async def test_similar_correction_without_explicit_target_preserves_old_fact(tag):
    plugin = FakeVectorPlugin()
    plugin.records["old"] = _record("old", content="Alice visits Shanghai on Friday")
    store = MemoryStore(plugin)
    await store.add_episode("kb", "emb", "user-1", "Bob visits Shanghai on Friday", tags=[tag])
    assert plugin.records["old"]["metadata"]["status"] == "active"
    assert len(plugin.records) == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", ["missing", "other-speaker", "other-scope", "archived"])
async def test_replacement_rejects_invalid_target_before_any_write(invalid):
    plugin = FakeVectorPlugin()
    record = _record("old")
    record["metadata"]["sender_id"] = "alice"
    if invalid == "other-speaker":
        record["metadata"]["sender_id"] = "bob"
    elif invalid == "other-scope":
        record["metadata"]["user_key"] = "other"
    elif invalid == "archived":
        record["metadata"]["status"] = "archived"
    if invalid != "missing":
        plugin.records["old"] = record
    store = MemoryStore(plugin)
    with pytest.raises(ValueError, match="Replacement targets"):
        await store.add_episode("kb", "emb", "user-1", "Corrected fact", sender_id="alice", supersedes=["old"])
    assert plugin.upserts == []


@pytest.mark.asyncio
async def test_exact_match_after_backend_top_k_boundary_is_still_ranked():
    plugin = FakeVectorPlugin()
    plugin.records = {f"noise-{i}": _record(f"noise-{i}", content="Unrelated note") for i in range(49)}
    plugin.records["answer"] = _record("answer", content="Release rendezvous is at Cedar Pier")
    result = await MemoryStore(plugin).search_episodes("kb", "emb", "release rendezvous", user_key="user-1", top_k=1)
    assert [episode["id"] for episode in result] == ["answer"]


@pytest.mark.asyncio
async def test_consolidation_preserves_old_active_facts_and_keeps_obsolete_facts_hidden():
    plugin = FakeVectorPlugin()
    plugin.records["active"] = _record("active", content="Alice chose PostgreSQL because of JSON queries")
    plugin.records["outdated"] = _record("outdated", status="superseded", content="Alice chose MySQL")
    store = MemoryStore(plugin)
    result = await store.apply_consolidation("kb", "emb", "user-1", min_age_days=0)
    assert result["summary_episode"] is None
    assert result["archived_episode_ids"] == ["outdated"]
    recalled = await store.search_episodes("kb", "emb", "database choice", user_key="user-1")
    assert [episode["content"] for episode in recalled] == ["Alice chose PostgreSQL because of JSON queries"]
    assert plugin.records["active"]["metadata"]["status"] == "active"
    second = await store.apply_consolidation("kb", "emb", "user-1", min_age_days=0)
    assert second["summary_episode"] is None
    assert second["archived_episode_ids"] == []


@pytest.mark.asyncio
@pytest.mark.parametrize("targets", ["old", [""], [1], ["old"] * 21])
async def test_replacement_target_input_is_validated_before_writing(targets):
    plugin = FakeVectorPlugin()
    with pytest.raises(ValueError, match="supersedes"):
        await MemoryStore(plugin).add_episode("kb", "emb", "user-1", "New fact", supersedes=targets)
    assert plugin.upserts == []
