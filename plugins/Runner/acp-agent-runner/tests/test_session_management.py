from __future__ import annotations

import types
from unittest.mock import AsyncMock

import pytest
from components.commands.session_commands import NewSession, StopRun, SwitchSession
from components.runner.default import DefaultRunner
from daemon import RunnerDaemon
from pkg.session_management import (
    conversation_id_from_command,
    delete_value,
    normalize_sessions,
    resolve_session_target,
    run_daemon_control,
    runner_session_identity,
    storage_key,
)


def test_normalize_sessions_sorts_and_filters_invalid_items():
    result = {
        "sessions": [
            {
                "sessionId": "ses_old",
                "title": "Old",
                "cwd": "/workspace",
                "updatedAt": "2026-01-01T00:00:00Z",
            },
            {"title": "Missing id"},
            {
                "sessionId": "ses_new",
                "title": "New",
                "cwd": "/workspace",
                "updatedAt": "2026-01-02T00:00:00Z",
            },
        ]
    }

    sessions = normalize_sessions(result)

    assert [item["session_id"] for item in sessions] == ["ses_new", "ses_old"]


def test_resolve_session_target_accepts_index_or_exact_id():
    sessions = [
        {"session_id": "ses_one", "title": "One", "cwd": "", "updated_at": ""},
        {"session_id": "ses_two", "title": "Two", "cwd": "", "updated_at": ""},
    ]

    assert resolve_session_target("2", sessions) == "ses_two"
    assert resolve_session_target("ses_one", sessions) == "ses_one"
    assert resolve_session_target("3", sessions) is None
    assert resolve_session_target("ses_missing", sessions) is None


def test_storage_key_does_not_expose_conversation_id():
    key = storage_key("current", "person_sensitive-platform-id")

    assert key.startswith("acp-session:v1:current:")
    assert "sensitive-platform-id" not in key


def test_runner_and_command_share_reset_stable_session_identity():
    session = types.SimpleNamespace(
        launcher_type=types.SimpleNamespace(value="person"),
        launcher_id="user-1",
    )
    command_context = types.SimpleNamespace(session=session)
    runner_context = types.SimpleNamespace(
        conversation=types.SimpleNamespace(
            conversation_id="conversation-uuid-123",
            session_id="person_user-1",
        )
    )

    assert conversation_id_from_command(command_context) == "person_user-1"
    assert runner_session_identity(runner_context) == "person_user-1"
    assert DefaultRunner()._conversation_id(runner_context) == "person_user-1"


@pytest.mark.asyncio
async def test_delete_value_only_ignores_explicit_missing_key_errors():
    missing_plugin = types.SimpleNamespace(get_plugin_storage=AsyncMock(side_effect=FileNotFoundError()))
    await delete_value(missing_plugin, "missing")

    failing_plugin = types.SimpleNamespace(get_plugin_storage=AsyncMock(side_effect=RuntimeError("storage offline")))
    with pytest.raises(RuntimeError, match="storage offline"):
        await delete_value(failing_plugin, "current")


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("control", "error"),
    [
        ({"location": "local"}, "location=daemon"),
        ({"location": "remote-ssh"}, "location=daemon"),
        ({"location": "daemon", "requires_env_json": True}, "env-json securely"),
        (
            {"location": "daemon", "session_capabilities": {"session/list": False}},
            "does not support session.list",
        ),
    ],
)
async def test_daemon_control_rejects_unsupported_configuration_without_waiting(control, error):
    plugin = types.SimpleNamespace(get_config=lambda: {})

    with pytest.raises(RuntimeError, match=error):
        await run_daemon_control(plugin, control, "session.list")


class FakeCommandPlugin:
    def __init__(self):
        self.values = {}
        self.deleted = []

    def get_config(self):
        return {"language": "en_US"}

    async def get_plugin_storage(self, key):
        return self.values.get(key, b"")

    async def delete_plugin_storage(self, key):
        self.deleted.append(key)

    async def set_plugin_storage(self, key, value):
        self.values[key] = value


async def _command_results(command, context):
    await command.initialize()
    subcommand = command.registered_subcommands[""].subcommand
    return [item async for item in subcommand(command, context)]


@pytest.mark.asyncio
async def test_group_session_changes_require_admin_privilege():
    plugin = FakeCommandPlugin()
    command = NewSession()
    command.plugin = plugin
    context = types.SimpleNamespace(
        session=types.SimpleNamespace(launcher_type=types.SimpleNamespace(value="group"), launcher_id="group-1"),
        privilege=1,
        create_new_conversation=AsyncMock(),
    )

    results = await _command_results(command, context)

    assert "Only bot administrators" in results[0].text
    assert plugin.deleted == []
    context.create_new_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_group_admin_can_create_new_session():
    plugin = FakeCommandPlugin()
    for kind in ("selected", "last", "list"):
        plugin.values[storage_key(kind, "group_group-1")] = b"{}"
    command = NewSession()
    command.plugin = plugin
    context = types.SimpleNamespace(
        session=types.SimpleNamespace(launcher_type=types.SimpleNamespace(value="group"), launcher_id="group-1"),
        privilege=2,
        create_new_conversation=AsyncMock(),
    )

    results = await _command_results(command, context)

    assert "next normal message" in results[0].text
    assert len(plugin.deleted) == 3
    context.create_new_conversation.assert_awaited_once()


@pytest.mark.asyncio
async def test_storage_failure_blocks_new_session_reset():
    plugin = FakeCommandPlugin()
    plugin.get_plugin_storage = AsyncMock(side_effect=RuntimeError("storage offline"))
    command = NewSession()
    command.plugin = plugin
    context = types.SimpleNamespace(
        session=types.SimpleNamespace(launcher_type=types.SimpleNamespace(value="person"), launcher_id="user-1"),
        privilege=1,
        create_new_conversation=AsyncMock(),
    )

    results = await _command_results(command, context)

    assert "storage offline" in results[0].text
    context.create_new_conversation.assert_not_awaited()


@pytest.mark.asyncio
async def test_switch_reset_failure_restores_previous_selection(monkeypatch):
    plugin = FakeCommandPlugin()
    conversation_id = "person_user-1"
    selected_key = storage_key("selected", conversation_id)
    plugin.values[selected_key] = b'{"session_id":"ses_previous"}'
    control_key = storage_key("control", conversation_id)
    plugin.values[control_key] = b'{"location":"daemon","daemon_id":"daemon-1"}'
    monkeypatch.setattr(
        "components.commands.session_commands.run_daemon_control",
        AsyncMock(
            return_value={"sessions": [{"sessionId": "ses_next", "title": "Next", "updatedAt": "2026-01-02T00:00:00Z"}]}
        ),
    )
    command = SwitchSession()
    command.plugin = plugin
    await command.initialize()
    context = types.SimpleNamespace(
        session=types.SimpleNamespace(launcher_type=types.SimpleNamespace(value="person"), launcher_id="user-1"),
        privilege=1,
        crt_params=["1"],
        create_new_conversation=AsyncMock(side_effect=RuntimeError("reset failed")),
    )
    subcommand = command.registered_subcommands["*"].subcommand

    results = [item async for item in subcommand(command, context)]

    assert "reset failed" in results[0].text
    assert plugin.values[selected_key] == b'{"session_id":"ses_previous"}'


@pytest.mark.asyncio
async def test_switch_survives_host_conversation_reset(monkeypatch):
    plugin = FakeCommandPlugin()
    runner = DefaultRunner()
    runner.plugin = plugin
    first_runner_context = types.SimpleNamespace(
        conversation=types.SimpleNamespace(
            conversation_id="conversation-before-reset",
            session_id="person_user-1",
        )
    )
    config = {
        "provider": "opencode",
        "location": "daemon",
        "acp_command": "opencode acp",
        "workspace": "/workspace",
        "session_cwd": "/workspace",
        "daemon_id": "daemon-1",
        "timeout": 60,
        "startup_timeout": 30,
        "initialize_timeout": 30,
        "permission_decision": "allow_once",
        "env": {},
    }
    assert await runner._managed_session_id(first_runner_context, config) == ""

    monkeypatch.setattr(
        "components.commands.session_commands.run_daemon_control",
        AsyncMock(
            return_value={
                "sessions": [
                    {
                        "sessionId": "ses_selected",
                        "title": "Selected",
                        "updatedAt": "2026-01-02T00:00:00Z",
                    }
                ]
            }
        ),
    )
    command = SwitchSession()
    command.plugin = plugin
    await command.initialize()
    context = types.SimpleNamespace(
        session=types.SimpleNamespace(launcher_type=types.SimpleNamespace(value="person"), launcher_id="user-1"),
        privilege=1,
        crt_params=["1"],
        create_new_conversation=AsyncMock(),
    )
    subcommand = command.registered_subcommands["*"].subcommand
    results = [item async for item in subcommand(command, context)]

    assert "ses_selected" in results[0].text
    context.create_new_conversation.assert_awaited_once()
    next_runner_context = types.SimpleNamespace(
        conversation=types.SimpleNamespace(
            conversation_id="conversation-after-reset",
            session_id="person_user-1",
        )
    )
    assert await runner._managed_session_id(next_runner_context, config) == "ses_selected"


@pytest.mark.asyncio
async def test_stop_reports_group_ownership_denial():
    plugin = FakeCommandPlugin()
    command = StopRun()
    command.plugin = plugin
    context = types.SimpleNamespace(get_query_vars=AsyncMock(return_value={"_stop_command_denied": True}))

    results = await _command_results(command, context)

    assert "belongs to another group member" in results[0].text


@pytest.mark.asyncio
async def test_daemon_control_operation_uses_supplied_environment(monkeypatch):
    seen = {}

    class FakeClient:
        def __init__(self, **kwargs):
            seen.update(kwargs)

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def initialize(self, timeout):
            return {"agentCapabilities": {"methods": ["session/list"]}}

        async def request(self, method, params, timeout):
            return {"sessions": []}

    monkeypatch.setattr("daemon.AcpStdioClient", FakeClient)
    daemon = RunnerDaemon(url="ws://example.test", daemon_id="daemon-1")
    daemon.emit_event = AsyncMock()

    await daemon._run_control_operation(
        "job-1",
        "session.list",
        {
            "config": {
                "acp_command": "opencode acp",
                "workspace": "/workspace",
                "env": {"ACP_PROFILE": "team"},
            },
            "arguments": {},
        },
    )

    assert seen["env"] == {"ACP_PROFILE": "team"}


@pytest.mark.asyncio
async def test_prompt_only_acp_client_rejects_session_management(monkeypatch):
    class PromptOnlyClient:
        def __init__(self, **_kwargs):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *_args):
            return None

        async def initialize(self, timeout):
            return {"agentCapabilities": {"methods": ["session/new", "session/prompt"]}}

    monkeypatch.setattr("daemon.AcpStdioClient", PromptOnlyClient)
    daemon = RunnerDaemon(url="ws://example.test", daemon_id="daemon-1")
    daemon.emit_event = AsyncMock()

    with pytest.raises(Exception, match="does not support session/list"):
        await daemon._run_control_operation(
            "job-1",
            "session.list",
            {"config": {"acp_command": "prompt-only-acp"}, "arguments": {}},
        )
