from __future__ import annotations

import asyncio
import json

import pytest

from main import LongTermMemoryPlugin
from components.knowledge_engine.memory_engine import LongTermMemoryEngine
from langbot_plugin.api.entities.builtin.rag.models import IngestionContext
from store.memory_store import MemoryStore


class StorageFixture:
    """Installation-bound Host storage that can fail or stall one call."""

    def __init__(self):
        self.storage: dict[str, bytes] = {}
        self.fail_keys: set[str] = set()
        self.write_stalls: dict[str, tuple[asyncio.Event, asyncio.Event]] = {}
        self.read_stalls: dict[str, tuple[asyncio.Event, asyncio.Event]] = {}

    def stall_write(self, key: str) -> tuple[asyncio.Event, asyncio.Event]:
        """Suspend writes to *key*; returns the (started, release) events."""
        events = (asyncio.Event(), asyncio.Event())
        self.write_stalls[key] = events
        return events

    def stall_read(self, key: str) -> tuple[asyncio.Event, asyncio.Event]:
        """Suspend reads of *key*; returns the (started, release) events."""
        events = (asyncio.Event(), asyncio.Event())
        self.read_stalls[key] = events
        return events

    async def get_plugin_storage(self, key: str) -> bytes:
        stall = self.read_stalls.get(key)
        if stall is not None:
            started, release = stall
            started.set()
            await release.wait()
        if key not in self.storage:
            raise KeyError(key)
        return self.storage[key]

    async def get_plugin_storage_keys(self) -> list[str]:
        return list(self.storage)

    async def set_plugin_storage(self, key: str, data: bytes) -> None:
        stall = self.write_stalls.get(key)
        if stall is not None:
            started, release = stall
            started.set()
            await release.wait()
        if key in self.fail_keys:
            # A dispatched commit whose outcome the caller never learns.
            raise RuntimeError("host write outcome unknown")
        self.storage[key] = data


class BoundStorageFixture(StorageFixture):
    """Host fixture that reports one certified installation binding."""

    def __init__(self, binding):
        super().__init__()
        self.binding = binding

    def get_installation_binding(self):
        return self.binding


class VectorStorageFixture(StorageFixture):
    """Host fixture with a vector backend, for the nested episode writes."""

    def __init__(self):
        super().__init__()
        self.records: dict[str, dict] = {}

    async def get_knowledge_file_stream(self, _path):
        return b'[{"content":"memory"}]'

    async def invoke_embedding(self, _model, texts):
        return [[1.0, 0.0] for _ in texts]

    async def vector_upsert(self, collection_id, vectors, ids, metadata=None, documents=None):
        for index, item_id in enumerate(ids):
            self.records[item_id] = {"id": item_id, "metadata": metadata[index]}

    async def vector_search(self, collection_id, query_vector, top_k=5, filters=None, **_kwargs):
        user_key = (filters or {}).get("user_key")
        items = [
            {**record, "distance": 0.0}
            for record in self.records.values()
            if record["metadata"].get("user_key") == user_key
        ]
        return items[:top_k]

    async def vector_list(self, collection_id, filters=None, limit=20, offset=0):
        items = list(self.records.values())
        return {"items": items[offset: offset + limit], "total": len(items)}

    async def vector_delete(self, collection_id, file_ids=None, filters=None):
        if filters and "document_id" in filters:
            file_ids = [
                item_id for item_id, record in self.records.items()
                if record["metadata"].get("document_id") == filters["document_id"]
            ]
        if not file_ids:
            return 0
        deleted = 0
        for item_id in file_ids:
            if item_id in self.records:
                self.records.pop(item_id)
                deleted += 1
        return deleted


def engine_context():
    return IngestionContext(
        file_object={
            "metadata": {
                "document_id": "doc-1", "filename": "memory.json",
                "knowledge_base_id": "kb-1", "file_size": 22,
                "mime_type": "application/json",
            },
            "storage_path": "memory.json",
        },
        knowledge_base_id="kb-1",
        creation_settings={"embedding_model_uuid": "embedding-1"},
    )


@pytest.mark.asyncio
async def test_engine_document_delete_cannot_race_a_status_update():
    plugin = VectorStorageFixture()
    plugin.records["episode-1"] = {"id": "episode-1", "metadata": {
        "document_id": "doc-1", "content": "memory", "user_key": "user-1",
    }}
    plugin.memory_store = MemoryStore(plugin)
    engine = LongTermMemoryEngine()
    engine.plugin = plugin
    started, release = asyncio.Event(), asyncio.Event()

    async def embedding(_model, _texts):
        started.set()
        await release.wait()
        return [[1.0, 0.0]]

    plugin.invoke_embedding = embedding
    update = asyncio.create_task(plugin.memory_store.update_episode_status(
        "kb-1", "embedding-1", "episode-1", "user-1", "archived",
    ))
    await started.wait()
    deletion = asyncio.create_task(engine.delete_document("kb-1", "doc-1"))
    try:
        await asyncio.sleep(0)
        assert "episode-1" in plugin.records
        assert not deletion.done()
    finally:
        release.set()
        await asyncio.gather(update, deletion)
    assert plugin.records == {}


@pytest.mark.asyncio
async def test_engine_document_delete_cannot_split_a_multibatch_import():
    plugin = VectorStorageFixture()
    plugin.memory_store = MemoryStore(plugin)
    engine = LongTermMemoryEngine()
    engine.plugin = plugin
    started, release = asyncio.Event(), asyncio.Event()
    upsert = plugin.vector_upsert

    async def file_stream(_path):
        return json.dumps([{"content": f"memory {i}"} for i in range(33)]).encode()

    async def write_batch(**kwargs):
        await upsert(**kwargs)
        if not started.is_set():
            started.set()
            await release.wait()

    plugin.get_knowledge_file_stream = file_stream
    plugin.vector_upsert = write_batch
    ingestion = asyncio.create_task(engine.ingest(engine_context()))
    await started.wait()
    deletion = asyncio.create_task(engine.delete_document("kb-1", "doc-1"))
    await asyncio.sleep(0)
    release.set()
    result, deleted = await asyncio.gather(ingestion, deletion)
    assert result.chunks_created == 33
    assert deleted is True
    assert plugin.records == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["ingest", "delete"])
async def test_engine_collection_writes_respect_existing_fence(operation):
    plugin = VectorStorageFixture()
    plugin.memory_store = MemoryStore(plugin)
    engine = LongTermMemoryEngine()
    engine.plugin = plugin
    await plugin.memory_store._writes.fence(plugin, "kb-1", "unknown prior mutation")

    with pytest.raises(RuntimeError, match="fenced"):
        if operation == "ingest":
            await engine.ingest(engine_context())
        else:
            await engine.delete_document("kb-1", "doc-1")
    assert plugin.records == {}


@pytest.mark.asyncio
@pytest.mark.parametrize("operation", ["ingest", "delete"])
async def test_engine_unknown_mutation_fences_the_collection(operation):
    plugin = VectorStorageFixture()
    plugin.memory_store = MemoryStore(plugin)
    engine = LongTermMemoryEngine()
    engine.plugin = plugin

    async def unknown_mutation(**_kwargs):
        raise RuntimeError("host mutation outcome unknown")

    plugin.vector_upsert = unknown_mutation
    plugin.vector_delete = unknown_mutation
    with pytest.raises(RuntimeError, match="outcome unknown"):
        if operation == "ingest":
            await engine.ingest(engine_context())
        else:
            await engine.delete_document("kb-1", "doc-1")
    assert plugin.memory_store.is_fenced("kb-1")


async def audit(store: MemoryStore, scope_key: str) -> None:
    await store.append_audit_entry(scope_key, "remember", "episode", "ep-1", "stored")


@pytest.mark.asyncio
@pytest.mark.parametrize("persisted_fence", [False, True])
async def test_restart_refuses_writes_until_persisted_fences_can_be_read(persisted_fence):
    storage = StorageFixture()
    if persisted_fence:
        await MemoryStore(storage)._writes.fence(storage, "scope-a", "unknown prior write")
    restarted = MemoryStore(storage)
    list_keys = storage.get_plugin_storage_keys
    before = dict(storage.storage)

    async def unavailable_keys():
        raise TimeoutError("storage listing unavailable")

    storage.get_plugin_storage_keys = unavailable_keys
    with pytest.raises(RuntimeError, match="Could not load persisted memory fences"):
        await audit(restarted, "scope-a")
    assert storage.storage == before

    storage.get_plugin_storage_keys = list_keys
    if persisted_fence:
        with pytest.raises(RuntimeError, match="fenced"):
            await audit(restarted, "scope-a")
        await restarted.clear_fence("scope-a")
    await audit(restarted, "scope-a")
    assert (await restarted.list_audit_entries("scope-a"))[1] == 1


@pytest.mark.asyncio
async def test_ambiguous_host_write_fences_only_that_scope_and_survives_restart():
    storage = StorageFixture()
    store = MemoryStore(plugin=storage)
    storage.fail_keys.add("audit:scope-a")

    with pytest.raises(RuntimeError, match="outcome unknown"):
        await audit(store, "scope-a")
    assert store.is_fenced("scope-a")
    assert not store.is_fenced("scope-b")

    with pytest.raises(RuntimeError, match="fenced"):
        await audit(store, "scope-a")
    # A sibling memory space still accepts writes and reads are never fenced.
    await audit(store, "scope-b")
    _, total = await store.list_audit_entries("scope-a")
    assert total == 0

    # The marker is persisted, so a restarted worker refuses that scope only.
    storage.fail_keys.clear()
    restarted = MemoryStore(plugin=storage)
    with pytest.raises(RuntimeError, match="fenced"):
        await audit(restarted, "scope-a")
    assert not restarted.is_fenced("scope-b")
    await audit(restarted, "scope-b")

    # Acknowledging reconciliation is the path back to a writable scope.
    await restarted.clear_fence("scope-a")
    assert not restarted.is_fenced("scope-a")
    await audit(restarted, "scope-a")


@pytest.mark.asyncio
async def test_validation_error_before_dispatch_does_not_fence():
    storage = StorageFixture()
    store = MemoryStore(plugin=storage)

    with pytest.raises(ValueError, match="candidate_type"):
        await store.append_memory_candidate("scope-a", "scope-a", "bogus", {}, "reason")

    assert not store.is_fenced("scope-a")
    await store.append_memory_candidate("scope-a", "scope-a", "l1_profile", {}, "reason")


@pytest.mark.asyncio
async def test_cancellation_before_dispatch_does_not_fence():
    storage = StorageFixture()
    store = MemoryStore(plugin=storage)
    started, release = storage.stall_read("candidates:scope-a")

    task = asyncio.create_task(
        store.append_memory_candidate("scope-a", "scope-a", "l2_episode", {}, "reason")
    )
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    release.set()

    # Nothing was dispatched, so the scope stays usable.
    assert not store.is_fenced("scope-a")
    await store.append_memory_candidate("scope-a", "scope-a", "l2_episode", {}, "reason")


@pytest.mark.asyncio
async def test_cancelled_caller_settles_a_dispatched_commit_and_only_fences_unknowns():
    storage = StorageFixture()
    store = MemoryStore(plugin=storage)
    started, release = storage.stall_write("candidates:scope-a")

    task = asyncio.create_task(
        store.append_memory_candidate("scope-a", "scope-a", "l2_episode", {}, "reason")
    )
    await started.wait()
    task.cancel()
    await asyncio.sleep(0)
    # The dispatched commit is settled before the lock is released.
    assert not task.done()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task

    # The Host acknowledged the commit, so the scope is not ambiguous.
    assert not store.is_fenced("scope-a")
    _, total = await store.list_memory_candidates("scope-a")
    assert total == 1

    # A dispatched commit that fails after the caller was cancelled is unknown.
    started, release = storage.stall_write("candidates:scope-b")
    storage.fail_keys.add("candidates:scope-b")
    unknown = asyncio.create_task(
        store.append_memory_candidate("scope-b", "scope-b", "l2_episode", {}, "reason")
    )
    await started.wait()
    unknown.cancel()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await unknown
    assert store.is_fenced("scope-b")
    assert not store.is_fenced("scope-a")


@pytest.mark.asyncio
async def test_accepting_a_profile_candidate_reenters_its_own_scope():
    storage = VectorStorageFixture()
    store = MemoryStore(plugin=storage)
    candidate = await store.append_memory_candidate(
        "scope-a",
        "scope-a",
        "l1_profile",
        {"target_scope": "session", "field": "notes", "action": "add", "value": "prefers concise replies"},
        "reason",
    )

    # The nested profile write shares its scope_key with the accepting call, so it
    # must not wait on the lock its own caller already holds.
    accepted = await asyncio.wait_for(
        store.accept_memory_candidate(
            "scope-a",
            candidate["candidate_id"],
            collection_id="kb-1",
            embedding_model_uuid="emb-1",
            user_key="scope-a",
        ),
        timeout=5,
    )

    assert accepted["status"] == "accepted"
    assert accepted["accepted_result"]["type"] == "profile"
    profile = await store.load_session_profile("scope-a")
    assert "prefers concise replies" in profile["notes"]


@pytest.mark.asyncio
async def test_accepting_an_episode_candidate_writes_into_its_collection():
    storage = VectorStorageFixture()
    store = MemoryStore(plugin=storage)
    candidate = await store.append_memory_candidate(
        "scope-a",
        "scope-a",
        "l2_episode",
        {"content": "Alice lives in Berlin", "tags": ["fact"]},
        "reason",
    )

    accepted = await asyncio.wait_for(
        store.accept_memory_candidate(
            "scope-a",
            candidate["candidate_id"],
            collection_id="kb-1",
            embedding_model_uuid="emb-1",
            user_key="scope-a",
        ),
        timeout=5,
    )

    episode = accepted["accepted_result"]["episode"]
    assert storage.records[episode["id"]]["metadata"]["content"] == "Alice lives in Berlin"


@pytest.mark.asyncio
async def test_nested_serialized_episode_write_does_not_self_lock():
    storage = VectorStorageFixture()
    store = MemoryStore(plugin=storage)

    original = await store.add_episode(
        collection_id="kb-1",
        embedding_model_uuid="emb-1",
        user_key="user-1",
        content="Alice lives in Berlin",
        importance=2,
    )

    # add_episode nests _auto_supersede for the same collection scope, which must
    # not wait on the lock its own caller already holds.
    created = await asyncio.wait_for(
        store.add_episode(
            collection_id="kb-1",
            embedding_model_uuid="emb-1",
            user_key="user-1",
            content="Alice lives in Munich",
            tags=["correction"],
            importance=3,
        ),
        timeout=5,
    )

    assert created["id"] in storage.records
    assert storage.records[original["id"]]["metadata"]["status"] == "superseded"


@pytest.mark.asyncio
async def test_profile_writes_are_serialized_and_fenced_per_scope():
    storage = StorageFixture()
    store = MemoryStore(plugin=storage)

    await store.update_session_profile_field("scope-a", "notes", "add", "likes tea")
    await store.update_speaker_profile_field("scope-a", "sender-1", "name", "set", "Alice")
    assert (await store.load_session_profile("scope-a"))["notes"] == "likes tea"
    assert (await store.load_speaker_profile("scope-a", "sender-1"))["name"] == "Alice"

    # The session profile is grouped by its scope_key, so an ambiguous profile
    # write fences that memory scope only.
    storage.fail_keys.add("ps:scope-a")
    with pytest.raises(RuntimeError, match="outcome unknown"):
        await store.update_session_profile_field("scope-a", "notes", "add", "likes coffee")
    assert store.is_fenced("scope-a")
    assert not store.is_fenced("scope-b")

    with pytest.raises(RuntimeError, match="fenced"):
        await store.update_speaker_profile_field("scope-a", "sender-1", "name", "set", "Bob")
    await store.update_speaker_profile_field("scope-b", "sender-1", "name", "set", "Carol")
    assert (await store.load_speaker_profile("scope-a", "sender-1"))["name"] == "Alice"
    assert (await store.load_speaker_profile("scope-b", "sender-1"))["name"] == "Carol"


@pytest.mark.asyncio
async def test_installation_wide_map_write_fences_every_scope_until_cleared():
    storage = StorageFixture()
    store = MemoryStore(plugin=storage)
    storage.fail_keys.add(MemoryStore._KB_CONFIGS_KEY)

    # kb_configs is one record shared by every KB, so its read-modify-write stays
    # installation-scoped: keying it by the collection id would let two KBs
    # overwrite each other's entry.
    with pytest.raises(RuntimeError, match="outcome unknown"):
        await store.save_kb_config("kb-1", {"embedding_model_uuid": "emb-1"})
    assert store.is_fenced(None)
    with pytest.raises(RuntimeError, match="fenced"):
        await store.save_kb_config("kb-2", {"embedding_model_uuid": "emb-2"})
    with pytest.raises(RuntimeError, match="fenced"):
        await audit(store, "scope-a")

    storage.fail_keys.clear()
    await store.clear_fence(None)
    await store.save_kb_config("kb-2", {"embedding_model_uuid": "emb-2"})
    await audit(store, "scope-a")
    assert (await store.get_kb_configs())["kb-2"] == {"embedding_model_uuid": "emb-2"}


@pytest.mark.asyncio
async def test_unregistering_a_kb_clears_that_collection_fence():
    storage = StorageFixture()
    store = MemoryStore(plugin=storage)
    storage.fail_keys.add("audit:kb-1")

    with pytest.raises(RuntimeError, match="outcome unknown"):
        await audit(store, "kb-1")
    assert store.is_fenced("kb-1")

    # Unregistering the KB deletes the fenced object, so its fence is cleared
    # even while it is fenced: deletion is the operator path out.
    storage.fail_keys.clear()
    await store.remove_kb_config("kb-1")
    assert not store.is_fenced("kb-1")
    await audit(store, "kb-1")


@pytest.mark.asyncio
async def test_revocation_releases_process_local_state_and_keeps_persistence():
    binding = ("workspace", "installation")
    storage = BoundStorageFixture(binding)
    store = MemoryStore(plugin=storage)
    storage.fail_keys.add("audit:scope-a")

    with pytest.raises(RuntimeError, match="outcome unknown"):
        await audit(store, "scope-a")
    state = store._writes
    assert (binding, "scope-a") in state._locks
    assert state.is_fenced(binding, "scope-a")

    plugin = LongTermMemoryPlugin()
    plugin.memory_store = store
    await plugin.on_installation_revoked(binding)

    # One object graph serves every installation, so the hook is the only place
    # that can drop a revoked binding's locks and fence cache.
    assert (binding, "scope-a") not in state._locks
    assert not state.is_fenced(binding, "scope-a")
    assert state._fenced.get(binding) is None

    # The fence itself is persisted, so a restarted worker still refuses it.
    storage.fail_keys.clear()
    restarted = MemoryStore(plugin=storage)
    assert await restarted.list_fences()
    with pytest.raises(RuntimeError, match="fenced"):
        await audit(restarted, "scope-a")
    await restarted.clear_fence("scope-a")
    await audit(restarted, "scope-a")
    assert await restarted.list_fences() == []
