from __future__ import annotations

import asyncio
import json

import pytest

from store.consolidation import proposal_key
from store.memory_store import MemoryStore
from test_semantic_consolidation import SemanticPlugin, add_source, preview


@pytest.mark.asyncio
@pytest.mark.parametrize("delete", ["forget", "collection"])
async def test_inflight_preview_finishes_before_delete_clears_its_draft(delete):
    plugin = SemanticPlugin()
    add_source(plugin, "one", "Fact to forget")
    store = MemoryStore(plugin)
    entered, release = asyncio.Event(), asyncio.Event()
    original = plugin.invoke_llm

    async def blocked(*args):
        entered.set()
        await release.wait()
        return await original(*args)

    plugin.invoke_llm = blocked
    draft_task = asyncio.create_task(preview(store))
    await entered.wait()
    deletion = store.delete_episode_by_id("kb", "one", "scope") if delete == "forget" else store.remove_kb_config("kb")
    delete_task = asyncio.create_task(deletion)
    await asyncio.sleep(0)
    assert not delete_task.done()
    release.set()
    await asyncio.wait_for(asyncio.gather(draft_task, delete_task), timeout=2)
    assert await store._read_json(proposal_key("kb", "scope")) == {}
    if delete == "collection":
        assert "kb" not in await store.get_kb_configs()
    else:
        assert "one" not in plugin.records


@pytest.mark.asyncio
async def test_collection_delete_clears_only_its_drafts_and_rejects_late_preview():
    plugin = SemanticPlugin()
    add_source(plugin, "one", "Fact to forget")
    store = MemoryStore(plugin)
    await preview(store)
    other_key = proposal_key("other-kb", "scope")
    other = {"id": "other", "collection_id": "other-kb", "summary": "Other collection private fact"}
    plugin.storage[other_key] = json.dumps(other).encode()
    await store.remove_kb_config("kb")
    assert await store._read_json(proposal_key("kb", "scope")) == {}
    assert await store._read_json(other_key) == other
    calls = plugin.model_calls
    with pytest.raises(ValueError, match="no longer configured"):
        await preview(store)
    assert plugin.model_calls == calls
    assert await store._read_json(proposal_key("kb", "scope")) == {}


@pytest.mark.asyncio
async def test_summary_validity_does_not_round_source_microseconds_outward():
    plugin = SemanticPlugin()
    add_source(
        plugin,
        "one",
        "Fractional validity",
        valid_from="2020-01-01T00:00:00.123456Z",
        valid_until="2030-01-01T00:00:00.654321Z",
    )
    store = MemoryStore(plugin)
    draft = await preview(store)
    summary = (await store.apply_consolidation("kb", "emb", "scope", proposal_id=draft["proposal_id"]))[
        "summary_episode"
    ]
    assert summary["metadata"]["valid_from"] == "2020-01-01T00:00:00.123456Z"
    assert summary["metadata"]["valid_until"] == "2030-01-01T00:00:00.654321Z"
