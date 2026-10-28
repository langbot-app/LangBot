from __future__ import annotations

import json

import pytest

from components.commands.memory import Memory
from langbot_plugin.api.entities.builtin.command.context import ExecuteContext
from langbot_plugin.api.entities.builtin.provider.session import Session, LauncherTypes
from store.memory_store import MemoryStore


class FakeAPI:
    async def get_bot_uuid(self) -> str:
        return "bot-1"

    async def get_query_vars(self) -> dict:
        return {"sender_id": "u-1", "sender_name": "Alice"}

    async def list_pipeline_knowledge_bases(self) -> list[dict]:
        return [{"uuid": "kb-1"}]


class FakePlugin:
    def __init__(self):
        self.storage: dict[str, bytes] = {}
        self.memory_store = MemoryStore(self)
        self.plugin_runtime_handler = object()

    async def get_plugin_storage_keys(self) -> list[str]:
        return list(self.storage)

    async def get_plugin_storage(self, key: str) -> bytes:
        if key not in self.storage:
            raise KeyError(key)
        return self.storage[key]

    async def set_plugin_storage(self, key: str, data: bytes) -> None:
        self.storage[key] = data


def _context(params: list[str]) -> ExecuteContext:
    return ExecuteContext(
        query_id=1,
        session=Session(launcher_type=LauncherTypes.GROUP, launcher_id="1"),
        command_text="memory audit",
        full_command_text="!memory audit",
        command="memory",
        crt_command="audit",
        params=["audit", *params],
        crt_params=params,
        privilege=0,
    )


async def _run_audit(command: Memory, params: list[str]) -> str:
    subcommand = command.registered_subcommands["audit"].subcommand
    results = []
    async for item in subcommand(command, _context(params)):
        results.append(item.text or "")
    return "\n".join(results)


@pytest.mark.asyncio
async def test_memory_audit_lists_current_scope(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    plugin.storage["kb_configs"] = json.dumps(
        {"kb-1": {"embedding_model_uuid": "emb-1", "isolation": "session"}}
    ).encode("utf-8")
    plugin.storage["audit:bot-1:group_1"] = json.dumps(
        [
            {
                "audit_id": "a1",
                "operation": "remember",
                "scope_key": "bot-1:group_1",
                "user_key": "bot-1:group_1",
                "target_type": "episode",
                "target_id": "ep-1",
                "summary": "remembered thing",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ]
    ).encode("utf-8")
    plugin.storage["audit:other"] = json.dumps(
        [{"operation": "remember", "target_id": "leaked", "summary": "other"}]
    ).encode("utf-8")
    command.plugin = plugin

    output = await _run_audit(command, [])

    assert "remember ep-1" in output
    assert "remembered thing" in output
    assert "leaked" not in output


@pytest.mark.asyncio
async def test_memory_audit_export_is_current_scope_only(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    plugin.storage["kb_configs"] = json.dumps(
        {"kb-1": {"embedding_model_uuid": "emb-1", "isolation": "session"}}
    ).encode("utf-8")
    plugin.storage["audit:bot-1:group_1"] = json.dumps(
        [
            {
                "audit_id": "a1",
                "operation": "remember",
                "scope_key": "bot-1:group_1",
                "user_key": "bot-1:group_1",
                "target_type": "episode",
                "target_id": "ep-1",
                "summary": "remembered thing",
                "timestamp": "2026-01-01T00:00:00Z",
            }
        ]
    ).encode("utf-8")
    plugin.storage["audit:other"] = json.dumps(
        [{"operation": "remember", "target_id": "leaked", "summary": "other"}]
    ).encode("utf-8")
    command.plugin = plugin

    output = await _run_audit(command, ["export"])
    data = json.loads(output)

    assert data["scope_key"] == "bot-1:group_1"
    assert len(data["entries"]) == 1
    assert data["entries"][0]["target_id"] == "ep-1"
    assert "leaked" not in output
