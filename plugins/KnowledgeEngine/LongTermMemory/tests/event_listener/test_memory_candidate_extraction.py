from __future__ import annotations

import json

import pytest

from components.event_listener.memory_injector import MemoryInjector
from langbot_plugin.api.entities import context, events
from langbot_plugin.api.entities.builtin.provider.session import LauncherTypes, Session
from store.memory_store import MemoryStore


class FakeAPI:
    query_vars: dict = {}

    async def get_bot_uuid(self) -> str:
        return "bot-1"

    async def get_query_vars(self) -> dict:
        return self.query_vars

    async def list_pipeline_knowledge_bases(self) -> list[dict]:
        return [{"uuid": "kb-1"}]


class FakePlugin:
    def __init__(self, config: dict):
        self.storage = {
            "kb_configs": json.dumps({"kb-1": config}).encode("utf-8"),
        }
        self.memory_store = MemoryStore(self)
        self.plugin_runtime_handler = object()
        self.upserts = []

    async def get_plugin_storage_keys(self) -> list[str]:
        return list(self.storage)

    async def get_plugin_storage(self, key: str) -> bytes:
        if key not in self.storage:
            raise KeyError(key)
        return self.storage[key]

    async def set_plugin_storage(self, key: str, value: bytes) -> None:
        self.storage[key] = value

    async def invoke_embedding(self, _embedding_model_uuid: str, texts: list[str]):
        return [[float(index + 1)] for index, _ in enumerate(texts)]

    async def vector_upsert(self, **kwargs):
        self.upserts.append(kwargs)


def _event_context() -> context.EventContext:
    event = events.NormalMessageResponded(
        launcher_type="group",
        launcher_id="1",
        sender_id="u-1",
        session=Session(launcher_type=LauncherTypes.GROUP, launcher_id="1"),
        prefix="",
        response_text="ok",
        finish_reason="stop",
        funcs_called=[],
    )
    return context.EventContext(
        query_id=1,
        event_name="NormalMessageResponded",
        event=event,
    )


@pytest.mark.asyncio
async def test_candidate_extraction_disabled_by_default(monkeypatch):
    FakeAPI.query_vars = {
        "user_message_text": "Alice has a meeting tomorrow",
        "sender_name": "Alice",
    }
    monkeypatch.setattr(
        "components.event_listener.memory_injector.QueryBasedAPIProxy",
        lambda **_: FakeAPI(),
    )
    plugin = FakePlugin({
        "embedding_model_uuid": "emb-1",
        "isolation": "session",
        "candidate_extraction_enabled": False,
    })
    injector = MemoryInjector()
    injector.plugin = plugin

    await injector._extract_memory_candidates(_event_context())

    assert not any(key.startswith("candidates:") for key in plugin.storage)
    assert plugin.upserts == []


@pytest.mark.asyncio
async def test_candidate_extraction_creates_pending_candidate_without_auto_apply(monkeypatch):
    FakeAPI.query_vars = {
        "user_message_text": "Alice has a meeting tomorrow",
        "sender_name": "Alice",
    }
    monkeypatch.setattr(
        "components.event_listener.memory_injector.QueryBasedAPIProxy",
        lambda **_: FakeAPI(),
    )
    plugin = FakePlugin({
        "embedding_model_uuid": "emb-1",
        "isolation": "session",
        "candidate_extraction_enabled": True,
        "candidate_auto_apply": False,
        "candidate_max_per_turn": 3,
    })
    injector = MemoryInjector()
    injector.plugin = plugin

    await injector._extract_memory_candidates(_event_context())

    candidates = json.loads(plugin.storage["candidates:bot-1:group_1"].decode("utf-8"))
    assert len(candidates) == 1
    assert candidates[0]["status"] == "pending"
    assert candidates[0]["candidate_type"] == "l2_episode"
    assert "Alice has a meeting tomorrow" in candidates[0]["payload"]["content"]
    assert plugin.upserts == []


@pytest.mark.asyncio
async def test_candidate_extraction_redacts_sensitive_ignore_candidate(monkeypatch):
    FakeAPI.query_vars = {
        "user_message_text": "password: hunter2 token=abc123",
        "sender_name": "Alice",
    }
    monkeypatch.setattr(
        "components.event_listener.memory_injector.QueryBasedAPIProxy",
        lambda **_: FakeAPI(),
    )
    plugin = FakePlugin({
        "embedding_model_uuid": "emb-1",
        "isolation": "session",
        "candidate_extraction_enabled": True,
        "candidate_auto_apply": False,
        "candidate_max_per_turn": 3,
    })
    injector = MemoryInjector()
    injector.plugin = plugin

    await injector._extract_memory_candidates(_event_context())

    candidates = json.loads(plugin.storage["candidates:bot-1:group_1"].decode("utf-8"))
    assert len(candidates) == 1
    assert candidates[0]["candidate_type"] == "ignore"
    assert candidates[0]["payload"]["redacted"] is True
    serialized = json.dumps(candidates, ensure_ascii=False)
    assert "hunter2" not in serialized
    assert "abc123" not in serialized
