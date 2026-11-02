from __future__ import annotations

import json
from types import SimpleNamespace

import pytest

from components.event_listener.memory_injector import MemoryInjector
from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes, Session
from store.candidate_extraction import extract_candidates
from test_episode_provenance import Plugin


TEXT = "I do not like coffee. I prefer tea."
QUOTE = "I do not like coffee."
GOOD = [
    {"candidate_type": "l1_profile", "field": "preferences", "evidence_quote": QUOTE}
]


class ModelPlugin(Plugin):
    def __init__(self, response):
        super().__init__()
        self.response = response
        self.invocations = []
        self.plugin_runtime_handler = object()

    async def invoke_llm(self, model, messages):
        self.invocations.append((model, messages))
        if isinstance(self.response, Exception):
            raise self.response
        return SimpleNamespace(content=self.response)


@pytest.mark.asyncio
async def test_model_selects_original_negation_without_rewriting_it():
    plugin = ModelPlugin(json.dumps(GOOD))
    selected = await extract_candidates(
        plugin, "model", TEXT, "2026-11-02T00:00:00Z", "alice", 3
    )
    assert selected[0]["payload"]["value"] == QUOTE
    assert selected[0]["payload"]["claim_type"] == "inference"
    assert selected[0]["payload"]["evidence_quote"] == QUOTE
    request = json.loads(plugin.invocations[0][1][1].content)
    assert request == {
        "recorded_at": "2026-11-02T00:00:00Z",
        "user_text": TEXT,
        "limit": 3,
    }


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        "```json\n[]\n```",
        "{}",
        json.dumps(
            [{"candidate_type": "l2_episode", "evidence_quote": "I like coffee."}]
        ),
        json.dumps(
            [{"candidate_type": "l2_episode", "evidence_quote": "like coffee."}]
        ),
        json.dumps(
            [
                {
                    "candidate_type": "l2_episode",
                    "evidence_quote": QUOTE,
                    "event_at": "tomorrow",
                }
            ]
        ),
        json.dumps(
            [{"candidate_type": "l1_profile", "field": "name", "evidence_quote": QUOTE}]
        ),
        json.dumps(
            [{"candidate_type": "l1_profile", "field": [], "evidence_quote": QUOTE}]
        ),
        json.dumps([{"candidate_type": [], "evidence_quote": QUOTE}]),
        json.dumps([{"candidate_type": "l2_episode", "evidence_quote": QUOTE}] * 4),
    ],
)
async def test_model_output_schema_and_full_evidence_are_validated(response):
    with pytest.raises(ValueError):
        await extract_candidates(
            ModelPlugin(response), "model", TEXT, "2026-11-02T00:00:00Z", "alice", 3
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("text", ["", "x" * 8001])
async def test_missing_or_unbounded_input_does_not_call_the_model(text):
    plugin = ModelPlugin("[]")
    assert (
        await extract_candidates(
            plugin, "model", text, "2026-11-02T00:00:00Z", "alice", 3
        )
        == []
    )
    assert plugin.invocations == []


async def run_injector(monkeypatch, response, text=TEXT):
    class API:
        async def get_bot_uuid(self):
            return "bot"

        async def get_query_vars(self):
            return {"user_message_text": text}

    monkeypatch.setattr(
        "components.event_listener.memory_injector.QueryBasedAPIProxy",
        lambda **_: API(),
    )
    plugin = ModelPlugin(response)
    await plugin.memory_store.save_kb_config(
        "kb",
        {
            "candidate_extraction_enabled": True,
            "candidate_auto_apply": True,
            "candidate_model_uuid": "model",
            "embedding_model_uuid": "emb",
        },
    )
    injector = MemoryInjector()
    injector.plugin = plugin
    await injector._extract_memory_candidates(
        SimpleNamespace(
            query_id=7,
            event=SimpleNamespace(
                session=Session(
                    launcher_type=LauncherTypes.PERSON,
                    launcher_id="user",
                    sender_id="alice",
                    bot_uuid="bot",
                ),
                sender_id="alice",
                response_text="Assistant assertion that must never become input",
            ),
        )
    )
    return plugin


@pytest.mark.asyncio
async def test_model_selected_candidate_is_pending_even_when_auto_apply_is_enabled(
    monkeypatch,
):
    plugin = await run_injector(monkeypatch, json.dumps(GOOD))
    entries, _ = await plugin.memory_store.list_memory_candidates("bot:person_user")
    assert len(entries) == 1
    assert entries[0]["status"] == "pending"
    assert entries[0]["payload"]["value"] == QUOTE
    assert entries[0]["payload"]["claim_type"] == "inference"
    assert entries[0]["payload"]["source_ref"] == "query:7"
    assert plugin.records == {}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "response",
    [
        RuntimeError("model unavailable"),
        "not json",
        json.dumps(
            GOOD
            + [{"candidate_type": "l2_episode", "evidence_quote": "A fabricated fact"}]
        ),
    ],
)
async def test_model_failure_or_invalid_later_entry_never_writes_partial_candidates(
    monkeypatch, response
):
    plugin = await run_injector(monkeypatch, response)
    entries, _ = await plugin.memory_store.list_memory_candidates("bot:person_user")
    assert entries == []
    assert plugin.records == {}


@pytest.mark.asyncio
async def test_sensitive_user_text_is_not_sent_to_candidate_model(monkeypatch):
    plugin = await run_injector(monkeypatch, "[]", text="my password=do-not-store-this")
    assert plugin.invocations == []
    entries, _ = await plugin.memory_store.list_memory_candidates(
        "bot:person_user", include_statuses=["accepted", "pending"]
    )
    assert all("do-not-store-this" not in json.dumps(item) for item in entries)


@pytest.mark.asyncio
@pytest.mark.parametrize("quote", ["We do not support v1.", "5."])
async def test_model_cannot_select_a_span_cut_inside_a_version_number(quote):
    text = "We do not support v1.5. Use v2.0."
    plugin = ModelPlugin(
        json.dumps([{"candidate_type": "l2_episode", "evidence_quote": quote}])
    )
    with pytest.raises(ValueError, match="original span"):
        await extract_candidates(
            plugin, "model", text, "2026-11-02T00:00:00Z", "alice", 3
        )


@pytest.mark.asyncio
async def test_full_version_statement_keeps_its_negation_and_decimal():
    text = "We do not support v1.5. Use v2.0."
    quote = "We do not support v1.5."
    plugin = ModelPlugin(
        json.dumps([{"candidate_type": "l2_episode", "evidence_quote": quote}])
    )
    result = await extract_candidates(
        plugin, "model", text, "2026-11-02T00:00:00Z", "alice", 3
    )
    assert result[0]["payload"]["content"] == quote
