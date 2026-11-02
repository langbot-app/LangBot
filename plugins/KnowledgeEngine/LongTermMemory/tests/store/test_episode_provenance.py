from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from components.event_listener.memory_injector import MemoryInjector
from components.tools.remember import Remember
from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes, Session
from store.episode_provenance import normalize_provenance
from store.memory_store import MemoryStore


class Plugin:
    def __init__(self):
        self.storage = {}
        self.records = {}
        self.memory_store = MemoryStore(self)

    async def get_plugin_storage_keys(self):
        return list(self.storage)

    async def get_plugin_storage(self, key):
        if key not in self.storage:
            raise KeyError(key)
        return self.storage[key]

    async def set_plugin_storage(self, key, value):
        self.storage[key] = value

    async def invoke_embedding(self, _model, texts):
        return [[1.0] for _ in texts]

    async def vector_upsert(self, collection_id, vectors, ids, metadata, documents):
        for item_id, meta, text in zip(ids, metadata, documents):
            self.records[item_id] = {
                "id": item_id,
                "metadata": dict(meta),
                "document": text,
            }

    async def vector_list(self, collection_id, filters=None, limit=20, offset=0):
        records = [
            r
            for r in self.records.values()
            if not filters or r["metadata"].get("user_key") == filters["user_key"]
        ]
        return {"items": records[offset : offset + limit], "total": len(records)}


FACT = {
    "event_at": "2026-11-03T12:00:00+08:00",
    "valid_from": "2026-11-01T00:00:00Z",
    "valid_until": "2026-11-04T00:00:00Z",
    "source_ref": "message:original-7",
    "claim_type": "user_statement",
}


def test_explicit_time_is_normalized_without_reinterpreting_storage_time():
    normalized = normalize_provenance(FACT)
    assert normalized["event_at"] == "2026-11-03T04:00:00Z"
    assert normalized["valid_from"] == FACT["valid_from"]
    assert normalized["source_ref"] == FACT["source_ref"]
    assert normalize_provenance({})["claim_type"] == "unknown"


@pytest.mark.parametrize(
    "bad",
    [
        {"event_at": "tomorrow"},
        {"event_at": "0001-01-01T00:00:00+01:00"},
        {"event_at": "2026-11-03T12:00:00"},
        {"valid_until": None},
        {"valid_from": "2026-11-04T00:00:00Z", "valid_until": "2026-11-04T00:00:00Z"},
        {"valid_from": "2026-11-05T00:00:00Z", "valid_until": "2026-11-04T00:00:00Z"},
        {"source_ref": "x" * 1025},
        {"claim_type": "verified"},
    ],
)
def test_bad_or_ambiguous_provenance_is_rejected(bad):
    with pytest.raises(ValueError):
        normalize_provenance(bad)


@pytest.mark.asyncio
async def test_write_export_import_and_status_changes_preserve_provenance():
    plugin = Plugin()
    store = plugin.memory_store
    written = await store.add_episode("kb", "emb", "scope", "Meeting tomorrow", **FACT)
    assert written["timestamp"] != written["event_at"]
    assert written["claim_type"] == "user_statement"
    exported = await store.export_episodes_by_user("kb", "scope")
    assert exported[0]["event_at"] == "2026-11-03T04:00:00Z"
    assert exported[0]["source_ref"] == FACT["source_ref"]
    imported = await store.import_episodes_for_user(
        "kb", "emb", "another-scope", exported
    )
    assert imported[0]["event_at"] == exported[0]["event_at"]
    assert imported[0]["valid_until"] == exported[0]["valid_until"]
    assert imported[0]["claim_type"] == "user_statement"
    await store.update_episode_status("kb", "emb", written["id"], "scope", "archived")
    persisted = await store.get_episode_by_id("kb", written["id"], "scope")
    assert persisted["source_ref"] == FACT["source_ref"]
    assert persisted["event_at"] == "2026-11-03T04:00:00Z"


@pytest.mark.asyncio
async def test_bad_time_later_in_import_is_rejected_before_any_write():
    plugin = Plugin()
    with pytest.raises(ValueError):
        await plugin.memory_store.import_episodes_for_user(
            "kb",
            "emb",
            "scope",
            [
                {"content": "Good legacy fact"},
                {"content": "Bad date", "event_at": "tomorrow"},
            ],
        )
    assert plugin.records == {}


@pytest.mark.asyncio
async def test_legacy_records_do_not_gain_invented_event_time_or_evidence():
    plugin = Plugin()
    plugin.records["old"] = {
        "id": "old",
        "metadata": {
            "content": "Old fact",
            "user_key": "scope",
            "timestamp": "2020-01-01T00:00:00Z",
        },
    }
    old = await plugin.memory_store.get_episode_by_id("kb", "old", "scope")
    assert old["timestamp"] == "2020-01-01T00:00:00Z"
    assert old["event_at"] == ""
    assert old["claim_type"] == "unknown"


@pytest.mark.asyncio
async def test_remember_passes_time_and_declared_provenance_to_store():
    plugin = Plugin()
    await plugin.memory_store.save_kb_config(
        "kb", {"embedding_model_uuid": "emb", "isolation": "session"}
    )
    tool = Remember()
    tool.plugin = plugin
    session = Session(
        launcher_type=LauncherTypes.PERSON,
        launcher_id="user",
        sender_id="user",
        bot_uuid="bot",
    )
    result = await tool.call({"content": "Meeting tomorrow", **FACT}, session, 7)
    assert result.startswith("Remembered:"), result
    assert (
        next(iter(plugin.records.values()))["metadata"]["source_ref"]
        == "message:original-7"
    )
    rejected = await tool.call(
        {"content": "Ambiguous", "event_at": "tomorrow"}, session, 8
    )
    assert rejected.startswith("Error:"), rejected
    assert len(plugin.records) == 1


def test_missing_user_input_is_not_invented():
    assert MemoryInjector._candidate_text_from_query_vars({}) == ""
    assert (
        MemoryInjector._candidate_text_from_query_vars(
            {"user_message_text": "I prefer tea"}
        )
        == "I prefer tea"
    )


@pytest.mark.asyncio
async def test_candidate_acceptance_preserves_declared_provenance():
    plugin = Plugin()
    store = plugin.memory_store
    entry = await store.append_memory_candidate(
        "session",
        "scope",
        "l2_episode",
        {"content": "Meeting tomorrow", **FACT},
        "User text",
    )
    accepted = await store.accept_memory_candidate(
        "session",
        entry["candidate_id"],
        collection_id="kb",
        embedding_model_uuid="emb",
        user_key="scope",
    )
    assert accepted["accepted_result"]["episode"]["source_ref"] == FACT["source_ref"]


@pytest.mark.asyncio
@pytest.mark.parametrize("has_user_input", [False, True])
async def test_automatic_candidates_mark_only_actual_user_input_as_statement(
    monkeypatch,
    has_user_input,
):
    class API:
        async def get_bot_uuid(self):
            return "bot"

        async def get_query_vars(self):
            return (
                {"user_message_text": "I have a meeting tomorrow"}
                if has_user_input
                else {}
            )

    monkeypatch.setattr(
        "components.event_listener.memory_injector.QueryBasedAPIProxy",
        lambda **_: API(),
    )
    plugin = Plugin()
    plugin.plugin_runtime_handler = object()
    await plugin.memory_store.save_kb_config(
        "kb", {"candidate_extraction_enabled": True, "candidate_auto_apply": False}
    )
    injector = MemoryInjector()
    injector.plugin = plugin
    event_ctx = SimpleNamespace(
        query_id=7,
        event=SimpleNamespace(
            session=Session(
                launcher_type=LauncherTypes.PERSON,
                launcher_id="user",
                sender_id="user",
                bot_uuid="bot",
            ),
            sender_id="user",
            response_text="Assistant invented a preference",
        ),
    )
    await injector._extract_memory_candidates(event_ctx)
    entries, _ = await plugin.memory_store.list_memory_candidates("bot:person_user")
    if not has_user_input:
        assert entries == []
        return
    assert len(entries) == 1
    assert entries[0]["payload"]["claim_type"] == "user_statement"
    assert entries[0]["payload"]["source_ref"] == "query:7"
    assert "Assistant invented" not in entries[0]["payload"]["content"]


@pytest.mark.asyncio
@pytest.mark.parametrize("invalid", [False, True])
async def test_document_ingestion_validates_and_preserves_provenance(invalid):
    from components.knowledge_engine.memory_engine import LongTermMemoryEngine
    from langbot_plugin.api.entities.builtin.rag.models import IngestionContext
    from langbot_plugin.api.entities.builtin.rag.enums import DocumentStatus

    plugin = Plugin()
    entries = [{"content": "Event", **FACT}]
    if invalid:
        entries.append({"content": "Invalid later event", "valid_from": "next week"})

    async def read_file(_path):
        return json.dumps(entries).encode()

    plugin.get_knowledge_file_stream = read_file
    engine = LongTermMemoryEngine()
    engine.plugin = plugin
    result = await engine.ingest(
        IngestionContext(
            file_object={
                "metadata": {
                    "document_id": "doc-1",
                    "filename": "memory.json",
                    "knowledge_base_id": "kb",
                    "file_size": 22,
                    "mime_type": "application/json",
                },
                "storage_path": "memory.json",
            },
            knowledge_base_id="kb",
            creation_settings={"embedding_model_uuid": "emb"},
        )
    )
    if invalid:
        assert result.status == DocumentStatus.FAILED
        assert plugin.records == {}
    else:
        assert result.status == DocumentStatus.COMPLETED
        meta = next(iter(plugin.records.values()))["metadata"]
        assert meta["event_at"] == "2026-11-03T04:00:00Z"
        assert meta["claim_type"] == "user_statement"
        assert meta["source_ref"] == FACT["source_ref"]
