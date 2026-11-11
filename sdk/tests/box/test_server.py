"""Unit tests for langbot_plugin.box.server.

These tests exercise the box action RPC server WITHOUT a live aiohttp
server. ``BoxServerHandler`` is instantiated with a mock ``Connection`` and a
mock ``BoxRuntime``; the registered action handlers are then invoked directly
via ``handler.actions[...]`` and the resulting ``ActionResponse`` objects are
asserted. The pure helpers, the ``AiohttpWSConnection`` adapter and the
error/early-return paths of the aiohttp request handlers are also covered with
``unittest.mock``.
"""

from __future__ import annotations

import asyncio
import datetime as dt
from types import SimpleNamespace
from unittest import mock

import pytest
from aiohttp import WSCloseCode, web

from langbot_plugin.box import server
from langbot_plugin.box.actions import LangBotToBoxAction
from langbot_plugin.box.errors import (
    BoxAdmissionError,
    BoxManagedProcessConflictError,
    BoxManagedProcessNotFoundError,
    BoxSessionNotFoundError,
)
from langbot_plugin.box.models import (
    BoxExecutionResult,
    BoxExecutionStatus,
    BoxSpec,
    SandboxAdmissionGrant,
    SandboxAdmissionRevocation,
)
from langbot_plugin.box.server import (
    AiohttpWSConnection,
    BoxGenerationFence,
    BoxServerHandler,
    _error_response,
    _result_to_dict,
    create_app,
    create_ws_relay_app,
    handle_healthz,
    handle_managed_process_ws,
    handle_readyz,
    handle_rpc_ws,
)
from langbot_plugin.box.security import (
    BOX_CONTROL_TOKEN_HEADER,
    BOX_INSTANCE_HEADER,
    BOX_PLACEMENT_GENERATION_HEADER,
    BOX_WORKSPACE_HEADER,
)
from langbot_plugin.box.tenancy import (
    box_namespace,
    namespace_session_id,
    workspace_session_namespace_prefix,
)
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.entities.io.errors import ConnectionClosedError
from langbot_plugin.entities.io.resp import ActionResponse


_ACTION_CONTEXT = ActionContext(
    instance_uuid="instance-a",
    workspace_uuid="workspace-a",
    placement_generation=1,
)
_CONTROL_TOKEN = "box-control-token-that-is-longer-than-32-bytes"


def _new_handler(
    connection,
    runtime,
    *,
    authenticated: bool = True,
    allow_host_backend: bool = False,
    generation_fence: BoxGenerationFence | None = None,
):
    return BoxServerHandler(
        connection,
        runtime,
        host_control_authenticated=authenticated,
        trusted_instance_uuid=_ACTION_CONTEXT.instance_uuid,
        allow_host_backend=allow_host_backend,
        generation_fence=generation_fence,
    )


def _physical_session_id(session_id: str) -> str:
    return namespace_session_id(_ACTION_CONTEXT, session_id)


# ── Fixtures ─────────────────────────────────────────────────────────


@pytest.fixture
def mock_connection():
    """A mock Connection (send/receive/close are awaitables)."""
    conn = mock.MagicMock()
    conn.send = mock.AsyncMock()
    conn.receive = mock.AsyncMock()
    conn.close = mock.AsyncMock()
    return conn


@pytest.fixture
def mock_runtime():
    """A mock BoxRuntime with async/sync methods stubbed out.

    Async methods are AsyncMock and synchronous methods are plain MagicMock.
    Defaults return realistic shapes; individual tests override return values
    and side effects as needed.
    """
    runtime = mock.MagicMock()
    runtime.admission_required = False
    runtime.max_admission_records = 100
    runtime.max_rpc_file_bytes = 20 * 1024 * 1024
    runtime.blocking_executor = None
    runtime.event_loop_monitor = None
    runtime._sessions = {}
    runtime._managed_process_session_ids = set()
    runtime._creating_session_tasks = {}
    runtime._closing_session_tasks = {}
    runtime._background_tasks = set()

    runtime.get_backend_info = mock.AsyncMock(
        return_value={"name": "docker", "available": True}
    )
    runtime.get_status = mock.AsyncMock(
        return_value={
            "backend": {"name": "docker", "available": True},
            "active_sessions": 0,
            "managed_processes": 0,
            "session_ttl_sec": 300,
        }
    )
    runtime.get_capacity = mock.AsyncMock(
        return_value={"limit": 10, "used": 0, "remaining": 10}
    )
    runtime.execute = mock.AsyncMock()
    runtime.create_session = mock.AsyncMock(return_value={"session_id": "s1"})
    runtime.get_session = mock.MagicMock(return_value={"session_id": "s1"})
    runtime.get_sessions = mock.MagicMock(return_value=[{"session_id": "s1"}])
    runtime.get_sessions_for_workspace = mock.MagicMock(
        return_value=[{"session_id": "s1"}]
    )
    runtime.delete_session = mock.AsyncMock()
    runtime.start_managed_process = mock.AsyncMock(
        return_value={"process_id": "default", "status": "running"}
    )
    runtime.get_managed_process = mock.MagicMock(
        return_value={"process_id": "default", "status": "running"}
    )
    runtime.stop_managed_process = mock.AsyncMock()
    runtime.init = mock.MagicMock()
    runtime.verify_shared_workspace = mock.MagicMock(
        return_value={
            "marker_name": ".langbot-box-volume-probe-" + "a" * 32,
            "sha256": "b" * 64,
            "size": 64,
        }
    )
    runtime.shutdown = mock.AsyncMock()

    return runtime


@pytest.fixture
def handler(mock_connection, mock_runtime):
    handler = _new_handler(mock_connection, mock_runtime)
    handler.bind_action_context(_ACTION_CONTEXT)
    return handler


def _spec_data(**overrides) -> dict:
    """A valid BoxSpec payload."""
    data = {"session_id": "s1", "cmd": "echo hi"}
    data.update(overrides)
    return data


async def _invoke(handler: BoxServerHandler, action, data: dict) -> ActionResponse:
    """Invoke a registered action handler by its enum and return the response."""
    func = handler.actions[action.value]
    return await func(data)


# ── Pure helpers ─────────────────────────────────────────────────────


def test_result_to_dict_serializes_execution_result():
    result = BoxExecutionResult(
        session_id="s1",
        backend_name="docker",
        status=BoxExecutionStatus.COMPLETED,
        exit_code=0,
        stdout="out",
        stderr="",
        duration_ms=12,
    )
    as_dict = _result_to_dict(result)
    assert as_dict["session_id"] == "s1"
    assert as_dict["status"] == "completed"  # enum serialized to its value
    assert as_dict["exit_code"] == 0
    assert as_dict["duration_ms"] == 12


def test_box_protocol_has_no_skill_surface(handler):
    assert all("skill" not in action.value for action in LangBotToBoxAction)
    assert "skill_name" not in BoxSpec.model_fields
    assert "box_list_skills" not in handler.actions
    with pytest.raises(ValueError, match="skill_name"):
        BoxSpec.model_validate(
            {"session_id": "s1", "cmd": "true", "skill_name": "demo"}
        )


def test_error_response_shape_and_status():
    resp = _error_response(BoxSessionNotFoundError("nope"))
    assert isinstance(resp, web.Response)
    assert resp.status == 400
    body = resp.text
    assert "BoxSessionNotFoundError" in body
    assert "nope" in body


# ── AiohttpWSConnection adapter ──────────────────────────────────────


async def test_ws_connection_send_delegates_to_ws():
    ws = mock.MagicMock()
    ws.send_str = mock.AsyncMock()
    conn = AiohttpWSConnection(ws)
    await conn.send("hello")
    ws.send_str.assert_awaited_once_with("hello")


async def test_ws_connection_send_raises_connection_closed_on_reset():
    ws = mock.MagicMock()
    ws.send_str = mock.AsyncMock(side_effect=ConnectionResetError())
    conn = AiohttpWSConnection(ws)
    with pytest.raises(ConnectionClosedError):
        await conn.send("hello")


async def test_ws_connection_receive_returns_text():
    msg = SimpleNamespace(type=web.WSMsgType.TEXT, data="payload")
    ws = mock.MagicMock()
    ws.receive = mock.AsyncMock(return_value=msg)
    conn = AiohttpWSConnection(ws)
    assert await conn.receive() == "payload"


@pytest.mark.parametrize(
    "msg_type",
    [
        web.WSMsgType.CLOSE,
        web.WSMsgType.CLOSING,
        web.WSMsgType.CLOSED,
        web.WSMsgType.ERROR,
    ],
)
async def test_ws_connection_receive_raises_on_close_types(msg_type):
    msg = SimpleNamespace(type=msg_type, data=None)
    ws = mock.MagicMock()
    ws.receive = mock.AsyncMock(return_value=msg)
    conn = AiohttpWSConnection(ws)
    with pytest.raises(ConnectionClosedError, match="Connection closed"):
        await conn.receive()


async def test_ws_connection_receive_raises_on_unexpected_type():
    msg = SimpleNamespace(type=web.WSMsgType.BINARY, data=b"x")
    ws = mock.MagicMock()
    ws.receive = mock.AsyncMock(return_value=msg)
    conn = AiohttpWSConnection(ws)
    with pytest.raises(ConnectionClosedError, match="Unexpected message type"):
        await conn.receive()


async def test_ws_connection_close_delegates():
    ws = mock.MagicMock()
    ws.close = mock.AsyncMock()
    conn = AiohttpWSConnection(ws)
    await conn.close()
    ws.close.assert_awaited_once()


# ── Handler construction / registration ──────────────────────────────


def test_handler_registers_all_box_actions(handler):
    # Every box action is registered.
    for action in LangBotToBoxAction:
        assert action.value in handler.actions
    # Plus the common PING action registered by the box handler.
    assert CommonAction.PING.value in handler.actions
    # Plus FILE_CHUNK registered by the base Handler.
    assert CommonAction.FILE_CHUNK.value in handler.actions


def test_handler_keeps_runtime_reference(mock_connection, mock_runtime):
    h = _new_handler(mock_connection, mock_runtime)
    assert h._runtime is mock_runtime
    assert h.conn is mock_connection
    assert h.name == "BoxServerHandler"


async def test_tenant_action_fails_closed_without_workspace_context(
    mock_connection, mock_runtime
):
    handler = _new_handler(mock_connection, mock_runtime)

    with pytest.raises(ValueError, match="trusted Workspace context"):
        await _invoke(handler, LangBotToBoxAction.CREATE_SESSION, _spec_data())

    mock_runtime.create_session.assert_not_awaited()


async def test_same_logical_session_id_is_namespaced_per_workspace(
    mock_connection, mock_runtime
):
    second_context = ActionContext(
        instance_uuid="instance-a",
        workspace_uuid="workspace-b",
        placement_generation=1,
    )
    first_handler = _new_handler(mock_connection, mock_runtime)
    first_handler.bind_action_context(_ACTION_CONTEXT)
    second_handler = _new_handler(mock_connection, mock_runtime)
    second_handler.bind_action_context(second_context)

    await _invoke(
        first_handler,
        LangBotToBoxAction.CREATE_SESSION,
        _spec_data(session_id="shared"),
    )
    await _invoke(
        second_handler,
        LangBotToBoxAction.CREATE_SESSION,
        _spec_data(session_id="shared"),
    )

    first_spec = mock_runtime.create_session.await_args_list[0].args[0]
    second_spec = mock_runtime.create_session.await_args_list[1].args[0]
    assert first_spec.session_id == namespace_session_id(_ACTION_CONTEXT, "shared")
    assert second_spec.session_id == namespace_session_id(second_context, "shared")
    assert first_spec.session_id != second_spec.session_id


async def test_generation_advance_retires_old_sessions_and_rejects_rollback(
    mock_connection, mock_runtime
):
    generation_fence = BoxGenerationFence()
    second_context = _ACTION_CONTEXT.model_copy(update={"placement_generation": 2})
    first_handler = _new_handler(
        mock_connection,
        mock_runtime,
        generation_fence=generation_fence,
    )
    first_handler.bind_action_context(_ACTION_CONTEXT)
    second_handler = _new_handler(
        mock_connection,
        mock_runtime,
        generation_fence=generation_fence,
    )
    second_handler.bind_action_context(second_context)

    old_physical_id = namespace_session_id(_ACTION_CONTEXT, "shared")
    sessions = [{"session_id": old_physical_id}]
    mock_runtime.get_sessions_for_workspace.side_effect = lambda _context: list(
        sessions
    )

    async def delete_session(session_id):
        sessions[:] = [
            session for session in sessions if session["session_id"] != session_id
        ]

    mock_runtime.delete_session.side_effect = delete_session

    await _invoke(
        first_handler,
        LangBotToBoxAction.CREATE_SESSION,
        _spec_data(session_id="shared"),
    )
    await _invoke(
        second_handler,
        LangBotToBoxAction.CREATE_SESSION,
        _spec_data(session_id="shared"),
    )

    assert namespace_session_id(second_context, "shared") != old_physical_id
    mock_runtime.delete_session.assert_awaited_once_with(old_physical_id)
    with pytest.raises(PermissionError, match="Stale Box placement generation"):
        await _invoke(
            first_handler,
            LangBotToBoxAction.GET_SESSIONS,
            {},
        )
    # RPC-only Workspaces do not allocate relay Events. The Event is created
    # lazily only when a managed-process relay actually waits on the fence.
    assert generation_fence._stale_events == {}


def test_generation_fence_workspace_records_are_bounded():
    generation_fence = BoxGenerationFence(max_records=1)
    advanced = _ACTION_CONTEXT.model_copy(update={"placement_generation": 2})
    second_workspace = _ACTION_CONTEXT.model_copy(
        update={"workspace_uuid": "workspace-b"}
    )

    generation_fence.observe(_ACTION_CONTEXT)
    generation_fence.observe(advanced)

    with pytest.raises(PermissionError, match="fence capacity reached"):
        generation_fence.observe(second_workspace)


def test_generation_fence_advance_does_not_scan_other_workspaces():
    class NoGlobalItemsScan(dict):
        def items(self):
            raise AssertionError("generation advance scanned every Workspace")

    generation_fence = BoxGenerationFence(max_records=1_000)
    contexts = [
        ActionContext(
            instance_uuid="instance-a",
            workspace_uuid=f"workspace-{index}",
            placement_generation=1,
        )
        for index in range(1_000)
    ]
    for context in contexts:
        generation_fence.observe(context)

    previous_event = asyncio.Event()
    generation_fence._stale_events[("instance-a", "workspace-500", 1)] = previous_event
    generation_fence._stale_events = NoGlobalItemsScan(generation_fence._stale_events)
    generation_fence._active_tasks = NoGlobalItemsScan(generation_fence._active_tasks)

    generation_fence.observe(
        contexts[500].model_copy(update={"placement_generation": 2})
    )

    assert previous_event.is_set()
    assert ("instance-a", "workspace-500", 1) not in generation_fence._stale_events
    assert ("instance-a", "workspace-500", 2) not in generation_fence._stale_events


async def test_generation_advance_cancels_inflight_old_rpc_and_retires_late_session(
    mock_connection, mock_runtime
):
    generation_fence = BoxGenerationFence()
    second_context = _ACTION_CONTEXT.model_copy(update={"placement_generation": 2})
    first_handler = _new_handler(
        mock_connection,
        mock_runtime,
        generation_fence=generation_fence,
    )
    first_handler.bind_action_context(_ACTION_CONTEXT)
    second_handler = _new_handler(
        mock_connection,
        mock_runtime,
        generation_fence=generation_fence,
    )
    second_handler.bind_action_context(second_context)
    started = asyncio.Event()
    sessions: list[dict[str, str]] = []
    old_session_id = namespace_session_id(_ACTION_CONTEXT, "late")

    async def execute_old(_spec, **_kwargs):
        started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            sessions.append({"session_id": old_session_id})
            raise

    async def delete_session(session_id):
        for session in tuple(sessions):
            if session["session_id"] == session_id:
                sessions.remove(session)
                return
        raise BoxSessionNotFoundError(f"session {session_id} not found")

    mock_runtime.execute.side_effect = execute_old
    mock_runtime.get_sessions_for_workspace.side_effect = lambda _context: list(
        sessions
    )
    mock_runtime.delete_session.side_effect = delete_session

    old_task = asyncio.create_task(
        _invoke(
            first_handler,
            LangBotToBoxAction.EXEC,
            _spec_data(session_id="late"),
        )
    )
    await asyncio.wait_for(started.wait(), timeout=1)
    await _invoke(second_handler, LangBotToBoxAction.GET_SESSIONS, {})

    with pytest.raises(asyncio.CancelledError):
        await old_task
    assert sessions == []
    assert mock_runtime.delete_session.await_count >= 1


def test_skill_namespace_persists_across_generation_change():
    second_context = _ACTION_CONTEXT.model_copy(update={"placement_generation": 2})

    assert box_namespace(_ACTION_CONTEXT) == box_namespace(second_context)
    assert namespace_session_id(_ACTION_CONTEXT, "shared") != namespace_session_id(
        second_context, "shared"
    )


def test_authenticated_host_accepts_multiple_workspaces_on_one_instance(
    mock_connection, mock_runtime
):
    handler = _new_handler(mock_connection, mock_runtime)
    second_workspace = _ACTION_CONTEXT.model_copy(
        update={"workspace_uuid": "workspace-b", "placement_generation": 2}
    )

    assert (
        handler.validate_inbound_action_context(
            LangBotToBoxAction.EXEC.value, _ACTION_CONTEXT
        )
        == _ACTION_CONTEXT
    )
    assert (
        handler.validate_inbound_action_context(
            LangBotToBoxAction.EXEC.value, second_workspace
        )
        == second_workspace
    )


def test_tenant_action_rejects_forged_instance(mock_connection, mock_runtime):
    handler = _new_handler(mock_connection, mock_runtime)
    forged = _ACTION_CONTEXT.model_copy(update={"instance_uuid": "instance-b"})

    with pytest.raises(PermissionError, match="trusted instance"):
        handler.validate_inbound_action_context(LangBotToBoxAction.EXEC.value, forged)


def test_tenant_action_rejects_missing_inbound_context(mock_connection, mock_runtime):
    handler = _new_handler(mock_connection, mock_runtime)

    with pytest.raises(PermissionError, match="trusted Workspace context"):
        handler.validate_inbound_action_context(LangBotToBoxAction.EXEC.value, None)


async def test_unauthenticated_handler_rejects_init_and_exec(
    mock_connection, mock_runtime
):
    handler = _new_handler(mock_connection, mock_runtime, authenticated=False)
    handler.bind_action_context(_ACTION_CONTEXT)

    with pytest.raises(PermissionError, match="host control authentication"):
        await _invoke(handler, LangBotToBoxAction.INIT, {"backend": "local"})
    with pytest.raises(PermissionError, match="host control authentication"):
        await _invoke(handler, LangBotToBoxAction.EXEC, _spec_data())

    mock_runtime.init.assert_not_called()
    mock_runtime.execute.assert_not_awaited()


# ── PING / HEALTH / STATUS / GET_BACKEND_INFO ────────────────────────


async def test_verify_shared_workspace_is_authenticated_host_control(
    mock_connection, mock_runtime
):
    marker_name = ".langbot-box-volume-probe-" + "a" * 32
    authenticated = _new_handler(mock_connection, mock_runtime)

    response = await _invoke(
        authenticated,
        LangBotToBoxAction.VERIFY_SHARED_WORKSPACE,
        {"marker_name": marker_name},
    )

    assert response.code == 0
    assert response.data["sha256"] == "b" * 64
    mock_runtime.verify_shared_workspace.assert_called_once_with(marker_name)

    unauthenticated = _new_handler(mock_connection, mock_runtime, authenticated=False)
    with pytest.raises(PermissionError, match="authentication"):
        await _invoke(
            unauthenticated,
            LangBotToBoxAction.VERIFY_SHARED_WORKSPACE,
            {"marker_name": marker_name},
        )


async def test_ping(handler):
    resp = await _invoke(handler, CommonAction.PING, {})
    assert resp.code == 0
    assert resp.data == {}


async def test_health(handler, mock_runtime):
    resp = await _invoke(handler, LangBotToBoxAction.HEALTH, {})
    assert resp.code == 0
    assert resp.data == {"name": "docker", "available": True}
    mock_runtime.get_backend_info.assert_awaited_once()


async def test_status(handler, mock_runtime):
    resp = await _invoke(handler, LangBotToBoxAction.STATUS, {})
    assert resp.code == 0
    assert resp.data["active_sessions"] == 0
    mock_runtime.get_status.assert_awaited_once()


async def test_get_backend_info(handler, mock_runtime):
    resp = await _invoke(handler, LangBotToBoxAction.GET_BACKEND_INFO, {})
    assert resp.code == 0
    assert resp.data == {"name": "docker", "available": True}
    mock_runtime.get_backend_info.assert_awaited_once()


async def test_grant_enforced_health_fails_closed_when_isolation_not_ready(
    handler, mock_runtime
):
    mock_runtime.admission_required = True
    mock_runtime.get_readiness = mock.AsyncMock(
        return_value={"ready": False, "checks": {"cgroup_v2": False}}
    )

    resp = await _invoke(handler, LangBotToBoxAction.HEALTH, {})

    assert resp.code == 1
    assert "BoxReadinessError" in resp.message
    mock_runtime.get_backend_info.assert_not_awaited()


# ── EXEC ─────────────────────────────────────────────────────────────


async def test_exec_success(handler, mock_runtime):
    result = BoxExecutionResult(
        session_id=_physical_session_id("s1"),
        backend_name="docker",
        status=BoxExecutionStatus.COMPLETED,
        exit_code=0,
        stdout="hi\n",
        stderr="",
        duration_ms=5,
    )
    mock_runtime.execute.return_value = result

    resp = await _invoke(handler, LangBotToBoxAction.EXEC, _spec_data())

    assert resp.code == 0
    assert resp.data["stdout"] == "hi\n"
    assert resp.data["status"] == "completed"
    # runtime.execute was called with a validated BoxSpec.
    mock_runtime.execute.assert_awaited_once()
    (spec_arg,), _ = mock_runtime.execute.call_args
    assert spec_arg.session_id == _physical_session_id("s1")
    assert spec_arg.cmd == "echo hi"


async def test_exec_invalid_spec_returns_validation_error(handler, mock_runtime):
    # Missing required session_id triggers a pydantic ValidationError.
    resp = await _invoke(handler, LangBotToBoxAction.EXEC, {"cmd": "echo hi"})
    assert resp.code == 1
    assert "BoxValidationError" in resp.message
    mock_runtime.execute.assert_not_awaited()


async def test_grant_enforced_exec_passes_trusted_context_to_runtime(
    handler, mock_runtime
):
    mock_runtime.admission_required = True
    mock_runtime.admission_policy = SimpleNamespace(logical_session_id="global")
    mock_runtime.require_sandbox_admission = mock.AsyncMock()
    mock_runtime.execute.return_value = BoxExecutionResult(
        session_id=_physical_session_id("global"),
        backend_name="nsjail",
        status=BoxExecutionStatus.COMPLETED,
        exit_code=0,
        stdout="ok",
        stderr="",
        duration_ms=1,
    )

    resp = await _invoke(
        handler,
        LangBotToBoxAction.EXEC,
        _spec_data(session_id="caller-controlled"),
    )

    assert resp.code == 0
    assert resp.data["session_id"] == "global"
    mock_runtime.execute.assert_awaited_once()
    (spec,) = mock_runtime.execute.await_args.args
    assert spec.session_id == "caller-controlled"
    assert mock_runtime.execute.await_args.kwargs["action_context"] == _ACTION_CONTEXT
    mock_runtime.require_sandbox_admission.assert_awaited_once_with(_ACTION_CONTEXT)


# ── CREATE_SESSION ───────────────────────────────────────────────────


async def test_create_session_success(handler, mock_runtime):
    mock_runtime.create_session.return_value = {
        "session_id": _physical_session_id("s1"),
        "image": "img",
    }
    resp = await _invoke(handler, LangBotToBoxAction.CREATE_SESSION, _spec_data())
    assert resp.code == 0
    assert resp.data["session_id"] == "s1"
    mock_runtime.create_session.assert_awaited_once()


async def test_create_session_invalid_spec(handler, mock_runtime):
    resp = await _invoke(handler, LangBotToBoxAction.CREATE_SESSION, {"cmd": "echo hi"})
    assert resp.code == 1
    assert "BoxValidationError" in resp.message
    mock_runtime.create_session.assert_not_awaited()


# ── GET_SESSION / GET_SESSIONS / DELETE_SESSION ──────────────────────


async def test_get_session(handler, mock_runtime):
    mock_runtime.get_session.return_value = {
        "session_id": _physical_session_id("abc"),
        "managed_process": {"session_id": _physical_session_id("abc")},
    }
    resp = await _invoke(handler, LangBotToBoxAction.GET_SESSION, {"session_id": "abc"})
    assert resp.code == 0
    assert resp.data == {
        "session_id": "abc",
        "managed_process": {"session_id": "abc"},
    }
    mock_runtime.get_session.assert_called_once_with(_physical_session_id("abc"))


async def test_grant_enforced_session_lookup_rejects_non_global_id(
    handler, mock_runtime
):
    mock_runtime.admission_required = True
    mock_runtime.admission_policy = SimpleNamespace(logical_session_id="global")
    mock_runtime.require_sandbox_admission = mock.AsyncMock()

    with pytest.raises(BoxAdmissionError, match="session_id is runtime-owned"):
        await _invoke(
            handler,
            LangBotToBoxAction.GET_SESSION,
            {"session_id": "caller-controlled"},
        )
    mock_runtime.get_session.assert_not_called()


async def test_get_sessions_wraps_list(handler, mock_runtime):
    mock_runtime.get_sessions_for_workspace.return_value = [
        {"session_id": _physical_session_id("a")},
        {"session_id": _physical_session_id("b")},
        {"session_id": "ws-other-foreign"},
    ]
    resp = await _invoke(handler, LangBotToBoxAction.GET_SESSIONS, {})
    assert resp.code == 0
    assert resp.data == {
        "sessions": [
            {"session_id": "a"},
            {"session_id": "b"},
        ]
    }


async def test_delete_session(handler, mock_runtime):
    resp = await _invoke(
        handler, LangBotToBoxAction.DELETE_SESSION, {"session_id": "gone"}
    )
    assert resp.code == 0
    assert resp.data == {"deleted": "gone"}
    mock_runtime.delete_session.assert_awaited_once_with(_physical_session_id("gone"))


# ── MANAGED PROCESS ──────────────────────────────────────────────────


async def test_start_managed_process_success(handler, mock_runtime):
    mock_runtime.start_managed_process.return_value = {
        "process_id": "p1",
        "status": "running",
    }
    data = {
        "session_id": "s1",
        "spec": {"process_id": "p1", "command": "python", "args": ["-V"]},
    }
    resp = await _invoke(handler, LangBotToBoxAction.START_MANAGED_PROCESS, data)
    assert resp.code == 0
    assert resp.data["process_id"] == "p1"
    mock_runtime.start_managed_process.assert_awaited_once()
    (session_id, spec_arg), _ = mock_runtime.start_managed_process.call_args
    assert session_id == _physical_session_id("s1")
    assert spec_arg.command == "python"
    assert spec_arg.process_id == "p1"


async def test_start_managed_process_invalid_spec(handler, mock_runtime):
    # Empty command fails BoxManagedProcessSpec validation.
    data = {"session_id": "s1", "spec": {"command": ""}}
    resp = await _invoke(handler, LangBotToBoxAction.START_MANAGED_PROCESS, data)
    assert resp.code == 1
    assert "BoxValidationError" in resp.message
    mock_runtime.start_managed_process.assert_not_awaited()


async def test_get_managed_process_defaults_process_id(handler, mock_runtime):
    resp = await _invoke(
        handler, LangBotToBoxAction.GET_MANAGED_PROCESS, {"session_id": "s1"}
    )
    assert resp.code == 0
    mock_runtime.get_managed_process.assert_called_once_with(
        _physical_session_id("s1"), "default"
    )


async def test_get_managed_process_explicit_process_id(handler, mock_runtime):
    await _invoke(
        handler,
        LangBotToBoxAction.GET_MANAGED_PROCESS,
        {"session_id": "s1", "process_id": "p2"},
    )
    mock_runtime.get_managed_process.assert_called_once_with(
        _physical_session_id("s1"), "p2"
    )


async def test_stop_managed_process_default(handler, mock_runtime):
    resp = await _invoke(
        handler, LangBotToBoxAction.STOP_MANAGED_PROCESS, {"session_id": "s1"}
    )
    assert resp.code == 0
    assert resp.data == {"stopped": "default"}
    mock_runtime.stop_managed_process.assert_awaited_once_with(
        _physical_session_id("s1"), "default"
    )


async def test_stop_managed_process_explicit(handler, mock_runtime):
    resp = await _invoke(
        handler,
        LangBotToBoxAction.STOP_MANAGED_PROCESS,
        {"session_id": "s1", "process_id": "p3"},
    )
    assert resp.data == {"stopped": "p3"}
    mock_runtime.stop_managed_process.assert_awaited_once_with(
        _physical_session_id("s1"), "p3"
    )


# ── INIT / SHUTDOWN ──────────────────────────────────────────────────


async def test_host_control_installs_grant_and_advances_generation_fence(
    handler, mock_runtime
):
    mock_runtime.upsert_sandbox_admission_grant = mock.AsyncMock(
        return_value={"installed": True}
    )
    grant = SandboxAdmissionGrant(
        instance_uuid=_ACTION_CONTEXT.instance_uuid,
        workspace_uuid=_ACTION_CONTEXT.workspace_uuid,
        execution_generation=2,
        entitlement_revision=4,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=60),
        max_sessions=1,
        max_managed_processes=0,
    )

    resp = await _invoke(
        handler,
        LangBotToBoxAction.UPSERT_SANDBOX_ADMISSION_GRANT,
        grant.model_dump(mode="json"),
    )

    assert resp.code == 0
    assert resp.data == {"installed": True}
    mock_runtime.upsert_sandbox_admission_grant.assert_awaited_once_with(grant)
    handler._generation_fence.require_current(
        _ACTION_CONTEXT.model_copy(update={"placement_generation": 2})
    )


async def test_host_control_rejects_grant_for_another_instance(handler, mock_runtime):
    mock_runtime.upsert_sandbox_admission_grant = mock.AsyncMock()
    grant = SandboxAdmissionGrant(
        instance_uuid="instance-b",
        workspace_uuid=_ACTION_CONTEXT.workspace_uuid,
        execution_generation=1,
        entitlement_revision=1,
        expires_at=dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=60),
        max_sessions=1,
        max_managed_processes=0,
    )

    with pytest.raises(PermissionError, match="trusted instance"):
        await _invoke(
            handler,
            LangBotToBoxAction.UPSERT_SANDBOX_ADMISSION_GRANT,
            grant.model_dump(mode="json"),
        )
    mock_runtime.upsert_sandbox_admission_grant.assert_not_awaited()


async def test_host_control_revokes_grant(handler, mock_runtime):
    mock_runtime.revoke_sandbox_admission_grant = mock.AsyncMock(
        return_value={"revoked": True}
    )
    revocation = SandboxAdmissionRevocation(
        instance_uuid=_ACTION_CONTEXT.instance_uuid,
        workspace_uuid=_ACTION_CONTEXT.workspace_uuid,
        entitlement_revision=5,
    )

    resp = await _invoke(
        handler,
        LangBotToBoxAction.REVOKE_SANDBOX_ADMISSION_GRANT,
        revocation.model_dump(mode="json"),
    )

    assert resp.code == 0
    assert resp.data == {"revoked": True}
    mock_runtime.revoke_sandbox_admission_grant.assert_awaited_once_with(revocation)


async def test_init(handler, mock_runtime):
    config = {"backend": "docker"}
    resp = await _invoke(handler, LangBotToBoxAction.INIT, config)
    assert resp.code == 0
    assert resp.data == {"initialized": True}
    mock_runtime.init.assert_called_once_with(config)


async def test_init_rejects_host_without_secure_control(mock_connection, mock_runtime):
    handler = _new_handler(mock_connection, mock_runtime)

    resp = await _invoke(handler, LangBotToBoxAction.INIT, {"backend": "host"})

    assert resp.code != 0
    assert "LANGBOT_BOX_CONTROL_TOKEN" in resp.message
    mock_runtime.init.assert_not_called()


async def test_init_allows_host_for_local_or_token_control(
    mock_connection, mock_runtime
):
    handler = _new_handler(
        mock_connection,
        mock_runtime,
        allow_host_backend=True,
    )

    resp = await _invoke(handler, LangBotToBoxAction.INIT, {"backend": "host"})

    assert resp.code == 0
    mock_runtime.init.assert_called_once_with({"backend": "host"})


async def test_shutdown(handler, mock_runtime):
    resp = await _invoke(handler, LangBotToBoxAction.SHUTDOWN, {})
    assert resp.code == 0
    assert resp.data == {}
    mock_runtime.shutdown.assert_awaited_once()


# ── App factory ──────────────────────────────────────────────────────


def test_create_app_registers_routes_and_runtime(mock_runtime):
    app = create_app(mock_runtime, control_token=_CONTROL_TOKEN)
    assert isinstance(app, web.Application)
    assert app["runtime"] is mock_runtime
    assert app[server._ACTIVE_WEBSOCKETS_KEY] == set()
    assert server._close_active_websockets in app.on_shutdown

    routes = {(route.method, route.resource.canonical) for route in app.router.routes()}
    assert ("GET", "/healthz") in routes
    assert ("GET", "/readyz") in routes
    assert ("GET", "/rpc/ws") in routes
    assert (
        "GET",
        "/v1/sessions/{session_id}/managed-process/{process_id}/ws",
    ) in routes
    assert (
        "GET",
        "/v1/sessions/{session_id}/managed-process/ws",
    ) in routes


def test_create_ws_relay_app_is_alias(mock_runtime):
    app = create_ws_relay_app(mock_runtime, control_token=_CONTROL_TOKEN)
    assert isinstance(app, web.Application)
    assert app["runtime"] is mock_runtime


def test_create_app_allows_unconfigured_control_token(monkeypatch, mock_runtime):
    monkeypatch.delenv(server.BOX_CONTROL_TOKEN_ENV, raising=False)

    app = create_app(mock_runtime)

    assert app["_box_control_token"] == ""


def test_create_app_rejects_invalid_configured_control_token(mock_runtime):
    with pytest.raises(ValueError, match=server.BOX_CONTROL_TOKEN_ENV):
        create_app(mock_runtime, control_token="too-short")


async def test_run_server_cleans_runtime_when_app_setup_fails(monkeypatch):
    calls = []

    class FakeRuntime:
        max_admission_records = 100

        def __init__(self, *, logger, instance_id=None, data_dir=None):
            self.logger = logger

        async def initialize(self):
            calls.append("initialize")

        async def shutdown(self):
            calls.append("shutdown")

        async def stop_background_reaper(self):
            calls.append("stop_background_reaper")

    monkeypatch.setenv(server.BOX_CONTROL_TOKEN_ENV, _CONTROL_TOKEN)
    monkeypatch.setattr(server, "BoxRuntime", FakeRuntime)
    monkeypatch.setattr(
        server,
        "configure_bounded_default_executor_from_env",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(
        server,
        "create_app",
        lambda *_args, **_kwargs: (_ for _ in ()).throw(RuntimeError("setup failed")),
    )

    with pytest.raises(RuntimeError, match="setup failed"):
        await server._run_server("127.0.0.1", 5410, "ws")

    assert calls == ["initialize", "shutdown", "stop_background_reaper"]


async def test_run_server_fails_closed_and_cleans_up_on_ws_bind_error(
    monkeypatch,
):
    calls = []

    class FakeRuntime:
        max_admission_records = 100

        def __init__(self, *, logger, instance_id=None, data_dir=None):
            self.logger = logger

        async def initialize(self):
            calls.append("initialize")

        async def shutdown(self):
            calls.append("shutdown")

        async def stop_background_reaper(self):
            calls.append("stop_background_reaper")

    class FakeRunner:
        def __init__(self, _app):
            pass

        async def setup(self):
            calls.append("runner_setup")

        async def cleanup(self):
            calls.append("runner_cleanup")

    class FakeSite:
        def __init__(self, _runner, _host, _port):
            pass

        async def start(self):
            raise OSError("address in use")

    monkeypatch.setenv(server.BOX_CONTROL_TOKEN_ENV, _CONTROL_TOKEN)
    monkeypatch.setattr(server, "BoxRuntime", FakeRuntime)
    monkeypatch.setattr(
        server,
        "configure_bounded_default_executor_from_env",
        lambda **_kwargs: object(),
    )
    monkeypatch.setattr(server.web, "AppRunner", FakeRunner)
    monkeypatch.setattr(server.web, "TCPSite", FakeSite)

    with pytest.raises(OSError, match="address in use"):
        await server._run_server("127.0.0.1", 5410, "ws")

    assert calls == [
        "initialize",
        "runner_setup",
        "runner_cleanup",
        "shutdown",
        "stop_background_reaper",
    ]


async def test_healthz_is_liveness_only():
    blocking_executor = mock.MagicMock()
    blocking_executor.snapshot.return_value = {
        "max_workers": 8,
        "max_pending": 128,
        "inflight": 0,
    }
    running = SimpleNamespace(is_running=True)
    completed = SimpleNamespace(is_running=False)
    runtime = SimpleNamespace(
        blocking_executor=blocking_executor,
        _sessions={
            "session-a": SimpleNamespace(
                managed_processes={
                    "running": running,
                    "completed": completed,
                }
            )
        },
        _creating_session_tasks=set(),
        _closing_session_tasks=set(),
        _background_tasks=set(),
    )
    request = mock.MagicMock()
    request.app = {server._APP_RUNTIME_KEY: runtime}

    response = await handle_healthz(request)

    assert response.status == 200
    assert '"live": true' in response.text
    assert '"sessions": 1' in response.text
    assert '"managed_processes": 1' in response.text
    assert '"completed_processes": 1' in response.text
    assert '"max_pending": 128' in response.text
    assert '"event_loop": {}' in response.text


async def test_healthz_does_not_scan_sessions_without_managed_processes():
    class NoGlobalIterationDict(dict):
        def __iter__(self):
            raise AssertionError("Box health globally scanned persistent sessions")

        def items(self):
            raise AssertionError("Box health globally scanned persistent sessions")

        def values(self):
            raise AssertionError("Box health globally scanned persistent sessions")

    runtime = SimpleNamespace(
        blocking_executor=None,
        _sessions=NoGlobalIterationDict(
            {
                "workspace-a": SimpleNamespace(managed_processes={}),
                "workspace-b": SimpleNamespace(managed_processes={}),
            }
        ),
        _managed_process_session_ids=set(),
        _creating_session_tasks=set(),
        _closing_session_tasks=set(),
        _background_tasks=set(),
    )
    request = mock.MagicMock()
    request.app = {server._APP_RUNTIME_KEY: runtime}

    response = await handle_healthz(request)

    assert response.status == 200
    assert '"sessions": 2' in response.text
    assert '"managed_processes": 0' in response.text


async def test_readyz_returns_503_when_strict_checks_fail(mock_runtime):
    mock_runtime.get_readiness = mock.AsyncMock(
        return_value={"ready": False, "checks": {"cgroup_v2": False}}
    )
    request = mock.MagicMock()
    request.app = {"runtime": mock_runtime}

    response = await handle_readyz(request)

    assert response.status == 503
    assert '"ready": false' in response.text
    assert '"resources":' in response.text
    assert '"event_loop": {}' in response.text


# ── handle_rpc_ws ────────────────────────────────────────────────────


async def test_handle_rpc_ws_prepares_ws_and_runs_handler(mock_runtime):
    fake_ws = mock.MagicMock()
    fake_ws.prepare = mock.AsyncMock()

    request = mock.MagicMock()
    request.app = {
        "runtime": mock_runtime,
        "_box_control_token": _CONTROL_TOKEN,
        "_box_trusted_instance_uuid": {"value": None},
        "_box_generation_fence": BoxGenerationFence(),
    }
    request.headers = {
        BOX_CONTROL_TOKEN_HEADER: _CONTROL_TOKEN,
        BOX_INSTANCE_HEADER: _ACTION_CONTEXT.instance_uuid,
    }

    run_mock = mock.AsyncMock()
    with (
        mock.patch.object(server.web, "WebSocketResponse", return_value=fake_ws),
        mock.patch.object(BoxServerHandler, "run", run_mock),
    ):
        result = await handle_rpc_ws(request)

    assert result is fake_ws
    fake_ws.prepare.assert_awaited_once_with(request)
    run_mock.assert_awaited_once()
    assert request.app[server._ACTIVE_WEBSOCKETS_KEY] == set()


async def test_close_active_websockets_closes_every_client(mock_runtime):
    app = create_app(mock_runtime, control_token=_CONTROL_TOKEN)
    first_ws = mock.MagicMock()
    first_ws.close = mock.AsyncMock()
    second_ws = mock.MagicMock()
    second_ws.close = mock.AsyncMock(side_effect=ConnectionResetError)
    app[server._ACTIVE_WEBSOCKETS_KEY].update((first_ws, second_ws))

    await server._close_active_websockets(app)

    for ws in (first_ws, second_ws):
        ws.close.assert_awaited_once_with(
            code=WSCloseCode.GOING_AWAY,
            message=b"Box runtime shutting down",
        )


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {
            BOX_CONTROL_TOKEN_HEADER: "wrong-token-that-is-still-long-enough-123",
            BOX_INSTANCE_HEADER: _ACTION_CONTEXT.instance_uuid,
        },
    ],
)
async def test_handle_rpc_ws_rejects_missing_or_wrong_token_before_upgrade(
    mock_runtime, headers
):
    request = mock.MagicMock()
    request.app = {
        "runtime": mock_runtime,
        "_box_control_token": _CONTROL_TOKEN,
        "_box_trusted_instance_uuid": {"value": None},
    }
    request.headers = headers

    with mock.patch.object(server.web, "WebSocketResponse") as websocket_response:
        result = await handle_rpc_ws(request)

    assert result.status == 401
    assert result.text == "Unauthorized"
    websocket_response.assert_not_called()


@pytest.mark.parametrize("supplied_token", ["", _CONTROL_TOKEN])
async def test_handle_rpc_ws_allows_optional_token_when_runtime_is_unconfigured(
    mock_runtime, supplied_token
):
    fake_ws = mock.MagicMock()
    fake_ws.prepare = mock.AsyncMock()
    request = mock.MagicMock()
    request.app = {
        "runtime": mock_runtime,
        "_box_control_token": "",
        "_box_trusted_instance_uuid": {"value": None},
        "_box_generation_fence": BoxGenerationFence(),
    }
    request.headers = {BOX_INSTANCE_HEADER: _ACTION_CONTEXT.instance_uuid}
    if supplied_token:
        request.headers[BOX_CONTROL_TOKEN_HEADER] = supplied_token

    run_mock = mock.AsyncMock()
    with (
        mock.patch.object(server.web, "WebSocketResponse", return_value=fake_ws),
        mock.patch.object(BoxServerHandler, "run", run_mock),
    ):
        result = await handle_rpc_ws(request)

    assert result is fake_ws
    assert (
        request.app["_box_trusted_instance_uuid"]["value"]
        == _ACTION_CONTEXT.instance_uuid
    )
    run_mock.assert_awaited_once()


async def test_handle_rpc_ws_pins_instance_and_rejects_rebind(mock_runtime):
    app = {
        "runtime": mock_runtime,
        "_box_control_token": _CONTROL_TOKEN,
        "_box_trusted_instance_uuid": {"value": None},
        "_box_generation_fence": BoxGenerationFence(),
    }

    async def connect(instance_uuid: str):
        fake_ws = mock.MagicMock()
        fake_ws.prepare = mock.AsyncMock()
        request = mock.MagicMock()
        request.app = app
        request.headers = {
            BOX_CONTROL_TOKEN_HEADER: _CONTROL_TOKEN,
            BOX_INSTANCE_HEADER: instance_uuid,
        }
        with (
            mock.patch.object(server.web, "WebSocketResponse", return_value=fake_ws),
            mock.patch.object(BoxServerHandler, "run", mock.AsyncMock()),
        ):
            return await handle_rpc_ws(request)

    assert await connect(_ACTION_CONTEXT.instance_uuid)
    rejected = await connect("instance-b")

    assert app["_box_trusted_instance_uuid"]["value"] == _ACTION_CONTEXT.instance_uuid
    assert rejected.status == 401


# ── handle_managed_process_ws error/early-return paths ───────────────


def _ws_request(
    runtime,
    session_id="s1",
    process_id=None,
    *,
    token=_CONTROL_TOKEN,
    expected_token=_CONTROL_TOKEN,
    instance_uuid=_ACTION_CONTEXT.instance_uuid,
    bound_instance_uuid=_ACTION_CONTEXT.instance_uuid,
    action_context=_ACTION_CONTEXT,
    generation_fence=None,
):
    generation_fence = generation_fence or BoxGenerationFence()
    generation_fence.observe(action_context)
    if not str(session_id).startswith(
        workspace_session_namespace_prefix(action_context)
    ):
        session_id = namespace_session_id(action_context, session_id)
    request = mock.MagicMock()
    request.app = {
        "runtime": runtime,
        "_box_control_token": expected_token,
        "_box_trusted_instance_uuid": {"value": bound_instance_uuid},
        "_box_generation_fence": generation_fence,
    }
    request.headers = {
        BOX_INSTANCE_HEADER: instance_uuid,
        BOX_WORKSPACE_HEADER: action_context.workspace_uuid,
        BOX_PLACEMENT_GENERATION_HEADER: str(action_context.placement_generation),
    }
    if token:
        request.headers[BOX_CONTROL_TOKEN_HEADER] = token
    match_info = {"session_id": session_id}
    if process_id is not None:
        match_info["process_id"] = process_id
    # match_info.get used in source; emulate dict.get default behavior.
    request.match_info = match_info
    return request


@pytest.mark.parametrize(
    "request_kwargs",
    [
        {"token": "wrong-token-that-is-still-long-enough-123"},
        {"bound_instance_uuid": None},
        {"instance_uuid": "instance-b"},
    ],
)
async def test_managed_process_ws_rejects_untrusted_attach_before_lookup(
    mock_runtime, request_kwargs
):
    mock_runtime._sessions = {"secret-session": mock.MagicMock()}
    request = _ws_request(
        mock_runtime,
        session_id="secret-session",
        **request_kwargs,
    )

    resp = await handle_managed_process_ws(request)

    assert resp.status == 401
    assert resp.text == "Unauthorized"


async def test_managed_process_ws_requires_workspace_generation_headers(
    mock_runtime,
):
    mock_runtime._sessions = {"secret-session": mock.MagicMock()}
    request = _ws_request(mock_runtime, session_id="secret-session")
    request.headers.pop(BOX_WORKSPACE_HEADER)

    resp = await handle_managed_process_ws(request)

    assert resp.status == 401
    assert resp.text == "Unauthorized"


async def test_managed_process_ws_rejects_session_from_old_generation(
    mock_runtime,
):
    generation_fence = BoxGenerationFence()
    second_context = _ACTION_CONTEXT.model_copy(update={"placement_generation": 2})
    generation_fence.observe(second_context)
    old_session_id = _physical_session_id("secret")
    mock_runtime._sessions = {old_session_id: mock.MagicMock()}
    request = _ws_request(
        mock_runtime,
        session_id=old_session_id,
        action_context=second_context,
        generation_fence=generation_fence,
    )

    resp = await handle_managed_process_ws(request)

    assert resp.status == 401
    assert resp.text == "Unauthorized"


async def test_managed_process_ws_session_not_found(mock_runtime):
    mock_runtime._sessions = {}
    request = _ws_request(mock_runtime, session_id="missing")
    resp = await handle_managed_process_ws(request)
    assert isinstance(resp, web.Response)
    assert resp.status == 400
    assert "BoxSessionNotFoundError" in resp.text


async def test_managed_process_ws_allows_tokenless_unconfigured_runtime(mock_runtime):
    mock_runtime._sessions = {}
    request = _ws_request(
        mock_runtime,
        session_id="missing",
        token="",
        expected_token="",
    )

    resp = await handle_managed_process_ws(request)

    assert resp.status == 400
    assert "BoxSessionNotFoundError" in resp.text


async def test_managed_process_ws_process_not_found(mock_runtime):
    runtime_session = mock.MagicMock()
    runtime_session.managed_processes = {}
    mock_runtime._sessions = {_physical_session_id("s1"): runtime_session}
    request = _ws_request(mock_runtime, session_id="s1", process_id="p1")
    resp = await handle_managed_process_ws(request)
    assert isinstance(resp, web.Response)
    assert resp.status == 400
    assert "BoxManagedProcessNotFoundError" in resp.text


async def test_managed_process_ws_process_not_running(mock_runtime):
    managed = mock.MagicMock()
    managed.is_running = False
    runtime_session = mock.MagicMock()
    runtime_session.managed_processes = {"default": managed}
    mock_runtime._sessions = {_physical_session_id("s1"): runtime_session}
    request = _ws_request(mock_runtime, session_id="s1", process_id="default")
    resp = await handle_managed_process_ws(request)
    assert isinstance(resp, web.Response)
    assert resp.status == 400
    assert "BoxManagedProcessConflictError" in resp.text


async def test_managed_process_ws_stdio_unavailable_closes_ws(mock_runtime):
    # A running process whose stdio is unavailable -> ws closed with message.
    process = SimpleNamespace(stdout=None, stdin=None)
    managed = mock.MagicMock()
    managed.is_running = True
    managed.process = process
    # Real asyncio.Lock so `async with managed_process.attach_lock` works.
    managed.attach_lock = asyncio.Lock()

    runtime_session = mock.MagicMock()
    runtime_session.managed_processes = {"default": managed}
    mock_runtime._sessions = {_physical_session_id("s1"): runtime_session}

    fake_ws = mock.MagicMock()
    fake_ws.prepare = mock.AsyncMock()
    fake_ws.close = mock.AsyncMock()

    request = _ws_request(mock_runtime, session_id="s1", process_id="default")
    with mock.patch.object(server.web, "WebSocketResponse", return_value=fake_ws):
        result = await handle_managed_process_ws(request)

    assert result is fake_ws
    fake_ws.prepare.assert_awaited_once_with(request)
    fake_ws.close.assert_awaited_once()


async def test_managed_process_ws_forwards_stdout_and_closes(mock_runtime):
    class FakeStdout:
        def __init__(self):
            # A plugin may emit a large payload without a newline. The relay
            # must consume bounded chunks instead of readline(), whose stream
            # limit can otherwise terminate the attachment.
            self.chunks = [b"x" * (64 * 1024), b"tail", b""]

        async def read(self, max_bytes):
            assert max_bytes == 64 * 1024
            return self.chunks.pop(0)

    class BlockingWebSocket:
        def __init__(self):
            self.sent = []
            self.closed = False

        async def prepare(self, _request):
            return None

        async def send_str(self, value):
            self.sent.append(value)

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.Event().wait()

        async def close(self, **_kwargs):
            self.closed = True

    managed = mock.MagicMock()
    managed.is_running = True
    managed.process = SimpleNamespace(
        stdout=FakeStdout(),
        stdin=mock.MagicMock(),
    )
    managed.attach_lock = asyncio.Lock()
    runtime_session = SimpleNamespace(
        managed_processes={"default": managed},
        info=SimpleNamespace(last_used_at=None),
    )
    mock_runtime._sessions = {_physical_session_id("s1"): runtime_session}
    fake_ws = BlockingWebSocket()
    request = _ws_request(mock_runtime, session_id="s1")

    with mock.patch.object(server.web, "WebSocketResponse", return_value=fake_ws):
        result = await handle_managed_process_ws(request)

    assert result is fake_ws
    assert fake_ws.sent == ["x" * (64 * 1024), "tail"]
    assert fake_ws.closed is True
    assert runtime_session.info.last_used_at is not None


async def test_managed_process_ws_forwards_text_stdin(mock_runtime):
    class BlockingStdout:
        async def read(self, _max_bytes):
            await asyncio.Event().wait()

    class FakeStdin:
        def __init__(self):
            self.writes = []
            self.drains = 0

        def write(self, value):
            self.writes.append(value)

        async def drain(self):
            self.drains += 1

    class InputWebSocket:
        def __init__(self):
            self.messages = iter(
                (
                    SimpleNamespace(type=web.WSMsgType.TEXT, data="ping"),
                    SimpleNamespace(type=web.WSMsgType.CLOSE, data=None),
                )
            )
            self.closed = False

        async def prepare(self, _request):
            return None

        async def send_str(self, _value):
            return None

        def __aiter__(self):
            return self

        async def __anext__(self):
            try:
                return next(self.messages)
            except StopIteration as exc:
                raise StopAsyncIteration from exc

        async def close(self, **_kwargs):
            self.closed = True

    stdin = FakeStdin()
    managed = mock.MagicMock()
    managed.is_running = True
    managed.process = SimpleNamespace(
        stdout=BlockingStdout(),
        stdin=stdin,
    )
    managed.attach_lock = asyncio.Lock()
    runtime_session = SimpleNamespace(
        managed_processes={"default": managed},
        info=SimpleNamespace(last_used_at=None),
    )
    mock_runtime._sessions = {_physical_session_id("s1"): runtime_session}
    fake_ws = InputWebSocket()
    request = _ws_request(mock_runtime, session_id="s1")

    with mock.patch.object(server.web, "WebSocketResponse", return_value=fake_ws):
        result = await handle_managed_process_ws(request)

    assert result is fake_ws
    assert stdin.writes == [b"ping\n"]
    assert stdin.drains == 1
    assert fake_ws.closed is True
    assert runtime_session.info.last_used_at is not None


async def test_managed_process_ws_requires_process_admission(mock_runtime):
    mock_runtime.admission_required = True
    mock_runtime.require_sandbox_admission = mock.AsyncMock(
        return_value=SimpleNamespace(max_managed_processes=0)
    )
    request = _ws_request(mock_runtime, session_id="s1")

    response = await handle_managed_process_ws(request)

    assert response.status == 400
    assert "does not permit managed process relay" in response.text
    mock_runtime.require_sandbox_admission.assert_awaited_once_with(_ACTION_CONTEXT)


async def test_active_managed_process_relay_closes_when_generation_advances(
    mock_runtime,
):
    class BlockingStdout:
        async def read(self, _max_bytes):
            await asyncio.Event().wait()

    class FakeStdin:
        def write(self, _value):
            raise AssertionError("stale relay must not forward stdin")

        async def drain(self):
            return None

    class BlockingWebSocket:
        def __init__(self):
            self.prepared = asyncio.Event()
            self.closed = asyncio.Event()

        async def prepare(self, _request):
            self.prepared.set()

        async def send_str(self, _value):
            raise AssertionError("stale relay must not forward stdout")

        def __aiter__(self):
            return self

        async def __anext__(self):
            await asyncio.Event().wait()

        async def close(self, **_kwargs):
            self.closed.set()

    generation_fence = BoxGenerationFence()
    managed = mock.MagicMock()
    managed.is_running = True
    managed.process = SimpleNamespace(
        stdout=BlockingStdout(),
        stdin=FakeStdin(),
    )
    managed.attach_lock = asyncio.Lock()
    runtime_session = mock.MagicMock()
    runtime_session.managed_processes = {"default": managed}
    session_id = _physical_session_id("active")
    mock_runtime._sessions = {session_id: runtime_session}
    fake_ws = BlockingWebSocket()
    request = _ws_request(
        mock_runtime,
        session_id=session_id,
        generation_fence=generation_fence,
    )

    with mock.patch.object(server.web, "WebSocketResponse", return_value=fake_ws):
        relay_task = asyncio.create_task(handle_managed_process_ws(request))
        await asyncio.wait_for(fake_ws.prepared.wait(), timeout=1)
        generation_fence.observe(
            _ACTION_CONTEXT.model_copy(update={"placement_generation": 2})
        )
        result = await asyncio.wait_for(relay_task, timeout=1)

    assert result is fake_ws
    assert fake_ws.closed.is_set()


# ── Sanity: error classes used by the relay are importable/usable ────


def test_relay_error_classes_render():
    for exc in (
        BoxSessionNotFoundError("a"),
        BoxManagedProcessNotFoundError("b"),
        BoxManagedProcessConflictError("c"),
    ):
        resp = _error_response(exc)
        assert resp.status == 400
