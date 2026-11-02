from __future__ import annotations

import json
from datetime import datetime, timezone

import pytest

from components.knowledge_engine.memory_engine import LongTermMemoryEngine
from langbot_plugin.api.entities.builtin.rag.context import RetrievalContext
from store.memory_store import MemoryStore
from store.recall import bounded_profile, matches_filters, select_memories

NOW = datetime(2026, 11, 2, tzinfo=timezone.utc)


def record(item_id, content=None, **metadata):
    return {
        "id": item_id,
        "score": 0.001,
        "metadata": {
            "content": content or item_id,
            "user_key": "bot:group_room",
            "sender_id": "alice",
            "timestamp": "2026-01-01T00:00:00Z",
            "status": "active",
            "importance": "2",
            **metadata,
        },
    }


class Plugin:
    def __init__(self, records):
        self.records = records
        self.memory_store = MemoryStore(self)
        self.calls = []

    async def invoke_embedding(self, _model, _texts):
        return [[1.0]]

    async def vector_search(self, **_kwargs):
        self.calls.append(_kwargs)
        # Deliberately ignore filters: the caller must still recheck them.
        return self.records

    async def vector_list(self, collection_id, filters=None, **_kwargs):
        items = [
            item for item in self.records if matches_filters(item["metadata"], filters)
        ]
        return {"items": items, "total": len(items)}


def test_backend_score_scale_and_zero_values_do_not_change_selection():
    records = [record("first"), record("second")]
    baseline = [r["id"] for r in select_memories(records, "different wording", now=NOW)]
    records[0]["score"] = 0
    records[1]["score"] = 100000
    assert [
        r["id"] for r in select_memories(records, "different wording", now=NOW)
    ] == baseline


def test_current_validity_and_explicit_history_have_distinct_semantics():
    records = [
        record("expired", valid_until="2026-11-02T00:00:00Z"),
        record("future", valid_from="2026-11-03T00:00:00Z"),
        record("legacy"),
        record("current", valid_from="2026-11-02T00:00:00Z"),
    ]
    assert {r["id"] for r in select_memories(records, "unrelated", now=NOW)} == {
        "legacy",
        "current",
    }
    assert len(select_memories(records, "unrelated", historical=True, now=NOW)) == 4


def test_old_timestamp_does_not_age_out_stable_or_legacy_facts():
    records = [
        record("preference", "Alice prefers tea", timestamp="2000-01-01T00:00:00Z"),
        record("recent", event_at="2026-11-02T00:00:00Z"),
    ]
    assert (
        select_memories(records, "preferences", top_k=1, now=NOW)[0]["id"]
        == "preference"
    )


def test_importance_and_explicit_event_recency_are_secondary_signals():
    records = [record(str(i)) for i in range(10)]
    records[-1]["metadata"].update(importance="5", event_at="2026-11-02T00:00:00Z")
    selected = [r["id"] for r in select_memories(records, "other", top_k=10, now=NOW)]
    assert selected[0] == "0"
    assert selected.index("9") < selected.index("8")


def test_duplicate_facts_do_not_collapse_distinct_speakers_or_events():
    records = [
        record("a", "Meeting Friday"),
        record("copy", "Meeting Friday"),
        record("bob", "Meeting Friday", sender_id="bob"),
        record("later", "Meeting Friday", event_at="2026-11-03T00:00:00Z"),
    ]
    assert {
        r["id"] for r in select_memories(records, "meeting", top_k=10, now=NOW)
    } == {"a", "bob", "later"}


def test_complete_records_and_json_remain_within_budget():
    huge = record("huge", "Fact " * 2000)
    small = record("small", "A complete source fact")
    assert select_memories([huge, small], "other", max_chars=1000) == [small]
    assert select_memories([small], "other", max_chars=1) == []
    assert bounded_profile("Profile " * 1000) == ""
    assert bounded_profile("A whole profile") == "A whole profile"
    assert (
        len(
            json.dumps(
                select_memories([huge, small], "other", max_chars=1000),
                ensure_ascii=False,
            )
        )
        <= 1000
    )


def test_summary_and_its_sources_do_not_repeat_the_same_evidence():
    summary = record(
        "summary", "Agreed milestones", consolidation_source_ids='["source"]'
    )
    selected = select_memories(
        [summary, record("source", "Agreed milestone")], "other", top_k=5
    )
    assert len(selected) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "filter_name,filter_value",
    [
        ("sender_id", "bob"),
        ("sender_name", "Bob"),
        ("source", "import"),
        ("importance_min", 5),
        ("time_after", "2027-01-01T00:00:00Z"),
    ],
)
async def test_exact_id_cannot_bypass_other_filters(filter_name, filter_value):
    plugin = Plugin([record("target", source="agent", sender_name="Alice")])
    result = await plugin.memory_store.search_episodes(
        "kb", "emb", "target", user_key="bot:group_room", **{filter_name: filter_value}
    )
    assert result == []


@pytest.mark.asyncio
async def test_time_filter_is_recorded_time_and_allows_expired_active_history():
    plugin = Plugin([record("expired", valid_until="2001-01-01T00:00:00Z")])
    assert (
        await plugin.memory_store.search_episodes(
            "kb",
            "emb",
            "expired",
            user_key="bot:group_room",
            include_statuses=["active"],
        )
        == []
    )
    historical = await plugin.memory_store.search_episodes(
        "kb",
        "emb",
        "expired",
        user_key="bot:group_room",
        time_after="2026-01-01T00:00:00Z",
    )
    assert historical[0]["id"] == "expired"


@pytest.mark.asyncio
async def test_engine_uses_same_validity_and_scope_selection():
    plugin = Plugin(
        [
            record("wrong-scope", user_key="other"),
            record("expired", valid_until="2001-01-01T00:00:00Z"),
            record("valid"),
        ]
    )
    engine = LongTermMemoryEngine()
    engine.plugin = plugin
    response = await engine.retrieve(
        RetrievalContext(
            query="other",
            knowledge_base_id="kb",
            creation_settings={"embedding_model_uuid": "emb"},
            retrieval_settings={
                "session_name": "group_room",
                "bot_uuid": "bot",
                "sender_id": "alice",
            },
        )
    )
    assert [entry.id for entry in response.results] == ["valid"]


@pytest.mark.asyncio
async def test_string_time_ranges_are_checked_locally_not_pushed_to_chroma():
    plugin = Plugin(
        [
            record("old", timestamp="2000-01-01T00:00:00Z"),
            record("new", timestamp="2026-01-01T00:00:00Z"),
        ]
    )
    result = await plugin.memory_store.search_episodes(
        "kb",
        "emb",
        "other",
        user_key="bot:group_room",
        time_after="2020-01-01T00:00:00Z",
        importance_min=2,
    )
    assert [item["id"] for item in result] == ["new"]
    assert plugin.calls[0]["filters"] == {"user_key": "bot:group_room"}


@pytest.mark.asyncio
async def test_tool_omits_whole_oversized_profile_without_corrupting_json():
    from types import SimpleNamespace
    from unittest.mock import AsyncMock
    from components.tools.recall_memory import RecallMemory
    from langbot_plugin.api.entities.builtin.provider.session import (
        Session,
        LauncherTypes,
    )

    store = SimpleNamespace(
        resolve_user_context=AsyncMock(
            return_value=(
                "scope",
                "scope",
                "kb",
                "session",
                {"embedding_model_uuid": "emb"},
            )
        ),
        search_episodes=AsyncMock(return_value=[]),
        load_session_profile=AsyncMock(return_value={"text": "Complete fact " * 1000}),
        load_speaker_profile=AsyncMock(
            return_value={"text": "Alice prefers concise replies"}
        ),
        format_profile_text=lambda profile: profile["text"],
        has_profile_data=bool,
        EPISODE_STATUSES={"active"},
    )
    tool = RecallMemory()
    tool.plugin = SimpleNamespace(memory_store=store)
    result = json.loads(
        await tool.call(
            {"query": "preferences"},
            Session(
                launcher_type=LauncherTypes.GROUP,
                launcher_id="room",
                sender_id="alice",
                bot_uuid="bot",
            ),
            1,
        )
    )
    assert result["session_profile"] == ""
    assert result["speaker_profile"] == "Alice prefers concise replies"
    assert result["profiles_omitted_for_budget"] == ["session"]
