from __future__ import annotations

import copy
import json
from types import SimpleNamespace

import pytest

from store.memory_store import MemoryStore


class SemanticPlugin:
    def __init__(self):
        self.records = {}
        self.storage = {"kb_configs": json.dumps({"kb": {"embedding_model_uuid": "emb"}}).encode()}
        self.response = None
        self.drop_summary = False
        self.model_calls = 0

    async def get_plugin_storage(self, key):
        return self.storage[key]

    async def get_plugin_storage_keys(self):
        return list(self.storage)

    async def set_plugin_storage(self, key, value):
        self.storage[key] = value

    async def invoke_embedding(self, model, texts):
        return [[1.0] for _ in texts]

    async def invoke_llm(self, model, messages):
        self.model_calls += 1
        assert model == "summary-model"
        assert "untrusted data" in messages[0].content
        sources = json.loads(messages[-1].content)
        response = self.response or {
            "facts": [{"text": source["content"], "source_ids": [source["id"]]} for source in sources]
        }
        return SimpleNamespace(content=json.dumps(response))

    async def vector_upsert(self, collection_id, vectors, ids, metadata, documents):
        for episode_id, meta in zip(ids, metadata):
            if self.drop_summary and meta.get("source") == "consolidation":
                continue
            self.records[episode_id] = {"id": episode_id, "metadata": copy.deepcopy(meta)}

    def filtered(self, filters):
        records = list(self.records.values())
        for condition in filters.get("$and", [filters]):
            for key, value in condition.items():
                records = [record for record in records if record["metadata"].get(key) == value]
        return records

    async def vector_list(self, collection_id, filters, limit, offset):
        records = self.filtered(filters)
        return {"items": records[offset : offset + limit], "total": len(records)}

    async def vector_delete(self, collection_id, filters):
        records = self.filtered(filters)
        for record in records:
            del self.records[record["id"]]
        return len(records)


def add_source(plugin, episode_id, content, user_key="scope", **metadata):
    plugin.records[episode_id] = {
        "id": episode_id,
        "metadata": {
            "episode_id": episode_id,
            "content": content,
            "user_key": user_key,
            "importance": "2",
            "timestamp": "2020-01-01T00:00:00Z",
            "sender_id": "alice",
            "status": "active",
            "source": "agent",
            "tags": "",
            **metadata,
        },
    }


async def preview(store):
    return await store.preview_consolidation("kb", "scope", min_age_days=0, summary_model_uuid="summary-model")


@pytest.mark.asyncio
async def test_semantic_preview_is_reviewed_before_write_and_sources_remain_active():
    plugin = SemanticPlugin()
    add_source(
        plugin,
        "decision",
        "Alice chose PostgreSQL because of JSON queries.",
        valid_from="2020-01-01T00:00:00Z",
        valid_until="2030-01-01T00:00:00Z",
    )
    add_source(
        plugin,
        "date",
        "The migration is scheduled for Friday.",
        valid_from="2021-01-01T00:00:00Z",
        valid_until="2029-01-01T00:00:00Z",
    )
    store = MemoryStore(plugin)
    draft = await preview(store)
    assert len(plugin.records) == 2
    assert [source["content"] for source in draft["source_records"]] == [
        "Alice chose PostgreSQL because of JSON queries.",
        "The migration is scheduled for Friday.",
    ]
    result = await store.apply_consolidation("kb", "emb", "scope", proposal_id=draft["proposal_id"])
    meta = result["summary_episode"]["metadata"]
    assert meta["claim_type"] == "inference"
    assert set(json.loads(meta["consolidation_source_ids"])) == {"decision", "date"}
    assert meta["valid_from"] == "2021-01-01T00:00:00Z"
    assert meta["valid_until"] == "2029-01-01T00:00:00Z"
    assert result["archived_episode_ids"] == []
    assert all(plugin.records[key]["metadata"]["status"] == "active" for key in ("decision", "date"))
    with pytest.raises(ValueError, match="proposal"):
        await store.apply_consolidation("kb", "emb", "scope", proposal_id=draft["proposal_id"])


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "facts",
    [[], [{"text": "Invented fact", "source_ids": ["outside"]}], [{"text": "Only one fact", "source_ids": ["one"]}]],
)
async def test_model_schema_cannot_select_scope_or_omit_sources(facts):
    plugin = SemanticPlugin()
    add_source(plugin, "one", "Fact one")
    add_source(plugin, "two", "Fact two")
    plugin.response = {"facts": facts}
    with pytest.raises(ValueError):
        await preview(MemoryStore(plugin))
    assert len(plugin.records) == 2
    assert not any(key.startswith("ltm.consolidation.") for key in plugin.storage)


@pytest.mark.asyncio
async def test_valid_citation_is_only_a_draft_not_proof_of_model_quality():
    plugin = SemanticPlugin()
    add_source(plugin, "one", "Alice chose PostgreSQL")
    plugin.response = {"facts": [{"text": "Alice chose Oracle", "source_ids": ["one"]}]}
    draft = await preview(MemoryStore(plugin))
    assert "Alice chose Oracle" in draft["summary_episode"]
    assert "Alice chose PostgreSQL" == draft["source_records"][0]["content"]
    assert any("does not prove semantic correctness" in note for note in draft["risk_notes"])
    assert list(plugin.records) == ["one"]


@pytest.mark.asyncio
@pytest.mark.parametrize("change", ["content", "status", "scope"])
async def test_stale_or_cross_scope_proposal_cannot_write(change):
    plugin = SemanticPlugin()
    add_source(plugin, "one", "Fact one")
    store = MemoryStore(plugin)
    draft = await preview(store)
    scope = "scope"
    if change == "scope":
        scope = "other"
    else:
        plugin.records["one"]["metadata"][change] = "changed"
    with pytest.raises(ValueError):
        await store.apply_consolidation("kb", "emb", scope, proposal_id=draft["proposal_id"])
    assert list(plugin.records) == ["one"]


@pytest.mark.asyncio
async def test_unverified_summary_never_hides_source_facts():
    plugin = SemanticPlugin()
    add_source(plugin, "one", "Fact one")
    store = MemoryStore(plugin)
    draft = await preview(store)
    plugin.drop_summary = True
    with pytest.raises(RuntimeError, match="verified"):
        await store.apply_consolidation("kb", "emb", "scope", proposal_id=draft["proposal_id"])
    assert plugin.records["one"]["metadata"]["status"] == "active"


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["forget", "supersede", "archive"])
async def test_source_change_invalidates_summary_without_touching_other_scope(action):
    plugin = SemanticPlugin()
    add_source(plugin, "one", "Original fact")
    add_source(plugin, "two", "Another fact")
    add_source(
        plugin, "outside", "Private fact", user_key="other", source="consolidation", consolidation_source_ids='["one"]'
    )
    store = MemoryStore(plugin)
    draft = await preview(store)
    summary = (await store.apply_consolidation("kb", "emb", "scope", proposal_id=draft["proposal_id"]))[
        "summary_episode"
    ]
    if action == "forget":
        await store.delete_episode_by_id("kb", "one", "scope")
        assert "one" not in plugin.records
    else:
        await store.update_episode_status(
            "kb", "emb", "one", "scope", "superseded" if action == "supersede" else "archived"
        )
    assert summary["id"] not in plugin.records
    assert plugin.records["two"]["metadata"]["status"] == "active"
    assert "outside" in plugin.records


@pytest.mark.asyncio
async def test_explicit_correction_invalidates_derived_summary_and_keeps_other_facts():
    plugin = SemanticPlugin()
    add_source(plugin, "one", "Alice chose PostgreSQL")
    add_source(plugin, "two", "Friday is the release date")
    store = MemoryStore(plugin)
    draft = await preview(store)
    summary = (await store.apply_consolidation("kb", "emb", "scope", proposal_id=draft["proposal_id"]))[
        "summary_episode"
    ]
    replacement = await store.add_episode(
        "kb", "emb", "scope", "Alice chose SQLite instead", sender_id="alice", supersedes=["one"]
    )
    assert plugin.records["one"]["metadata"]["superseded_by"] == replacement["id"]
    assert summary["id"] not in plugin.records
    assert plugin.records["two"]["metadata"]["status"] == "active"


@pytest.mark.asyncio
@pytest.mark.parametrize("bulk", [False, True])
async def test_forget_clears_pending_draft_with_source_text(bulk):
    from store.consolidation import proposal_key

    plugin = SemanticPlugin()
    add_source(plugin, "one", "Source to forget")
    add_source(plugin, "other", "Other scope source", user_key="other")
    store = MemoryStore(plugin)
    draft = await preview(store)
    if bulk:
        await store.delete_episodes_by_user("kb", "scope")
    else:
        await store.delete_episodes_by_filters("kb", "scope", sender_id="alice")
    assert await store._read_json(proposal_key("kb", "scope")) == {}
    assert "one" not in plugin.records and "other" in plugin.records
    with pytest.raises(ValueError, match="proposal"):
        await store.apply_consolidation("kb", "emb", "scope", proposal_id=draft["proposal_id"])


@pytest.mark.asyncio
async def test_expired_sources_never_trigger_a_model_call():
    plugin = SemanticPlugin()
    add_source(plugin, "one", "Old plan", valid_until="2020-01-02T00:00:00Z")
    with pytest.raises(ValueError, match="currently valid"):
        await preview(MemoryStore(plugin))
    assert plugin.model_calls == 0


@pytest.mark.asyncio
@pytest.mark.parametrize("value", ["nonsense", "2020-01-01T00:00:00", 10])
async def test_invalid_source_validity_fails_before_model_call(value):
    plugin = SemanticPlugin()
    add_source(plugin, "one", "Fact one", valid_from=value)
    with pytest.raises(ValueError):
        await preview(MemoryStore(plugin))
    assert plugin.model_calls == 0


@pytest.mark.asyncio
async def test_offset_provenance_is_normalized_and_visible_to_reviewer():
    plugin = SemanticPlugin()
    add_source(
        plugin,
        "one",
        "An event",
        valid_from="2020-01-01T09:00:00+09:00",
        valid_until="2030-01-01T09:00:00+09:00",
        event_at="2020-01-02T09:00:00+09:00",
        claim_type="user_statement",
        source_ref="message:one",
    )
    draft = await preview(MemoryStore(plugin))
    source = draft["source_records"][0]
    assert source["event_at"] == "2020-01-02T00:00:00Z"
    assert source["valid_from"] == "2020-01-01T00:00:00Z"
    assert source["claim_type"] == "user_statement"
    assert source["source_ref"] == "message:one"


@pytest.mark.asyncio
async def test_hanging_model_times_out_without_saving_a_proposal(monkeypatch):
    import asyncio
    import store.consolidation as consolidation

    plugin = SemanticPlugin()
    add_source(plugin, "one", "Fact one")

    async def hang(*args):
        await asyncio.sleep(10)

    plugin.invoke_llm = hang
    monkeypatch.setattr(consolidation, "MODEL_TIMEOUT_SECONDS", 0.001)
    with pytest.raises(ValueError, match="timed out"):
        await preview(MemoryStore(plugin))
    assert not any(key.startswith("ltm.consolidation.") for key in plugin.storage)
    assert plugin.records["one"]["metadata"]["status"] == "active"


@pytest.mark.asyncio
async def test_cancelled_model_does_not_leave_an_escaped_write():
    import asyncio

    plugin = SemanticPlugin()
    add_source(plugin, "one", "Fact one")
    entered = asyncio.Event()

    async def hang(*args):
        entered.set()
        await asyncio.sleep(10)

    plugin.invoke_llm = hang
    task = asyncio.create_task(preview(MemoryStore(plugin)))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert not any(key.startswith("ltm.consolidation.") for key in plugin.storage)
    assert list(plugin.records) == ["one"]


def test_summary_validity_preserves_source_subsecond_bounds():
    from store.consolidation import validity

    sources = [{"metadata": {"valid_from": "2020-01-01T00:00:00.123456Z", "valid_until": "2999-01-01T00:00:00.654321Z"}}]
    assert validity(sources) == ("2020-01-01T00:00:00.123456Z", "2999-01-01T00:00:00.654321Z")


@pytest.mark.asyncio
async def test_summary_verification_allows_host_added_scope_metadata():
    class ScopedPlugin(SemanticPlugin):
        async def vector_upsert(self, *args, **kwargs):
            kwargs["metadata"] = [{**metadata, "_langbot_workspace_uuid": "workspace-test"} for metadata in kwargs["metadata"]]
            await super().vector_upsert(*args, **kwargs)

    plugin = ScopedPlugin()
    add_source(plugin, "source", "Alice chose PostgreSQL")
    store = MemoryStore(plugin)
    draft = await preview(store)
    result = await store.apply_consolidation("kb", "emb", "scope", proposal_id=draft["proposal_id"])
    assert result["summary_episode"]["status"] == "active"
    assert result["summary_episode"]["metadata"]["_langbot_workspace_uuid"] == "workspace-test"
    assert plugin.records["source"]["metadata"]["status"] == "active"


@pytest.mark.asyncio
async def test_summary_too_large_for_recall_is_not_published():
    plugin = SemanticPlugin()
    add_source(plugin, "one", "First source fact")
    add_source(plugin, "two", "Second source fact")
    plugin.response = {"facts": [
        {"text": "a" * 2000, "source_ids": ["one"]},
        {"text": "b" * 2000, "source_ids": ["two"]},
    ]}
    store = MemoryStore(plugin)
    draft = await preview(store)
    with pytest.raises(ValueError, match="recall budget"):
        await store.apply_consolidation("kb", "emb", "scope", proposal_id=draft["proposal_id"])
    assert set(plugin.records) == {"one", "two"}
    assert all(item["metadata"]["status"] == "active" for item in plugin.records.values())
