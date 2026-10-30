from __future__ import annotations

import pytest

from components.commands.memory import Memory
from langbot_plugin.api.entities.builtin.command.context import ExecuteContext
from langbot_plugin.api.entities.builtin.provider.session import Session, LauncherTypes


class FakeAPI:
    async def get_bot_uuid(self) -> str:
        return "bot-1"

    async def get_query_vars(self) -> dict:
        return {}

    async def list_pipeline_knowledge_bases(self) -> list[dict]:
        return [{"uuid": "kb-1"}]


class FakeStore:
    EPISODE_STATUS_ACTIVE = "active"
    EPISODE_STATUS_SUPERSEDED = "superseded"
    EPISODE_STATUS_ARCHIVED = "archived"
    EPISODE_STATUS_DELETED = "deleted"
    EPISODE_STATUSES = {"active", "superseded", "archived", "deleted"}

    def __init__(self):
        self.last_statuses = None

    async def resolve_user_context(self, session, bot_uuid: str = ""):
        return (
            "bot-1:group_1",
            "bot-1:group_1",
            "kb-1",
            "session",
            {"embedding_model_uuid": "emb-1"},
        )

    async def list_episodes(
        self,
        collection_id,
        user_key,
        limit=10,
        offset=0,
        include_statuses=None,
    ):
        self.last_statuses = include_statuses
        episodes = [
            {
                "id": "active-1",
                "timestamp": "2026-01-01T00:00:00Z",
                "importance": 2,
                "tags": [],
                "content": "Active memory",
                "status": "active",
            }
        ]
        if include_statuses and "superseded" in include_statuses:
            episodes.append(
                {
                    "id": "superseded-1",
                    "timestamp": "2026-01-02T00:00:00Z",
                    "importance": 1,
                    "tags": [],
                    "content": "Old memory",
                    "status": "superseded",
                }
            )
        return episodes, len(episodes)

    @staticmethod
    def _preview_text(value: str, max_len: int = 120) -> str:
        return value[:max_len]


class FakePlugin:
    def __init__(self):
        self.memory_store = FakeStore()
        self.plugin_runtime_handler = object()


def _context(params: list[str]) -> ExecuteContext:
    return ExecuteContext(
        query_id=1,
        session=Session(launcher_type=LauncherTypes.GROUP, launcher_id="1"),
        command_text="memory list",
        full_command_text="!memory list",
        command="memory",
        crt_command="list",
        params=["list", *params],
        crt_params=params,
        privilege=0,
    )


async def _run_list(command: Memory, params: list[str]) -> str:
    subcommand = command.registered_subcommands["list"].subcommand
    results = []
    async for item in subcommand(command, _context(params)):
        results.append(item.text or "")
    return "\n".join(results)


@pytest.mark.asyncio
async def test_memory_list_defaults_to_active(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    output = await _run_list(command, [])

    assert plugin.memory_store.last_statuses == ["active"]
    assert "active-1" in output
    assert "superseded-1" not in output


@pytest.mark.asyncio
async def test_memory_list_can_include_superseded(monkeypatch):
    monkeypatch.setattr("components.commands.memory.QueryBasedAPIProxy", lambda **_: FakeAPI())
    command = Memory()
    plugin = FakePlugin()
    command.plugin = plugin

    output = await _run_list(command, ["--include-superseded"])

    assert plugin.memory_store.last_statuses == ["active", "superseded"]
    assert "active-1" in output
    assert "superseded-1" in output
    assert "(superseded, imp:1)" in output
