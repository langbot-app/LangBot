"""Unit tests for ActionRPCBoxClient.

These tests do NOT require a real socket/transport – they mock the underlying
Handler (which owns the connection) so we can verify request construction, the
action sent for each public method, response deserialization into models, the
error-prefix translation logic, and timeout/failure handling.
"""

from __future__ import annotations

import datetime as dt
import logging
from unittest import mock

import pytest

from langbot_plugin.box.actions import LangBotToBoxAction
from langbot_plugin.box.client import (
    ActionRPCBoxClient,
    _translate_action_error,
)
from langbot_plugin.box.errors import (
    BoxAdmissionError,
    BoxBackendUnavailableError,
    BoxError,
    BoxManagedProcessConflictError,
    BoxManagedProcessNotFoundError,
    BoxRuntimeUnavailableError,
    BoxReadinessError,
    BoxSessionConflictError,
    BoxSessionNotFoundError,
    BoxValidationError,
)
from langbot_plugin.box.models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxManagedProcessInfo,
    BoxManagedProcessSpec,
    BoxManagedProcessStatus,
    BoxNetworkMode,
    BoxSpec,
    SandboxAdmissionGrant,
    SandboxAdmissionRevocation,
)
from langbot_plugin.box.tenancy import namespace_session_id
from langbot_plugin.entities.io.context import ActionContext


@pytest.fixture
def logger():
    return logging.getLogger("test.box.client")


@pytest.fixture
def handler():
    """A mocked Handler whose async call_action / send_file we control per-test."""
    h = mock.MagicMock()
    h.call_action = mock.AsyncMock()
    h.send_file = mock.AsyncMock(return_value="file-key-abc")
    return h


@pytest.fixture
def client(logger, handler):
    c = ActionRPCBoxClient(logger=logger)
    c.set_handler(handler)
    return c


def _managed_process_payload(**overrides) -> dict:
    payload = {
        "session_id": "sess-1",
        "process_id": "default",
        "status": "running",
        "command": "python",
        "args": ["app.py"],
        "cwd": "/workspace",
        "env_keys": ["FOO"],
        "attached": False,
        "started_at": "2024-01-01T00:00:00+00:00",
    }
    payload.update(overrides)
    return payload


# ── handler property / set_handler ────────────────────────────────────


def test_handler_property_raises_when_unset(logger):
    c = ActionRPCBoxClient(logger=logger)
    with pytest.raises(BoxRuntimeUnavailableError):
        _ = c.handler


def test_set_handler_makes_property_accessible(logger, handler):
    c = ActionRPCBoxClient(logger=logger)
    c.set_handler(handler)
    assert c.handler is handler


# ── _translate_action_error ───────────────────────────────────────────


@pytest.mark.parametrize(
    ("prefix", "expected"),
    [
        ("BoxValidationError:", BoxValidationError),
        ("BoxSessionNotFoundError:", BoxSessionNotFoundError),
        ("BoxSessionConflictError:", BoxSessionConflictError),
        ("BoxManagedProcessNotFoundError:", BoxManagedProcessNotFoundError),
        ("BoxManagedProcessConflictError:", BoxManagedProcessConflictError),
        ("BoxBackendUnavailableError:", BoxBackendUnavailableError),
        ("BoxAdmissionError:", BoxAdmissionError),
        ("BoxReadinessError:", BoxReadinessError),
    ],
)
def test_translate_action_error_maps_known_prefixes(prefix, expected):
    err = _translate_action_error(Exception(f"{prefix} something went wrong"))
    assert type(err) is expected
    assert "something went wrong" in str(err)


def test_translate_action_error_falls_back_to_base():
    err = _translate_action_error(Exception("totally unknown failure"))
    assert type(err) is BoxError
    assert "totally unknown failure" in str(err)


def test_translate_action_error_matches_prefix_anywhere_in_message():
    # The implementation uses substring containment, not str.startswith.
    err = _translate_action_error(
        Exception("ActionCallError: BoxSessionNotFoundError: no such session")
    )
    assert type(err) is BoxSessionNotFoundError


# ── _call error handling ──────────────────────────────────────────────


@pytest.mark.anyio
async def test_call_unavailable_propagates_when_no_handler(logger):
    c = ActionRPCBoxClient(logger=logger)
    # No handler set → handler property raises BoxRuntimeUnavailableError,
    # which _call must re-raise untouched (not translate it).
    with pytest.raises(BoxRuntimeUnavailableError):
        await c.get_status()


@pytest.mark.anyio
async def test_call_translates_arbitrary_exception(client, handler):
    handler.call_action.side_effect = RuntimeError("BoxValidationError: bad spec")
    with pytest.raises(BoxValidationError) as exc_info:
        await client.get_status()
    assert "bad spec" in str(exc_info.value)


@pytest.mark.anyio
async def test_call_translates_unknown_to_base_box_error(client, handler):
    handler.call_action.side_effect = RuntimeError("connection reset")
    with pytest.raises(BoxError) as exc_info:
        await client.get_status()
    assert type(exc_info.value) is BoxError


@pytest.mark.anyio
async def test_call_passes_action_data_and_default_timeout(client, handler):
    handler.call_action.return_value = {"ok": True}
    await client.get_status()
    handler.call_action.assert_awaited_once()
    args, kwargs = handler.call_action.call_args
    assert args[0] is LangBotToBoxAction.STATUS
    assert args[1] == {}
    assert kwargs["timeout"] == 15.0
    assert kwargs["cancel_peer_on_cancel"] is False


# ── initialize ────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_initialize_sends_health(client, handler):
    handler.call_action.return_value = {}
    await client.initialize()
    action = handler.call_action.call_args.args[0]
    assert action is LangBotToBoxAction.HEALTH


@pytest.mark.anyio
async def test_initialize_wraps_failure_in_unavailable(client, handler):
    handler.call_action.side_effect = RuntimeError("boom")
    with pytest.raises(BoxRuntimeUnavailableError) as exc_info:
        await client.initialize()
    assert "box runtime unavailable" in str(exc_info.value)


@pytest.mark.anyio
async def test_verify_shared_workspace_uses_host_control_action(client, handler):
    marker_name = ".langbot-box-volume-probe-" + "a" * 32
    handler.call_action.return_value = {
        "marker_name": marker_name,
        "sha256": "b" * 64,
        "size": 64,
    }

    result = await client.verify_shared_workspace(marker_name)

    assert result["sha256"] == "b" * 64
    args, kwargs = handler.call_action.call_args
    assert args == (
        LangBotToBoxAction.VERIFY_SHARED_WORKSPACE,
        {"marker_name": marker_name},
    )
    assert kwargs["action_context"] is None


@pytest.mark.anyio
async def test_upsert_sandbox_admission_grant_uses_host_control_action(client, handler):
    handler.call_action.return_value = {"installed": True}
    grant = SandboxAdmissionGrant(
        instance_uuid="instance-a",
        workspace_uuid="workspace-a",
        execution_generation=2,
        entitlement_revision=7,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=60),
        max_sessions=1,
        max_managed_processes=0,
    )

    result = await client.upsert_sandbox_admission_grant(grant)

    assert result == {"installed": True}
    args, kwargs = handler.call_action.call_args
    assert args[0] is LangBotToBoxAction.UPSERT_SANDBOX_ADMISSION_GRANT
    assert args[1] == grant.model_dump(mode="json")
    assert kwargs["action_context"] is None


@pytest.mark.anyio
async def test_revoke_sandbox_admission_grant_uses_monotonic_tombstone(client, handler):
    handler.call_action.return_value = {"revoked": True}
    revocation = SandboxAdmissionRevocation(
        instance_uuid="instance-a",
        workspace_uuid="workspace-a",
        entitlement_revision=8,
    )

    result = await client.revoke_sandbox_admission_grant(revocation)

    assert result == {"revoked": True}
    args, kwargs = handler.call_action.call_args
    assert args[0] is LangBotToBoxAction.REVOKE_SANDBOX_ADMISSION_GRANT
    assert args[1] == revocation.model_dump(mode="json")
    assert kwargs["timeout"] == 30.0
    assert kwargs["action_context"] is None


# ── execute ───────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_execute_sends_spec_and_parses_result(client, handler):
    handler.call_action.return_value = {
        "session_id": "sess-9",
        "backend_name": "nsjail",
        "status": "completed",
        "exit_code": 0,
        "stdout": "hi\n",
        "stderr": "",
        "duration_ms": 42,
    }
    spec = BoxSpec(session_id="sess-9", cmd="echo hi")

    result = await client.execute(spec)

    assert isinstance(result, BoxExecutionResult)
    assert result.session_id == "sess-9"
    assert result.backend_name == "nsjail"
    assert result.status is BoxExecutionStatus.COMPLETED
    assert result.exit_code == 0
    assert result.stdout == "hi\n"
    assert result.duration_ms == 42
    assert result.ok is True

    # Verify the EXEC action, json-serialized spec payload, and 300s timeout.
    args, kwargs = handler.call_action.call_args
    assert args[0] is LangBotToBoxAction.EXEC
    assert args[1] == spec.model_dump(mode="json")
    assert kwargs["timeout"] == 300.0
    assert kwargs["cancel_peer_on_cancel"] is True


@pytest.mark.anyio
async def test_execute_timed_out_result(client, handler):
    handler.call_action.return_value = {
        "session_id": "sess-t",
        "backend_name": "e2b",
        "status": "timed_out",
        "exit_code": None,
        "stderr": "timed out",
        "duration_ms": 30000,
    }
    spec = BoxSpec(session_id="sess-t", cmd="sleep 100")

    result = await client.execute(spec)

    assert result.status is BoxExecutionStatus.TIMED_OUT
    assert result.exit_code is None
    assert result.stdout == ""  # default applied when key absent
    assert result.ok is False


@pytest.mark.anyio
async def test_execute_propagates_translated_error(client, handler):
    handler.call_action.side_effect = RuntimeError(
        "BoxBackendUnavailableError: no backend"
    )
    spec = BoxSpec(session_id="sess-x", cmd="ls")
    with pytest.raises(BoxBackendUnavailableError):
        await client.execute(spec)


# ── shutdown ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_shutdown_sends_action_and_clears_handler(client, handler):
    handler.call_action.return_value = {}
    await client.shutdown()
    assert handler.call_action.call_args.args[0] is LangBotToBoxAction.SHUTDOWN
    # Handler is cleared; subsequent calls now report unavailable.
    with pytest.raises(BoxRuntimeUnavailableError):
        _ = client.handler


@pytest.mark.anyio
async def test_shutdown_swallows_errors(client, handler):
    handler.call_action.side_effect = RuntimeError("already dead")
    # Should not raise even though the underlying call fails.
    await client.shutdown()
    with pytest.raises(BoxRuntimeUnavailableError):
        _ = client.handler


@pytest.mark.anyio
async def test_shutdown_noop_without_handler(logger):
    c = ActionRPCBoxClient(logger=logger)
    # No handler set: shutdown must be a quiet no-op.
    await c.shutdown()


# ── get_status / get_backend_info ─────────────────────────────────────


@pytest.mark.anyio
async def test_get_status_returns_raw_dict(client, handler):
    handler.call_action.return_value = {"healthy": True, "sessions": 3}
    result = await client.get_status()
    assert result == {"healthy": True, "sessions": 3}
    assert handler.call_action.call_args.args[0] is LangBotToBoxAction.STATUS


@pytest.mark.anyio
async def test_get_backend_info_returns_raw_dict(client, handler):
    handler.call_action.return_value = {"name": "nsjail", "available": True}
    result = await client.get_backend_info()
    assert result == {"name": "nsjail", "available": True}
    assert handler.call_action.call_args.args[0] is LangBotToBoxAction.GET_BACKEND_INFO


# ── sessions ──────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_get_sessions_unwraps_list(client, handler):
    handler.call_action.return_value = {
        "sessions": [{"session_id": "a"}, {"session_id": "b"}]
    }
    sessions = await client.get_sessions()
    assert sessions == [{"session_id": "a"}, {"session_id": "b"}]
    assert handler.call_action.call_args.args[0] is LangBotToBoxAction.GET_SESSIONS


@pytest.mark.anyio
async def test_get_session_sends_session_id(client, handler):
    handler.call_action.return_value = {"session_id": "sess-5", "backend_name": "e2b"}
    result = await client.get_session("sess-5")
    assert result == {"session_id": "sess-5", "backend_name": "e2b"}
    args = handler.call_action.call_args.args
    assert args[0] is LangBotToBoxAction.GET_SESSION
    assert args[1] == {"session_id": "sess-5"}


@pytest.mark.anyio
async def test_create_session_sends_spec(client, handler):
    handler.call_action.return_value = {
        "session_id": "new-sess",
        "backend_name": "nsjail",
    }
    spec = BoxSpec(session_id="new-sess", cmd="", network=BoxNetworkMode.ON)
    result = await client.create_session(spec)
    assert result == {"session_id": "new-sess", "backend_name": "nsjail"}
    args = handler.call_action.call_args.args
    assert args[0] is LangBotToBoxAction.CREATE_SESSION
    assert args[1] == spec.model_dump(mode="json")


@pytest.mark.anyio
async def test_create_session_uses_backend_startup_timeout(client, handler):
    handler.call_action.return_value = {
        "session_id": "new-sess",
        "backend_name": "docker",
    }
    spec = BoxSpec(session_id="new-sess", cmd="", network=BoxNetworkMode.ON)

    await client.create_session(spec)

    assert handler.call_action.call_args.kwargs["timeout"] == 60.0


@pytest.mark.anyio
async def test_delete_session_sends_id_with_timeout(client, handler):
    handler.call_action.return_value = {}
    await client.delete_session("sess-del")
    args, kwargs = handler.call_action.call_args
    assert args[0] is LangBotToBoxAction.DELETE_SESSION
    assert args[1] == {"session_id": "sess-del"}
    assert kwargs["timeout"] == 30.0


@pytest.mark.anyio
async def test_delete_session_translates_not_found(client, handler):
    handler.call_action.side_effect = RuntimeError("BoxSessionNotFoundError: missing")
    with pytest.raises(BoxSessionNotFoundError):
        await client.delete_session("nope")


# ── managed processes ─────────────────────────────────────────────────


@pytest.mark.anyio
async def test_start_managed_process_parses_info(client, handler):
    handler.call_action.return_value = _managed_process_payload()
    spec = BoxManagedProcessSpec(command="python", args=["app.py"])

    info = await client.start_managed_process("sess-1", spec)

    assert isinstance(info, BoxManagedProcessInfo)
    assert info.session_id == "sess-1"
    assert info.process_id == "default"
    assert info.status is BoxManagedProcessStatus.RUNNING
    assert info.command == "python"
    assert info.args == ["app.py"]

    args = handler.call_action.call_args.args
    assert args[0] is LangBotToBoxAction.START_MANAGED_PROCESS
    assert args[1] == {
        "session_id": "sess-1",
        "spec": spec.model_dump(mode="json"),
    }


@pytest.mark.anyio
async def test_start_managed_process_conflict_error(client, handler):
    handler.call_action.side_effect = RuntimeError(
        "BoxManagedProcessConflictError: already running"
    )
    spec = BoxManagedProcessSpec(command="python")
    with pytest.raises(BoxManagedProcessConflictError):
        await client.start_managed_process("sess-1", spec)


@pytest.mark.anyio
async def test_get_managed_process_default_and_explicit_id(client, handler):
    handler.call_action.return_value = _managed_process_payload(
        process_id="worker",
        status="exited",
        exit_code=0,
        exited_at="2024-01-01T00:05:00+00:00",
    )

    info = await client.get_managed_process("sess-1", "worker")

    assert isinstance(info, BoxManagedProcessInfo)
    assert info.process_id == "worker"
    assert info.status is BoxManagedProcessStatus.EXITED
    assert info.exit_code == 0

    args = handler.call_action.call_args.args
    assert args[0] is LangBotToBoxAction.GET_MANAGED_PROCESS
    assert args[1] == {"session_id": "sess-1", "process_id": "worker"}


@pytest.mark.anyio
async def test_get_managed_process_uses_default_process_id(client, handler):
    handler.call_action.return_value = _managed_process_payload()
    await client.get_managed_process("sess-1")
    assert handler.call_action.call_args.args[1]["process_id"] == "default"


@pytest.mark.anyio
async def test_get_managed_process_not_found(client, handler):
    handler.call_action.side_effect = RuntimeError(
        "BoxManagedProcessNotFoundError: gone"
    )
    with pytest.raises(BoxManagedProcessNotFoundError):
        await client.get_managed_process("sess-1", "ghost")


@pytest.mark.anyio
async def test_stop_managed_process_sends_payload_with_timeout(client, handler):
    handler.call_action.return_value = {}
    await client.stop_managed_process("sess-1", "worker")
    args, kwargs = handler.call_action.call_args
    assert args[0] is LangBotToBoxAction.STOP_MANAGED_PROCESS
    assert args[1] == {"session_id": "sess-1", "process_id": "worker"}
    assert kwargs["timeout"] == 30.0


@pytest.mark.anyio
async def test_stop_managed_process_default_id(client, handler):
    handler.call_action.return_value = {}
    await client.stop_managed_process("sess-1")
    assert handler.call_action.call_args.args[1]["process_id"] == "default"


# ── websocket url builder ─────────────────────────────────────────────


def test_ws_url_from_https(client):
    url = client.get_managed_process_websocket_url(
        "sess-1", "https://relay.example.com"
    )
    assert url == (
        "wss://relay.example.com/v1/sessions/sess-1/managed-process/default/ws"
    )


def test_ws_url_from_http(client):
    url = client.get_managed_process_websocket_url(
        "sess-1", "http://relay.example.com", process_id="worker"
    )
    assert url == (
        "ws://relay.example.com/v1/sessions/sess-1/managed-process/worker/ws"
    )


def test_ws_url_from_bare_host(client):
    url = client.get_managed_process_websocket_url("sess-1", "relay:8080")
    assert url == ("ws://relay:8080/v1/sessions/sess-1/managed-process/default/ws")


def test_ws_url_uses_generation_scoped_physical_session(client):
    context = ActionContext(
        instance_uuid="instance-a",
        workspace_uuid="workspace-a",
        placement_generation=3,
    )

    url = client.get_managed_process_websocket_url(
        "sess-1",
        "https://relay.example.com",
        process_id="worker",
        action_context=context,
    )

    assert namespace_session_id(context, "sess-1") in url
    assert "instance-a" not in url
    assert "workspace-a" not in url


# ── init ──────────────────────────────────────────────────────────────


@pytest.mark.anyio
async def test_init_sends_config(client, handler):
    handler.call_action.return_value = {}
    await client.init({"backend": "nsjail", "foo": 1})
    args = handler.call_action.call_args.args
    assert args[0] is LangBotToBoxAction.INIT
    assert args[1] == {"backend": "nsjail", "foo": 1}
