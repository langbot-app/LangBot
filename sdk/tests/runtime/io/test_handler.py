from __future__ import annotations

import asyncio
import base64
import contextlib
import errno
import json
import os
import shutil
import stat
import tempfile
import threading

import pytest

from langbot_plugin.entities.io.actions.enums import ActionType, CommonAction
from langbot_plugin.entities.io.errors import (
    ActionCallError,
    ActionCallTimeoutError,
    ConnectionClosedError,
)
from langbot_plugin.entities.io.resp import ActionResponse, ChunkStatus
from langbot_plugin.entities.io.context import ActionContext, InstallationBinding
from langbot_plugin.runtime.io.connection import Connection
from langbot_plugin.runtime.io import handler as handler_module
from langbot_plugin.runtime.io.handler import (
    FILE_CHUNK_LENGTH,
    MAX_INLINE_REGISTRATION_BYTES,
    Handler,
)
from langbot_plugin.runtime.security import (
    PLUGIN_FILE_STORAGE_DIR_ENV,
    PLUGIN_RUNTIME_PROFILE_ENV,
)
from langbot_plugin.runtime.bounded_executor import (
    blocking_work_scope,
    current_blocking_work_scope,
)

from tests.helpers.protocol import ProtocolConnection


def _transfer_entry_name(path: str | os.PathLike[str]) -> str:
    """Return the entry name a transfer filesystem call targets.

    Descriptor-relative calls receive a bare entry name; the path-backed
    fallback used where ``dir_fd`` is unavailable receives the resolved
    absolute path.  Fixtures key off the entry name so both shapes match.
    """

    return os.path.basename(os.fspath(path))


def _confine_absolute_opens(monkeypatch, granted) -> None:
    """Deny absolute-path opens outside ``granted``, like an app sandbox.

    A confinement profile grants one subtree instead of relying on UNIX
    permissions, so every component above the grant is refused even though the
    granted subtree stays reachable by its full path.  Relative (``dir_fd``)
    opens always target something inside the grant and stay allowed.
    """

    real_open = os.open

    def confinement_open(path, flags, *args, **kwargs):
        target = os.fspath(path)
        if os.path.isabs(target):
            resolved = os.path.realpath(target)
            if resolved != str(granted) and not resolved.startswith(
                str(granted) + os.sep
            ):
                raise PermissionError(
                    errno.EACCES, "denied by confinement profile", target
                )
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "open", confinement_open)


def _symlinks_supported() -> bool:
    """Whether this host may create symlinks (Windows needs a privilege)."""

    directory = tempfile.mkdtemp(prefix="lbp-symlink-probe-")
    try:
        os.symlink(__file__, os.path.join(directory, "probe-link"))
        return True
    except (OSError, NotImplementedError):
        return False
    finally:
        shutil.rmtree(directory, ignore_errors=True)


SYMLINK_SUPPORTED = _symlinks_supported()
DESCRIPTOR_ROOT_SUPPORTED = handler_module._DIRECTORY_HANDLE_SUPPORTED

requires_symlinks = pytest.mark.skipif(
    not SYMLINK_SUPPORTED,
    reason="host cannot create symlinks (Windows requires developer mode)",
)
requires_descriptor_root = pytest.mark.skipif(
    not DESCRIPTOR_ROOT_SUPPORTED,
    reason="asserts descriptor-relative transfer root semantics (POSIX only)",
)
requires_path_only_open = pytest.mark.skipif(
    getattr(os, "O_PATH", None) is None,
    reason="needs O_PATH to inspect a directory without read permission",
)
requires_unreadable_directories = pytest.mark.skipif(
    not hasattr(os, "geteuid") or os.geteuid() == 0,
    reason="permission bits only restrict non-root POSIX users",
)


class SampleAction(ActionType):
    ECHO = "echo"
    STREAM = "stream"


class QueueConnection(Connection):
    def __init__(self):
        self.incoming: asyncio.Queue[str | BaseException] = asyncio.Queue()
        self.sent: list[str] = []
        self.sent_event = asyncio.Event()
        self.closed = False
        self.close_calls = 0

    async def send(self, message: str) -> None:
        self.sent.append(message)
        self.sent_event.set()

    async def receive(self) -> str:
        message = await self.incoming.get()
        if isinstance(message, BaseException):
            raise message
        return message

    async def close(self) -> None:
        self.close_calls += 1
        self.closed = True


class FailingSendConnection(QueueConnection):
    async def send(self, message: str) -> None:
        raise ConnectionClosedError("send failed")


async def _wait_for_sent(conn: QueueConnection, count: int = 1) -> list[dict]:
    for _ in range(50):
        if len(conn.sent) >= count:
            return [json.loads(message) for message in conn.sent]
        await asyncio.sleep(0.01)
    raise AssertionError(f"timed out waiting for {count} sent messages")


@pytest.mark.asyncio
async def test_first_inline_send_bypasses_handler_encoder(monkeypatch):
    conn = QueueConnection()
    setattr(conn, "_first_message_send_inline", True)
    handler = Handler(conn)

    async def blocked_encode(*args, **kwargs):
        raise AssertionError("ordinary encoder must not run")

    monkeypatch.setattr(handler, "_encode_message", blocked_encode)
    task = asyncio.create_task(
        handler.call_action(SampleAction.ECHO, {"message": "hello"}, timeout=1)
    )
    [request] = await _wait_for_sent(conn)
    handler.resp_waiters[request["seq_id"]].set_result(
        ActionResponse(
            seq_id=request["seq_id"], code=0, message="ok", data={"ok": True}
        )
    )

    assert await task == {"ok": True}


@pytest.mark.asyncio
async def test_first_inline_receive_rejects_oversized_frame_before_json_decode(
    monkeypatch,
):
    conn = QueueConnection()
    handler = Handler(conn)
    monkeypatch.setattr(handler, "_uses_reserved_decode_capacity", lambda message: True)
    monkeypatch.setattr(
        handler, "_uses_reserved_action_capacity", lambda req_data: True
    )
    decoded = False

    def forbidden_decode(_message):
        nonlocal decoded
        decoded = True
        raise AssertionError("oversized frame must be rejected before JSON decoding")

    monkeypatch.setattr(handler_module.json, "loads", forbidden_decode)
    await conn.incoming.put(" " * (MAX_INLINE_REGISTRATION_BYTES + 1))
    await conn.incoming.put(ConnectionClosedError("done"))

    await handler.run()

    assert decoded is False


@pytest.mark.asyncio
async def test_call_action_sends_request_and_returns_response_data():
    conn = QueueConnection()
    handler = Handler(conn)

    task = asyncio.create_task(
        handler.call_action(SampleAction.ECHO, {"message": "hello"}, timeout=1)
    )
    [request] = await _wait_for_sent(conn)
    assert request["action"] == "echo"
    assert request["data"] == {"message": "hello"}

    handler.resp_waiters[request["seq_id"]].set_result(
        ActionResponse(
            seq_id=request["seq_id"], code=0, message="ok", data={"ok": True}
        )
    )

    assert await task == {"ok": True}
    assert request["seq_id"] not in handler.resp_waiters


@pytest.mark.asyncio
async def test_escaped_invocation_cannot_reuse_host_authority():
    from langbot_plugin.api.proxies.invocation import bind_invocation

    conn = QueueConnection()
    handler = Handler(conn)
    captured = None

    async def escaped_call():
        await asyncio.sleep(0)
        return await handler.call_action(SampleAction.ECHO, {}, timeout=0.1)

    with bind_invocation(handler, config={"tenant": "a"}):
        captured = asyncio.create_task(escaped_call())

    with pytest.raises(RuntimeError, match="ended"):
        await captured
    assert conn.sent == []


@pytest.mark.asyncio
async def test_escaped_invocation_cannot_delete_after_waiting_for_file_lock(tmp_path):
    from langbot_plugin.api.proxies.invocation import bind_invocation

    handler = Handler(QueueConnection(), file_storage_dir=tmp_path)
    handler._file_transfer_lock = asyncio.Lock()
    deleted = []

    def fake_delete(*args):
        deleted.append(args)
        return True

    handler._delete_transfer_sync = fake_delete
    await handler._file_transfer_lock.acquire()
    with bind_invocation(handler, config={"tenant": "a"}):
        task = asyncio.create_task(handler.delete_local_file("ft1_" + "a" * 64))
        await asyncio.sleep(0)
    handler._file_transfer_lock.release()

    with pytest.raises(RuntimeError, match="invocation has ended"):
        await task
    assert deleted == []


def _action_context(workspace_uuid="workspace-a", installation_uuid=None):
    return ActionContext(
        instance_uuid="instance-1",
        workspace_uuid=workspace_uuid,
        placement_generation=5,
        installation_uuid=installation_uuid,
    )


@pytest.mark.asyncio
async def test_call_action_carries_bound_context_outside_data_payload():
    conn = QueueConnection()
    handler = Handler(conn)
    context = _action_context(installation_uuid="installation-1")
    handler.bind_action_context(context)

    task = asyncio.create_task(handler.call_action(SampleAction.ECHO, {}, timeout=1))
    [request] = await _wait_for_sent(conn)

    assert request["data"] == {}
    assert request["context"] == context.model_dump()

    handler.resp_waiters[request["seq_id"]].set_result(
        ActionResponse(seq_id=request["seq_id"], code=0, message="ok", data={})
    )
    await task


def test_nested_outbound_action_inherits_current_inbound_context():
    handler = Handler(QueueConnection())
    context = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=5,
        installation_uuid="installation-1",
        runtime_revision=2,
        artifact_digest="a" * 64,
    )
    token = handler._current_action_context.set(context)
    try:
        assert handler.resolve_outbound_action_context(None) == context
    finally:
        handler._current_action_context.reset(token)


@pytest.mark.asyncio
async def test_bound_handler_accepts_legacy_peer_request_without_context():
    """SDK 0.4.x peers omit the context envelope; the trusted binding supplies it."""

    conn = ProtocolConnection()
    handler = Handler(conn)
    binding = _action_context(installation_uuid="installation-1")
    handler.bind_action_context(binding)
    seen = []

    @handler.action(SampleAction.ECHO)
    async def echo(data):
        seen.append((data, handler.current_action_context))
        return ActionResponse.success({"ok": True})

    run_task = asyncio.create_task(handler.run())
    await conn.incoming.put(
        json.dumps(
            {
                "seq_id": 7,
                "action": SampleAction.ECHO.value,
                "data": {"legacy": True},
            }
        )
    )
    [response] = await conn.sent_messages(1)
    await conn.close_peer()
    await run_task

    assert response["code"] == 0
    assert response["data"] == {"ok": True}
    assert seen == [({"legacy": True}, binding)]


def test_handler_binding_is_idempotent_but_cannot_change_workspace_or_installation():
    handler = Handler(QueueConnection())
    workspace_binding = _action_context()

    assert handler.bind_action_context(workspace_binding) == workspace_binding
    assert handler.bind_action_context(workspace_binding) == workspace_binding

    installation_binding = workspace_binding.for_installation("installation-1")
    assert handler.bind_action_context(installation_binding) == installation_binding

    with pytest.raises(ValueError, match="another Workspace"):
        handler.bind_action_context(_action_context(workspace_uuid="workspace-b"))
    with pytest.raises(ValueError, match="another plugin installation"):
        handler.bind_action_context(
            workspace_binding.for_installation("installation-2")
        )
    with pytest.raises(ValueError, match="cannot be removed"):
        handler.bind_action_context(workspace_binding)


@pytest.mark.asyncio
async def test_handler_json_codec_uses_workspace_bounded_thread(monkeypatch):
    handler = Handler(QueueConnection())
    handler.bind_action_context(_action_context(workspace_uuid="workspace-a"))
    calls = []

    async def fake_to_thread(fn, *args, **kwargs):
        calls.append((fn, current_blocking_work_scope()))
        return fn(*args, **kwargs)

    monkeypatch.setattr(handler_module.asyncio, "to_thread", fake_to_thread)

    assert await handler._decode_message('{"ok": true}') == {"ok": True}
    assert json.loads(await handler._encode_message({"ok": True})) == {"ok": True}
    assert calls[0] == (json.loads, "workspace-a")
    assert calls[1][1] == "workspace-a"
    assert len(calls) == 2


def test_handler_preserves_complete_installation_binding_and_rejects_downgrade():
    handler = Handler(QueueConnection())
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=5,
        installation_uuid="installation-1",
        runtime_revision=2,
        artifact_digest="a" * 64,
    )

    assert handler.bind_action_context(binding.model_dump()) == binding
    assert isinstance(handler.bound_action_context, InstallationBinding)
    with pytest.raises(ValueError, match="revision or artifact"):
        handler.bind_action_context(
            ActionContext(
                instance_uuid=binding.instance_uuid,
                workspace_uuid=binding.workspace_uuid,
                placement_generation=binding.placement_generation,
                installation_uuid=binding.installation_uuid,
            )
        )
    with pytest.raises(ValueError, match="revision or artifact"):
        handler.bind_action_context(binding.model_copy(update={"runtime_revision": 3}))


@pytest.mark.asyncio
async def test_run_exposes_validated_context_to_action_and_rejects_mismatch():
    conn = ProtocolConnection()
    handler = Handler(conn)
    binding = _action_context()
    handler.bind_action_context(binding)
    seen = []

    @handler.action(SampleAction.ECHO)
    async def echo(_data):
        seen.append(
            (
                handler.current_action_context,
                current_blocking_work_scope(),
            )
        )
        return ActionResponse.success({})

    run_task = asyncio.create_task(handler.run())
    await conn.send_peer_request("echo", {}, seq_id=1)
    [success] = await conn.sent_messages(1)
    assert success["code"] == 0
    assert seen == [(binding, binding.workspace_uuid)]

    await conn.send_peer_request(
        "echo",
        {},
        seq_id=2,
        action_context=_action_context(workspace_uuid="workspace-b"),
    )
    responses = await conn.sent_messages(2)
    assert responses[1]["code"] == 1
    assert "does not match connection Workspace" in responses[1]["message"]
    assert seen == [(binding, binding.workspace_uuid)]

    await conn.close_peer()
    await run_task


@pytest.mark.asyncio
async def test_call_action_cancellation_cancels_peer_action():
    class PairedConnection(Connection):
        def __init__(self):
            self.incoming = asyncio.Queue()
            self.peer = None

        async def send(self, message: str) -> None:
            await self.peer.incoming.put(message)

        async def receive(self) -> str:
            return await self.incoming.get()

        async def close(self) -> None:
            pass

    connection_a = PairedConnection()
    connection_b = PairedConnection()
    connection_a.peer = connection_b
    connection_b.peer = connection_a
    caller = Handler(connection_a)
    peer = Handler(connection_b)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    @peer.action(CommonAction.PING)
    async def hang(_data):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            cancelled.set()
        return ActionResponse.success({})

    caller_run = asyncio.create_task(caller.run())
    peer_run = asyncio.create_task(peer.run())
    call = asyncio.create_task(
        caller.call_action(
            CommonAction.PING,
            {},
            timeout=None,
            cancel_peer_on_cancel=True,
        )
    )
    await started.wait()
    call.cancel()
    with pytest.raises(asyncio.CancelledError):
        await call
    await asyncio.wait_for(cancelled.wait(), timeout=1)
    assert peer._action_tasks == set()
    assert caller.resp_waiters == {}

    caller_run.cancel()
    peer_run.cancel()
    await asyncio.gather(caller_run, peer_run, return_exceptions=True)


@pytest.mark.parametrize("streaming", [False, True])
@pytest.mark.parametrize("trigger", ["cancel", "timeout"])
@pytest.mark.parametrize("revoked", [False, True])
async def test_peer_cancellation_survives_repeated_cancel_and_revocation(
    streaming, trigger, revoked
):
    from langbot_plugin.api.proxies.invocation import (
        bind_invocation,
        invocation_capability,
    )

    caller, peer = Handler(ProtocolConnection()), Handler(ProtocolConnection())
    started, sending_cancel, release_cancel, stopped = (
        asyncio.Event() for _ in range(4)
    )
    context = ActionContext(
        instance_uuid="instance", workspace_uuid="workspace", placement_generation=1
    )
    cancellations = []
    requests = []

    async def send(message):
        request = json.loads(message)
        requests.append(request)
        if request.get("action") == CommonAction.CANCEL_ACTION.value:
            cancellations.append(request)
            sending_cancel.set()
            await release_cancel.wait()
        await peer.conn.incoming.put(message)

    caller.conn.send = send
    peer.conn.send = caller.conn.incoming.put

    @peer.action(SampleAction.ECHO)
    async def block(_data):
        assert peer.current_action_context == context
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            stopped.set()

    async def call():
        timeout = 0.1 if trigger == "timeout" else None
        if streaming:
            async for _ in caller.call_action_generator(
                SampleAction.ECHO, {}, timeout=timeout, action_context=context
            ):
                pass
        else:
            await caller.call_action(
                SampleAction.ECHO,
                {},
                timeout=timeout,
                action_context=context,
                cancel_peer_on_cancel=True,
            )

    loops = [asyncio.create_task(handler.run()) for handler in (caller, peer)]
    task = None
    try:
        with bind_invocation(caller):
            task = asyncio.create_task(call())
            await asyncio.wait_for(started.wait(), 1)
            if revoked:
                invocation_capability(caller).active = False
                with pytest.raises(RuntimeError, match="invocation has ended"):
                    await caller.call_action(SampleAction.ECHO, {})
            if trigger == "cancel":
                task.cancel()
            await asyncio.wait_for(sending_cancel.wait(), 1)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            release_cancel.set()
            with pytest.raises(asyncio.CancelledError):
                await asyncio.wait_for(task, 1)
        await asyncio.wait_for(stopped.wait(), 1)
        assert len(cancellations) == 1
        assert cancellations[0]["data"] == {"seq_id": requests[0]["seq_id"]}
        assert cancellations[0]["context"] == requests[0]["context"]
        assert caller.resp_waiters == {}
        assert caller.resp_queues == {}
        assert peer._action_tasks == set()
    finally:
        release_cancel.set()
        actions = list(peer._action_tasks)
        tasks = [*actions, *loops, *([task] if task is not None else [])]
        for pending in tasks:
            pending.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


async def test_repeated_cancellation_keeps_cleanup_send_bounded():
    conn = ProtocolConnection()
    caller = Handler(conn)
    sending_cancel, send_closed = asyncio.Event(), asyncio.Event()
    send = conn.send

    async def blocked_send(message):
        if json.loads(message).get("action") == CommonAction.CANCEL_ACTION.value:
            sending_cancel.set()
            try:
                await asyncio.Event().wait()
            finally:
                send_closed.set()
        await send(message)

    conn.send = blocked_send
    task = asyncio.create_task(
        caller.call_action(
            SampleAction.ECHO, {}, timeout=None, cancel_peer_on_cancel=True
        )
    )
    try:
        await conn.sent_messages(1)
        task.cancel()
        await asyncio.wait_for(sending_cancel.wait(), 1)
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(task, 6)
        assert send_closed.is_set()
        assert caller.resp_waiters == {}
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


async def test_action_timeout_clears_waiter():
    conn = QueueConnection()
    handler = Handler(conn)

    with pytest.raises(ActionCallTimeoutError, match="Action echo call timed out"):
        await handler.call_action(SampleAction.ECHO, {}, timeout=0.01)

    assert handler.resp_waiters == {}


@pytest.mark.asyncio
async def test_call_action_send_failure_cleans_waiter_immediately():
    handler = Handler(FailingSendConnection())

    with pytest.raises(ConnectionClosedError, match="send failed"):
        await handler.call_action(SampleAction.ECHO, {}, timeout=10)

    assert handler.resp_waiters == {}


@pytest.mark.asyncio
async def test_disconnect_fails_pending_unary_and_stream_calls():
    conn = ProtocolConnection()
    handler = Handler(conn)
    run_task = asyncio.create_task(handler.run())
    unary = asyncio.create_task(handler.call_action(SampleAction.ECHO, {}, timeout=10))

    async def consume_stream():
        async for _ in handler.call_action_generator(
            SampleAction.STREAM, {}, timeout=10
        ):
            pass

    stream = asyncio.create_task(consume_stream())
    await conn.sent_messages(2)
    await conn.close_peer()

    with pytest.raises(ConnectionClosedError):
        await asyncio.wait_for(unary, timeout=0.5)
    with pytest.raises(ConnectionClosedError):
        await asyncio.wait_for(stream, timeout=0.5)
    await run_task
    assert handler.resp_waiters == {}
    assert handler.resp_queues == {}


@pytest.mark.asyncio
async def test_reconnect_still_fails_requests_from_old_transport():
    first = QueueConnection()
    second = QueueConnection()
    reconnects = 0

    async def reconnect(current_handler):
        nonlocal reconnects
        reconnects += 1
        if reconnects == 1:
            current_handler.conn = second
            return True
        return False

    handler = Handler(first, reconnect)
    run_task = asyncio.create_task(handler.run())
    old_call = asyncio.create_task(
        handler.call_action(SampleAction.ECHO, {}, timeout=10)
    )
    await _wait_for_sent(first)
    await first.incoming.put(ConnectionClosedError("old transport closed"))

    with pytest.raises(ConnectionClosedError, match="old transport closed"):
        await asyncio.wait_for(old_call, timeout=0.5)

    new_call = asyncio.create_task(
        handler.call_action(SampleAction.ECHO, {}, timeout=1)
    )
    [request] = await _wait_for_sent(second)
    await second.incoming.put(
        json.dumps(
            ActionResponse.success({"generation": 2})
            .model_copy(update={"seq_id": request["seq_id"]})
            .model_dump()
        )
    )
    assert await new_call == {"generation": 2}

    await second.incoming.put(ConnectionClosedError("done"))
    await run_task


@pytest.mark.asyncio
async def test_run_ignores_non_object_json_message():
    conn = QueueConnection()
    handler = Handler(conn)

    @handler.action(SampleAction.ECHO)
    async def echo(data):
        return ActionResponse.success(data)

    run_task = asyncio.create_task(handler.run())
    await conn.incoming.put("[]")
    await conn.incoming.put(
        json.dumps({"seq_id": 4, "action": "echo", "data": {"ok": True}})
    )
    [response] = await _wait_for_sent(conn)
    await conn.incoming.put(ConnectionClosedError("done"))
    await run_task

    assert response["data"] == {"ok": True}


@pytest.mark.asyncio
async def test_slow_inbound_action_does_not_block_outbound_response_routing():
    conn = ProtocolConnection()
    handler = Handler(conn)
    release = asyncio.Event()

    @handler.action(SampleAction.STREAM)
    async def slow_action(_data):
        await release.wait()
        return ActionResponse.success({})

    run_task = asyncio.create_task(handler.run())
    await conn.send_peer_request("stream", {}, seq_id=77)
    call_task = asyncio.create_task(
        handler.call_action(SampleAction.ECHO, {}, timeout=1)
    )
    [request] = await conn.sent_messages(1)
    await conn.send_peer_response(request["seq_id"], data={"ok": True})

    assert await asyncio.wait_for(call_task, timeout=0.5) == {"ok": True}
    release.set()
    await conn.sent_messages(2)
    await conn.close_peer()
    await run_task


@pytest.mark.asyncio
async def test_call_action_error_response_should_preserve_peer_message():
    conn = QueueConnection()
    handler = Handler(conn)
    task = asyncio.create_task(handler.call_action(SampleAction.ECHO, {}, timeout=1))
    [request] = await _wait_for_sent(conn)

    handler.resp_waiters[request["seq_id"]].set_result(
        ActionResponse(
            seq_id=request["seq_id"],
            code=1,
            message="peer failed",
            data={"error": {"code": "peer.failed"}},
        )
    )

    with pytest.raises(ActionCallError, match="^peer failed$") as exc_info:
        await task

    assert exc_info.value.data == {"error": {"code": "peer.failed"}}


@pytest.mark.asyncio
async def test_call_action_generator_yields_chunks_until_end():
    conn = QueueConnection()
    handler = Handler(conn)
    context = _action_context(installation_uuid="installation-1")
    handler.bind_action_context(context)
    chunks: list[dict] = []

    async def consume():
        async for chunk in handler.call_action_generator(
            SampleAction.STREAM, {}, timeout=1
        ):
            chunks.append(chunk)

    task = asyncio.create_task(consume())
    [request] = await _wait_for_sent(conn)
    assert request["context"] == context.model_dump()
    queue = handler.resp_queues[request["seq_id"]]
    await queue.put(
        ActionResponse(
            seq_id=request["seq_id"],
            code=0,
            message="ok",
            data={"part": 1},
            chunk_status=ChunkStatus.CONTINUE,
        )
    )
    await queue.put(
        ActionResponse(
            seq_id=request["seq_id"],
            code=0,
            message="ok",
            data={},
            chunk_status=ChunkStatus.END,
        )
    )

    await task
    assert chunks == [{"part": 1}]
    assert handler.resp_queues == {}


@pytest.mark.asyncio
async def test_call_action_generator_cancel_propagates_and_cleans_queue():
    conn = QueueConnection()
    handler = Handler(conn)

    async def consume():
        async for _chunk in handler.call_action_generator(
            SampleAction.STREAM, {}, timeout=1
        ):
            pass

    task = asyncio.create_task(consume())
    [request] = await _wait_for_sent(conn)

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task

    assert request["seq_id"] not in handler.resp_queues


@pytest.mark.asyncio
async def test_run_dispatches_registered_action_and_sends_response():
    conn = QueueConnection()
    handler = Handler(conn)

    @handler.action(SampleAction.ECHO)
    async def echo(data):
        return ActionResponse.success({"echo": data["message"]})

    task = asyncio.create_task(handler.run())
    await conn.incoming.put(
        json.dumps({"seq_id": 7, "action": "echo", "data": {"message": "hi"}})
    )
    [response] = await _wait_for_sent(conn)
    await conn.incoming.put(ConnectionClosedError("closed"))
    await task

    assert response["seq_id"] == 7
    assert response["code"] == 0
    assert response["data"] == {"echo": "hi"}


@pytest.mark.asyncio
async def test_run_sends_error_response_for_unknown_action():
    conn = QueueConnection()
    handler = Handler(conn)

    task = asyncio.create_task(handler.run())
    await conn.incoming.put(json.dumps({"seq_id": 9, "action": "missing", "data": {}}))
    [response] = await _wait_for_sent(conn)
    await conn.incoming.put(ConnectionClosedError("closed"))
    await task

    assert response["seq_id"] == 9
    assert response["code"] == 1
    assert "Action missing not found" in response["message"]


@pytest.mark.asyncio
async def test_forwarded_action_error_preserves_permission_code_and_details():
    conn = QueueConnection()
    handler = Handler(conn)
    details = {"code": "permission_denied", "denied_operations": ["stats.basic"]}

    @handler.action(SampleAction.ECHO)
    async def denied(_data):
        raise ActionCallError("Workspace operation has not been granted", data=details)

    task = asyncio.create_task(handler.run())
    await conn.incoming.put(json.dumps({"seq_id": 9, "action": "echo", "data": {}}))
    [response] = await _wait_for_sent(conn)
    await conn.incoming.put(ConnectionClosedError("closed"))
    await task
    assert response["code"] == 1
    assert response["data"] == details


@pytest.mark.asyncio
async def test_run_handles_streaming_action_response():
    conn = QueueConnection()
    handler = Handler(conn)
    context = _action_context()
    handler.bind_action_context(context)
    seen_contexts = []

    @handler.action(SampleAction.STREAM)
    async def stream(_data):
        seen_contexts.append(handler.current_action_context)
        yield ActionResponse.success({"part": 1})
        yield ActionResponse.success({"part": 2})

    task = asyncio.create_task(handler.run())
    await conn.incoming.put(json.dumps({"seq_id": 3, "action": "stream", "data": {}}))
    responses = await _wait_for_sent(conn, count=3)
    await conn.incoming.put(ConnectionClosedError("closed"))
    await task

    assert [response["chunk_status"] for response in responses] == [
        "continue",
        "continue",
        "end",
    ]
    assert [response["data"] for response in responses] == [
        {"part": 1},
        {"part": 2},
        {},
    ]
    assert seen_contexts == [context]


@pytest.mark.asyncio
async def test_run_does_not_cancel_active_streaming_action_by_default():
    conn = QueueConnection()
    handler = Handler(conn)
    started = asyncio.Event()
    release = asyncio.Event()
    cancelled = asyncio.Event()
    finished = asyncio.Event()

    @handler.action(SampleAction.STREAM)
    async def stream(_data):
        started.set()
        try:
            await release.wait()
            yield ActionResponse.success({"part": "late"})
        except asyncio.CancelledError:
            cancelled.set()
            raise
        finally:
            finished.set()

    task = asyncio.create_task(handler.run())
    await conn.incoming.put(json.dumps({"seq_id": 3, "action": "stream", "data": {}}))
    await asyncio.wait_for(started.wait(), timeout=1)

    await conn.incoming.put(ConnectionClosedError("closed"))
    await task

    assert not cancelled.is_set()
    assert handler._active_tasks == set()

    release.set()
    await asyncio.wait_for(finished.wait(), timeout=1)


@pytest.mark.asyncio
async def test_run_cancels_active_streaming_action_on_disconnect_when_enabled():
    conn = QueueConnection()
    handler = Handler(conn, cancel_active_tasks_on_close=True)
    started = asyncio.Event()
    cancelled = asyncio.Event()

    @handler.action(SampleAction.STREAM)
    async def stream(_data):
        started.set()
        try:
            while True:
                await asyncio.sleep(60)
                yield ActionResponse.success({"part": "late"})
        finally:
            cancelled.set()

    task = asyncio.create_task(handler.run())
    await conn.incoming.put(json.dumps({"seq_id": 3, "action": "stream", "data": {}}))
    await asyncio.wait_for(started.wait(), timeout=1)

    await conn.incoming.put(ConnectionClosedError("closed"))
    await task

    assert cancelled.is_set()
    assert handler._active_tasks == set()


@pytest.mark.asyncio
async def test_send_file_calls_file_chunk_action_for_each_chunk(monkeypatch):
    conn = QueueConnection()
    handler = Handler(conn)
    calls: list[dict] = []
    action_context = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=5,
        installation_uuid="installation-1",
        runtime_revision=2,
        artifact_digest="a" * 64,
    )

    async def fake_call_action(action, data, timeout=15.0, action_context=None):
        calls.append(
            {
                "action": action,
                "data": data,
                "timeout": timeout,
                "action_context": action_context,
            }
        )
        return {}

    monkeypatch.setattr(handler, "call_action", fake_call_action)
    file_key = await handler.send_file(
        b"abc",
        "txt",
        action_context=action_context,
    )

    assert file_key.endswith(".txt")
    assert calls[0]["action"] is CommonAction.FILE_CHUNK
    assert calls[0]["data"]["file_length"] == 3
    assert calls[0]["data"]["chunk_amount"] == 1
    assert calls[0]["action_context"] == action_context


def test_handler_file_storage_dir_is_created_for_instances(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    Handler(QueueConnection())

    assert (tmp_path / "data" / "temp" / "lbp").is_dir()


def test_shared_worker_file_storage_uses_private_writable_tmp(tmp_path, monkeypatch):
    worker_tmp = tmp_path / "lbp-rpc"
    monkeypatch.setenv(PLUGIN_RUNTIME_PROFILE_ENV, "shared")
    monkeypatch.setattr(
        "langbot_plugin.runtime.io.handler.SHARED_WORKER_FILE_STORAGE_DIR",
        str(worker_tmp),
    )

    handler = Handler(QueueConnection())

    assert handler.file_storage_dir == str(worker_tmp)
    assert worker_tmp.is_dir()


def test_worker_file_storage_env_overrides_read_only_artifact_cwd(
    tmp_path, monkeypatch
):
    artifact_dir = tmp_path / "artifact" / "code"
    artifact_dir.mkdir(parents=True)
    artifact_dir.chmod(0o555)
    worker_tmp = tmp_path / "installation" / "rpc-transfer"
    monkeypatch.chdir(artifact_dir)
    monkeypatch.setenv(PLUGIN_RUNTIME_PROFILE_ENV, "oss_dev")
    monkeypatch.setenv(PLUGIN_FILE_STORAGE_DIR_ENV, str(worker_tmp))

    handler = Handler(QueueConnection())

    assert handler.file_storage_dir == str(worker_tmp)
    assert worker_tmp.is_dir()


def test_handler_file_storage_can_be_isolated_per_installation(tmp_path):
    first = Handler(
        QueueConnection(),
        file_storage_dir=tmp_path / "installation-a" / "rpc-transfer",
    )
    second = Handler(
        QueueConnection(),
        file_storage_dir=tmp_path / "installation-b" / "rpc-transfer",
    )

    assert first.file_storage_dir != second.file_storage_dir
    assert (tmp_path / "installation-a" / "rpc-transfer").is_dir()
    assert (tmp_path / "installation-b" / "rpc-transfer").is_dir()
    if os.name != "nt":
        assert (
            stat.S_IMODE((tmp_path / "installation-a" / "rpc-transfer").stat().st_mode)
            == 0o700
        )


# ---------------------------------------------------------------------------
# Response routing through the receive loop (run()).
#
# The tests above resolve futures by poking handler.resp_waiters directly,
# which bypasses run(). These drive a real response message in through the
# connection so the full request -> wire -> response -> waiter path is covered.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_run_routes_response_to_call_action_waiter():
    conn = ProtocolConnection()
    handler = Handler(conn)
    run_task = asyncio.create_task(handler.run())

    call_task = asyncio.create_task(
        handler.call_action(SampleAction.ECHO, {"x": 1}, timeout=1)
    )
    [request] = await conn.sent_messages(1)
    assert request["action"] == "echo"

    await conn.send_peer_response(request["seq_id"], code=0, data={"ok": True})

    assert await call_task == {"ok": True}
    assert handler.resp_waiters == {}

    await conn.close_peer()
    await run_task


@pytest.mark.asyncio
async def test_run_routes_streaming_response_to_generator_queue():
    conn = ProtocolConnection()
    handler = Handler(conn)
    run_task = asyncio.create_task(handler.run())

    chunks: list[dict] = []

    async def consume():
        async for chunk in handler.call_action_generator(
            SampleAction.STREAM, {}, timeout=1
        ):
            chunks.append(chunk)

    consume_task = asyncio.create_task(consume())
    [request] = await conn.sent_messages(1)
    seq_id = request["seq_id"]

    await conn.send_peer_response(seq_id, data={"part": 1}, chunk_status="continue")
    await conn.send_peer_response(seq_id, data={"part": 2}, chunk_status="continue")
    await conn.send_peer_response(seq_id, data={}, chunk_status="end")

    await consume_task
    assert chunks == [{"part": 1}, {"part": 2}]
    assert handler.resp_queues == {}

    await conn.close_peer()
    await run_task


@pytest.mark.asyncio
async def test_run_skips_none_message_and_keeps_running():
    conn = ProtocolConnection()
    handler = Handler(conn)

    @handler.action(SampleAction.ECHO)
    async def echo(data):
        return ActionResponse.success({"seen": data})

    run_task = asyncio.create_task(handler.run())
    await conn.incoming.put(None)  # receive() returns None -> loop should just continue

    await conn.send_peer_request("echo", {"v": 1}, seq_id=5)
    [response] = await conn.sent_messages(1)

    assert response["seq_id"] == 5
    assert response["data"] == {"seen": {"v": 1}}

    await conn.close_peer()
    await run_task


@pytest.mark.asyncio
async def test_run_reconnects_while_disconnect_callback_returns_true():
    conn = ProtocolConnection()
    handler = Handler(conn)

    attempts: list[Handler] = []

    async def on_disconnect(h: Handler) -> bool:
        attempts.append(h)
        return len(attempts) < 2  # reconnect once, then give up

    handler.set_disconnect_callback(on_disconnect)

    run_task = asyncio.create_task(handler.run())
    await conn.incoming.put(ConnectionClosedError("drop-1"))  # -> reconnect (True)
    await conn.incoming.put(ConnectionClosedError("drop-2"))  # -> give up -> break
    await run_task

    assert len(attempts) == 2
    assert attempts[0] is handler


@pytest.mark.asyncio
async def test_run_supports_sync_action_handler_returning_response():
    conn = ProtocolConnection()
    handler = Handler(conn)

    # A handler whose return value is an ActionResponse rather than a coroutine;
    # run() handles this via its `isinstance(response, Coroutine)` guard.
    def sync_echo(data):
        return ActionResponse.success({"echoed": data})

    handler.actions[SampleAction.ECHO.value] = sync_echo

    run_task = asyncio.create_task(handler.run())
    await conn.send_peer_request("echo", {"a": 1}, seq_id=11)
    [response] = await conn.sent_messages(1)

    assert response["seq_id"] == 11
    assert response["data"] == {"echoed": {"a": 1}}

    await conn.close_peer()
    await run_task


@pytest.mark.asyncio
async def test_call_action_wraps_unexpected_future_error():
    conn = ProtocolConnection()
    handler = Handler(conn)

    call_task = asyncio.create_task(
        handler.call_action(SampleAction.ECHO, {}, timeout=1)
    )
    [request] = await conn.sent_messages(1)

    # An arbitrary exception delivered on the waiter (not a normal ActionResponse)
    # is wrapped as ActionCallError instead of leaking the raw exception type.
    handler.resp_waiters[request["seq_id"]].set_exception(RuntimeError("kaboom"))

    with pytest.raises(ActionCallError, match="RuntimeError: kaboom"):
        await call_task

    assert handler.resp_waiters == {}


# ---------------------------------------------------------------------------
# Streaming error / timeout / cancellation paths in call_action_generator.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_call_action_generator_raises_on_error_chunk():
    conn = ProtocolConnection()
    handler = Handler(conn)

    captured: dict[str, str] = {}

    async def consume():
        try:
            async for _ in handler.call_action_generator(
                SampleAction.STREAM, {}, timeout=1
            ):
                pass
        except ActionCallError as exc:
            captured["error"] = str(exc)

    task = asyncio.create_task(consume())
    [request] = await conn.sent_messages(1)
    queue = handler.resp_queues[request["seq_id"]]
    await queue.put(
        ActionResponse(seq_id=request["seq_id"], code=1, message="stream boom", data={})
    )

    await task
    assert captured["error"] == "stream boom"
    assert handler.resp_queues == {}


@pytest.mark.asyncio
async def test_call_action_generator_times_out_without_response():
    conn = ProtocolConnection()
    handler = Handler(conn)

    async def consume():
        async for _ in handler.call_action_generator(
            SampleAction.STREAM, {}, timeout=0.01
        ):
            pass

    with pytest.raises(ActionCallTimeoutError, match="Action stream call timed out"):
        await consume()

    assert handler.resp_queues == {}


@pytest.mark.asyncio
async def test_call_action_generator_stops_on_cancellation():
    conn = ProtocolConnection()
    handler = Handler(conn)

    async def consume():
        async for _ in handler.call_action_generator(
            SampleAction.STREAM, {}, timeout=5
        ):
            pass

    task = asyncio.create_task(consume())
    [request] = await conn.sent_messages(1)  # generator is now blocked on queue.get
    assert request["seq_id"] in handler.resp_queues

    task.cancel()
    with contextlib.suppress(asyncio.CancelledError):
        await task

    # The generator's finally clause clears its queue regardless of how it exits.
    assert handler.resp_queues == {}


# ---------------------------------------------------------------------------
# Inbound file transfer: the __file_chunk handler reassembles chunks on disk,
# then read_local_file / delete_local_file round-trip them.
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_file_chunk_action_reassembles_file_and_read_delete_roundtrip(
    tmp_path, monkeypatch
):
    monkeypatch.chdir(tmp_path)
    conn = ProtocolConnection()
    handler = Handler(conn)

    payload = b"the quick brown fox jumps over the lazy dog" * 3
    file_key = "roundtrip.bin"
    chunk_handler = handler.actions[CommonAction.FILE_CHUNK.value]

    size = len(payload)
    step = (size + 2) // 3
    pieces = [payload[i : i + step] for i in range(0, size, step)]
    assert len(pieces) == 3  # exercises both the last-chunk and non-last branches

    for index, piece in enumerate(pieces):
        resp = await chunk_handler(
            {
                "file_key": file_key,
                "chunk_base64": base64.b64encode(piece).decode("utf-8"),
                "chunk_index": index,
                "chunk_amount": len(pieces),
            }
        )
        assert isinstance(resp, ActionResponse)
        assert resp.code == 0

    assert await handler.read_local_file(file_key) == payload

    # Delete once, then again: the second call must swallow FileNotFoundError.
    await handler.delete_local_file(file_key)
    await handler.delete_local_file(file_key)


@pytest.mark.asyncio
async def test_file_transfer_owner_uses_effective_context_and_denies_sibling(
    tmp_path,
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    binding_a = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    binding_b = binding_a.model_copy(
        update={
            "workspace_uuid": "workspace-b",
            "installation_uuid": "installation-b",
        }
    )
    token = handler._current_action_context.set(binding_a)
    try:
        await handler.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": "private.bin",
                "chunk_base64": base64.b64encode(b"A-secret").decode("ascii"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
    finally:
        handler._current_action_context.reset(token)

    token = handler._current_action_context.set(binding_b)
    try:
        with pytest.raises(FileNotFoundError):
            await handler.read_local_file("private.bin")
        await handler.delete_local_file("private.bin")
        await handler.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": "private.bin",
                "chunk_base64": base64.b64encode(b"B-data").decode("ascii"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
        assert await handler.read_local_file("private.bin") == b"B-data"
    finally:
        handler._current_action_context.reset(token)

    assert (
        await handler.read_local_file("private.bin", action_context=binding_a)
        == b"A-secret"
    )


@pytest.mark.asyncio
async def test_file_transfer_owner_survives_handler_recreation_and_failed_cleanup(
    tmp_path,
    monkeypatch,
):
    binding_a = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    binding_b = binding_a.model_copy(
        update={
            "workspace_uuid": "workspace-b",
            "installation_uuid": "installation-b",
        }
    )
    first = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    token = first._current_action_context.set(binding_a)
    try:
        await first.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": "private.bin",
                "chunk_base64": base64.b64encode(b"A-secret").decode("ascii"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
    finally:
        first._current_action_context.reset(token)

    async def fail_cleanup(*_args, **_kwargs):
        raise OSError("simulated cleanup failure")

    monkeypatch.setattr(handler_module, "run_blocking_cleanup", fail_cleanup)
    await first._cleanup_owned_transfers()

    restarted = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    assert (
        await restarted.read_local_file("private.bin", action_context=binding_a)
        == b"A-secret"
    )
    with pytest.raises(FileNotFoundError):
        await restarted.read_local_file("private.bin", action_context=binding_b)

    token = restarted._current_action_context.set(binding_b)
    try:
        await restarted.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": "private.bin",
                "chunk_base64": base64.b64encode(b"B-data").decode("ascii"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
        await restarted.delete_local_file("private.bin")
    finally:
        restarted._current_action_context.reset(token)

    assert (
        await restarted.read_local_file("private.bin", action_context=binding_a)
        == b"A-secret"
    )


@pytest.mark.asyncio
async def test_transfer_capability_recovers_exact_owner_without_current_context(
    tmp_path,
):
    sender = Handler(ProtocolConnection(), file_storage_dir=tmp_path / "sender")
    sent_chunks = []
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )

    async def capture_chunk(action, data, timeout=15.0, action_context=None):
        assert action is CommonAction.FILE_CHUNK
        sent_chunks.append((data, action_context))
        return {}

    sender.call_action = capture_chunk
    file_key = await sender.send_file(
        b"capability payload", "bin", action_context=binding
    )
    assert file_key.startswith("ft1_")

    receiver = Handler(ProtocolConnection(), file_storage_dir=tmp_path / "receiver")
    token = receiver._current_action_context.set(binding)
    try:
        for chunk, chunk_context in sent_chunks:
            assert chunk_context == binding
            await receiver.actions[CommonAction.FILE_CHUNK.value](chunk)
    finally:
        receiver._current_action_context.reset(token)

    assert await receiver.read_local_file(file_key) == b"capability payload"
    await receiver.delete_local_file(file_key)
    with pytest.raises(FileNotFoundError):
        await receiver.read_local_file(file_key)


@pytest.mark.asyncio
async def test_transfer_capability_owner_survives_handler_recreation(tmp_path):
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    file_key = f"ft1_{'1' * 64}.bin"
    first = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    token = first._current_action_context.set(binding)
    try:
        await first.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": file_key,
                "chunk_base64": base64.b64encode(b"restart payload").decode("ascii"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
    finally:
        first._current_action_context.reset(token)

    restarted = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    assert await restarted.read_local_file(file_key) == b"restart payload"


@pytest.mark.asyncio
async def test_transfer_capability_cleanup_removes_owner_record(tmp_path):
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    file_key = f"ft1_{'4' * 64}.bin"
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    token = handler._current_action_context.set(binding)
    try:
        await handler.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": file_key,
                "chunk_base64": base64.b64encode(b"cleanup payload").decode("ascii"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
    finally:
        handler._current_action_context.reset(token)

    owner_records = list((tmp_path / ".transfer-owners").iterdir())
    assert len(owner_records) == 1
    await handler._cleanup_owned_transfers()
    assert not owner_records[0].exists()


@pytest.mark.asyncio
async def test_transfer_capability_rejects_cross_slot_read_write_and_delete(tmp_path):
    binding_a = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    binding_b = binding_a.model_copy(
        update={
            "workspace_uuid": "workspace-b",
            "installation_uuid": "installation-b",
        }
    )
    file_key = f"ft1_{'2' * 64}.bin"
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    token = handler._current_action_context.set(binding_a)
    try:
        await handler.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": file_key,
                "chunk_base64": base64.b64encode(b"A-secret").decode("ascii"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
    finally:
        handler._current_action_context.reset(token)

    token = handler._current_action_context.set(binding_b)
    try:
        with pytest.raises(FileNotFoundError):
            await handler.read_local_file(file_key)
        await handler.delete_local_file(file_key)
        with pytest.raises(ValueError, match="Invalid file transfer capability"):
            await handler.actions[CommonAction.FILE_CHUNK.value](
                {
                    "file_key": file_key,
                    "chunk_base64": base64.b64encode(b"B-overwrite").decode("ascii"),
                    "chunk_index": 0,
                    "chunk_amount": 1,
                }
            )
    finally:
        handler._current_action_context.reset(token)

    assert (
        await handler.read_local_file(file_key, action_context=binding_a) == b"A-secret"
    )


@pytest.mark.asyncio
async def test_transfer_capability_corrupt_owner_record_fails_closed(tmp_path):
    binding = InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid="workspace-a",
        placement_generation=1,
        installation_uuid="installation-a",
        runtime_revision=1,
        artifact_digest="a" * 64,
    )
    file_key = f"ft1_{'3' * 64}.bin"
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    token = handler._current_action_context.set(binding)
    try:
        await handler.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": file_key,
                "chunk_base64": base64.b64encode(b"protected").decode("ascii"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
    finally:
        handler._current_action_context.reset(token)

    owner_records = list((tmp_path / ".transfer-owners").iterdir())
    assert len(owner_records) == 1
    owner_records[0].write_text("{}")
    restarted = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await restarted.read_local_file(file_key)


def _installation_binding(name: str = "a") -> InstallationBinding:
    return InstallationBinding(
        instance_uuid="instance-1",
        workspace_uuid=f"workspace-{name}",
        placement_generation=1,
        installation_uuid=f"installation-{name}",
        runtime_revision=1,
        artifact_digest=name * 64,
    )


async def _write_chunk(
    handler: Handler,
    file_key: str,
    payload: bytes,
    *,
    binding: InstallationBinding | None = None,
    index: int = 0,
    amount: int = 1,
) -> None:
    token = handler._current_action_context.set(binding)
    try:
        await handler.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": file_key,
                "chunk_base64": base64.b64encode(payload).decode("ascii"),
                "chunk_index": index,
                "chunk_amount": amount,
            }
        )
    finally:
        handler._current_action_context.reset(token)


def _staging_files(root) -> list:
    return [path for path in root.rglob(".payload-*.tmp")]


@pytest.mark.asyncio
async def test_cancel_after_stage_creation_reconciles_worker_before_close(
    tmp_path, monkeypatch
):
    connection = QueueConnection()
    handler = Handler(connection, file_storage_dir=tmp_path)
    file_key = f"ft1_{'c' * 64}.bin"
    stage_created = threading.Event()
    release_stage = threading.Event()
    staged_descriptor = None

    def pause_after_staging_create(event, **details):
        nonlocal staged_descriptor
        if event != "after_staging_create":
            return
        staged_descriptor = details["descriptor"]
        stage_created.set()
        assert release_stage.wait(timeout=2)

    monkeypatch.setattr(handler, "_transfer_race_hook", pause_after_staging_create)

    async def run_in_thread(fn, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: fn(*args))

    monkeypatch.setattr(handler_module.asyncio, "to_thread", run_in_thread)
    chunk_task = asyncio.create_task(_write_chunk(handler, file_key, b"cancelled"))
    assert await asyncio.to_thread(stage_created.wait, 1)

    chunk_task.cancel()
    await asyncio.sleep(0)
    close_task = asyncio.create_task(handler.close())
    await asyncio.sleep(0)

    assert close_task.done() is False
    assert handler._file_storage_root_fd_closed is False
    release_stage.set()

    with pytest.raises(asyncio.CancelledError):
        await asyncio.wait_for(chunk_task, timeout=2)
    await asyncio.wait_for(close_task, timeout=2)
    await handler.close()

    assert staged_descriptor is not None
    with pytest.raises(OSError):
        os.fstat(staged_descriptor)
    assert handler._transfer_stages == {}
    assert handler._owned_transfer_files == set()
    assert _staging_files(tmp_path) == []
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []
    assert handler._file_storage_root_fd_closed is True
    assert connection.close_calls == 1


@pytest.mark.asyncio
async def test_final_chunk_cannot_publish_after_close_begins(tmp_path, monkeypatch):
    connection = QueueConnection()
    handler = Handler(connection, file_storage_dir=tmp_path)
    binding = _installation_binding()
    file_key = f"ft1_{'f' * 64}.bin"
    await _write_chunk(
        handler,
        file_key,
        b"first-",
        binding=binding,
        index=0,
        amount=2,
    )
    final_paused = threading.Event()
    release_final = threading.Event()

    def pause_final_before_write(event, **details):
        if event != "before_staging_write":
            return
        final_paused.set()
        assert release_final.wait(timeout=2)

    monkeypatch.setattr(handler, "_transfer_race_hook", pause_final_before_write)

    async def run_in_thread(fn, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: fn(*args))

    monkeypatch.setattr(handler_module.asyncio, "to_thread", run_in_thread)
    final_chunk = asyncio.create_task(
        _write_chunk(
            handler,
            file_key,
            b"second",
            binding=binding,
            index=1,
            amount=2,
        )
    )
    assert await asyncio.to_thread(final_paused.wait, 1)

    close_task = asyncio.create_task(handler.close())
    await asyncio.sleep(0)
    assert handler._file_transfer_closing is True
    assert close_task.done() is False
    assert handler._file_storage_root_fd_closed is False
    release_final.set()

    with pytest.raises(ConnectionClosedError):
        await asyncio.wait_for(final_chunk, timeout=2)
    await asyncio.wait_for(close_task, timeout=2)
    await handler.close()

    namespace = tmp_path / handler_module._transfer_namespace(binding)
    assert not (namespace / file_key).exists()
    assert handler._transfer_stages == {}
    assert handler._owned_transfer_files == set()
    assert handler._owned_transfer_records == set()
    assert _staging_files(tmp_path) == []
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []
    assert handler._file_storage_root_fd_closed is True
    assert connection.close_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("first_close", ["local", "disconnect"])
async def test_close_during_stage_creation_rejects_chunk_without_orphan(
    tmp_path,
    monkeypatch,
    first_close,
):
    connection = QueueConnection()
    handler = Handler(connection, file_storage_dir=tmp_path)
    stage_created = threading.Event()
    release_stage = threading.Event()
    staged_descriptor = None

    def pause_after_staging_create(event, **details):
        nonlocal staged_descriptor
        if event != "after_staging_create":
            return
        staged_descriptor = details["descriptor"]
        stage_created.set()
        assert release_stage.wait(timeout=2)

    monkeypatch.setattr(handler, "_transfer_race_hook", pause_after_staging_create)

    async def run_in_thread(fn, *args):
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, lambda: fn(*args))

    monkeypatch.setattr(handler_module.asyncio, "to_thread", run_in_thread)
    run_task = None
    if first_close == "disconnect":
        run_task = asyncio.create_task(handler.run())

    chunk_task = asyncio.create_task(
        _write_chunk(handler, f"ft1_{'d' * 64}.bin", b"raced-stage")
    )
    assert await asyncio.to_thread(stage_created.wait, 1)

    if first_close == "local":
        first_close_task = asyncio.create_task(handler.close())
    else:
        await connection.incoming.put(ConnectionClosedError("peer disconnected"))
        assert run_task is not None
        first_close_task = run_task
    second_close_task = asyncio.create_task(handler.close())
    await asyncio.sleep(0)
    release_stage.set()

    with pytest.raises(ConnectionClosedError):
        await asyncio.wait_for(chunk_task, timeout=2)
    await asyncio.wait_for(
        asyncio.gather(first_close_task, second_close_task),
        timeout=2,
    )
    await handler.close()

    assert staged_descriptor is not None
    with pytest.raises(OSError):
        os.fstat(staged_descriptor)
    assert handler._transfer_stages == {}
    assert handler._owned_transfer_files == set()
    assert _staging_files(tmp_path) == []
    assert handler._file_storage_root_fd_closed is True
    assert connection.close_calls == (1 if first_close == "local" else 0)


@pytest.mark.asyncio
async def test_concurrent_closes_cleanup_active_completed_transfers(tmp_path):
    connection = QueueConnection()
    handler = Handler(connection, file_storage_dir=tmp_path)
    binding = _installation_binding()
    file_keys = [f"ft1_{index:064x}.bin" for index in range(1, 4)]
    for file_key in file_keys:
        await _write_chunk(handler, file_key, file_key.encode(), binding=binding)

    await asyncio.wait_for(
        asyncio.gather(*(handler.close() for _ in range(8))),
        timeout=2,
    )
    await handler.close()

    assert connection.close_calls == 1
    assert handler._owned_transfer_files == set()
    assert handler._owned_transfer_records == set()
    assert handler._transfer_stages == {}
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []
    assert handler._file_storage_root_fd_closed is True


@pytest.mark.asyncio
async def test_concurrent_closes_wait_for_primary_cleanup_retry(tmp_path, monkeypatch):
    connection = QueueConnection()
    handler = Handler(connection, file_storage_dir=tmp_path)
    file_key = f"ft1_{'e' * 64}.bin"
    await _write_chunk(handler, file_key, b"completed")
    cleanup_started = asyncio.Event()
    release_cleanup = asyncio.Event()
    real_cleanup = handler._cleanup_owned_transfers_locked
    cleanup_calls = 0

    async def paused_cleanup(*, close_root=False):
        nonlocal cleanup_calls
        cleanup_calls += 1
        if cleanup_calls == 1:
            cleanup_started.set()
            await release_cleanup.wait()
        await real_cleanup(close_root=close_root)

    monkeypatch.setattr(handler, "_cleanup_owned_transfers_locked", paused_cleanup)

    first_close = asyncio.create_task(handler.close())
    await asyncio.wait_for(cleanup_started.wait(), timeout=1)
    repeated_closes = [asyncio.create_task(handler.close()) for _ in range(4)]
    await asyncio.sleep(0)

    assert all(not task.done() for task in repeated_closes)
    release_cleanup.set()
    await asyncio.wait_for(
        asyncio.gather(first_close, *repeated_closes),
        timeout=2,
    )

    assert connection.close_calls == 1
    assert handler._owned_transfer_files == set()
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []
    assert handler._file_storage_root_fd_closed is True


@pytest.mark.asyncio
async def test_close_discards_incomplete_transfer_stage_and_releases_ownership(
    tmp_path,
):
    handler = Handler(QueueConnection(), file_storage_dir=tmp_path)
    binding = _installation_binding()
    file_key = f"ft1_{'8' * 64}.bin"

    await _write_chunk(
        handler,
        file_key,
        b"first",
        binding=binding,
        index=0,
        amount=2,
    )
    stage = handler._transfer_stages[file_key]
    descriptor = stage.descriptor
    assert descriptor is not None
    assert _staging_files(tmp_path)

    await handler.close()

    assert handler._transfer_stages == {}
    assert _staging_files(tmp_path) == []
    with pytest.raises(OSError):
        os.fstat(descriptor)
    assert handler._file_storage_root_fd_closed is True
    with handler_module._locked_transfer(str(tmp_path), file_key) as lock_key:
        assert handler_module._active_transfer_handler(lock_key) is None


@pytest.mark.asyncio
async def test_close_retries_incomplete_stage_unlink_before_closing_root(
    tmp_path,
    monkeypatch,
):
    connection = QueueConnection()
    handler = Handler(connection, file_storage_dir=tmp_path)
    file_key = f"ft1_{'9' * 64}.bin"
    await _write_chunk(handler, file_key, b"first", index=0, amount=2)
    stage = handler._transfer_stages[file_key]
    descriptor = stage.descriptor
    assert descriptor is not None
    real_remove = os.remove
    failed = False

    def fail_stage_unlink_once(path, *args, **kwargs):
        nonlocal failed
        if _transfer_entry_name(path) == stage.temp_name and not failed:
            failed = True
            raise OSError("simulated staging unlink failure")
        return real_remove(path, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "remove", fail_stage_unlink_once)

    await handler.close()

    assert file_key in handler._transfer_stages
    assert _staging_files(tmp_path)
    with pytest.raises(OSError):
        os.fstat(descriptor)
    assert handler._file_storage_root_fd_closed is False
    assert connection.close_calls == 1

    await handler.close()

    assert handler._transfer_stages == {}
    assert _staging_files(tmp_path) == []
    assert handler._file_storage_root_fd_closed is True
    assert connection.close_calls == 1


@pytest.mark.asyncio
async def test_disconnect_and_close_concurrently_discard_incomplete_stage(tmp_path):
    connection = QueueConnection()
    handler = Handler(connection, file_storage_dir=tmp_path)
    file_key = f"ft1_{'6' * 64}.bin"
    await _write_chunk(handler, file_key, b"first", index=0, amount=2)
    descriptor = handler._transfer_stages[file_key].descriptor
    assert descriptor is not None
    run_task = asyncio.create_task(handler.run())

    await connection.incoming.put(ConnectionClosedError("peer disconnected"))
    await asyncio.wait_for(
        asyncio.gather(run_task, handler.close()),
        timeout=2,
    )

    assert handler._transfer_stages == {}
    assert _staging_files(tmp_path) == []
    with pytest.raises(OSError):
        os.fstat(descriptor)
    assert handler._file_storage_root_fd_closed is True


@pytest.mark.asyncio
async def test_short_writes_complete_staging_payload_and_owner_sidecar(
    tmp_path,
    monkeypatch,
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    binding = _installation_binding()
    file_key = f"ft1_{'4' * 64}.bin"
    real_write = os.write
    short_writes = 0

    def write_short(fd, data):
        nonlocal short_writes
        if len(data) > 1:
            short_writes += 1
            return real_write(fd, data[: max(1, len(data) // 2)])
        return real_write(fd, data)

    monkeypatch.setattr(handler_module.os, "write", write_short)

    await _write_chunk(handler, file_key, b"short-write-payload", binding=binding)

    assert short_writes >= 2
    assert (
        await handler.read_local_file(file_key, action_context=binding)
        == b"short-write-payload"
    )
    await handler.close()
    assert list(tmp_path.rglob("*.tmp")) == []
    assert list((tmp_path / ".transfer-owners").iterdir()) == []


@pytest.mark.asyncio
@pytest.mark.parametrize("zero_call", [1, 2], ids=["staging", "owner-sidecar"])
async def test_zero_progress_write_rolls_back_and_allows_retry(
    tmp_path,
    monkeypatch,
    zero_call,
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    binding = _installation_binding()
    file_key = f"ft1_{zero_call:064x}.bin"
    real_write = os.write
    calls = 0

    def write_zero_once(fd, data):
        nonlocal calls
        calls += 1
        if calls == zero_call:
            return 0
        return real_write(fd, data)

    monkeypatch.setattr(handler_module.os, "write", write_zero_once)

    with pytest.raises(OSError, match="made no progress"):
        await _write_chunk(handler, file_key, b"first", binding=binding)

    assert handler._transfer_stages == {}
    assert _staging_files(tmp_path) == []
    assert handler._owned_transfer_files == set()

    monkeypatch.setattr(handler_module.os, "write", real_write)
    await _write_chunk(handler, file_key, b"second", binding=binding)
    assert await handler.read_local_file(file_key, action_context=binding) == b"second"
    await handler.close()
    assert list(tmp_path.rglob("*.tmp")) == []
    assert list((tmp_path / ".transfer-owners").iterdir()) == []


@pytest.mark.asyncio
@requires_symlinks
async def test_transfer_rejects_symlinked_namespace_without_overwriting_sibling(
    tmp_path,
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    binding_a = _installation_binding("a")
    binding_b = _installation_binding("b")
    file_key = f"ft1_{'5' * 64}.bin"
    await _write_chunk(handler, file_key, b"B-secret", binding=binding_b)

    namespace_a = os.path.dirname(
        handler_module._file_storage_path(file_key, tmp_path, action_context=binding_a)
    )
    namespace_b = os.path.dirname(
        handler_module._file_storage_path(file_key, tmp_path, action_context=binding_b)
    )
    os.symlink(namespace_b, namespace_a)

    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await _write_chunk(handler, file_key, b"A-overwrite", binding=binding_a)
    assert (
        await handler.read_local_file(file_key, action_context=binding_b) == b"B-secret"
    )


@pytest.mark.asyncio
@requires_symlinks
async def test_transfer_rejects_symlinked_file_for_write_read_and_delete(tmp_path):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    victim = tmp_path / "victim.bin"
    victim.write_bytes(b"outside")
    namespace = tmp_path / "unbound"
    namespace.mkdir()
    file_key = f"ft1_{'6' * 64}.bin"
    await _write_chunk(handler, file_key, b"original")
    (namespace / file_key).unlink()
    os.symlink(victim, namespace / file_key)

    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await _write_chunk(handler, file_key, b"overwrite")
    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await handler.read_local_file(file_key)
    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await handler.delete_local_file(file_key)
    assert victim.read_bytes() == b"outside"


@pytest.mark.asyncio
@requires_symlinks
async def test_transfer_rejects_symlinked_owner_directory(tmp_path):
    external = tmp_path / "external-owners"
    external.mkdir()
    os.symlink(external, tmp_path / ".transfer-owners")
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'7' * 64}.bin"

    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await _write_chunk(handler, file_key, b"payload")
    assert list(external.iterdir()) == []


@requires_symlinks
def test_transfer_rejects_symlinked_configured_root_without_touching_target(tmp_path):
    external = tmp_path / "external-root"
    external.mkdir(mode=0o755)
    root = tmp_path / "transfer-root"
    root.symlink_to(external, target_is_directory=True)
    original_mode = stat.S_IMODE(external.stat().st_mode)

    with pytest.raises(ValueError, match="Invalid file transfer root"):
        Handler(ProtocolConnection(), file_storage_dir=root)

    assert stat.S_IMODE(external.stat().st_mode) == original_mode
    assert list(external.iterdir()) == []


@requires_descriptor_root
@requires_symlinks
def test_transfer_rejects_configured_root_replaced_by_symlink_during_init(
    tmp_path, monkeypatch
):
    external = tmp_path / "external-root"
    external.mkdir(mode=0o755)
    root = tmp_path / "transfer-root"
    real_open = os.open
    replaced = False

    def replace_before_root_open(path, flags, *args, **kwargs):
        nonlocal replaced
        if path == root.name and kwargs.get("dir_fd") is not None and not replaced:
            replaced = True
            root.rmdir()
            root.symlink_to(external, target_is_directory=True)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "open", replace_before_root_open)

    with pytest.raises(ValueError, match="Invalid file transfer root"):
        Handler(ProtocolConnection(), file_storage_dir=root)

    assert replaced is True
    assert stat.S_IMODE(external.stat().st_mode) == 0o755
    assert list(external.iterdir()) == []


@pytest.mark.asyncio
async def test_transfer_rejects_configured_root_replaced_after_init(tmp_path):
    root = tmp_path / "transfer-root"
    handler = Handler(ProtocolConnection(), file_storage_dir=root)
    bound_root = tmp_path / "bound-root"
    root.rename(bound_root)
    root.mkdir()

    with pytest.raises(ValueError, match="Invalid file transfer root"):
        await _write_chunk(handler, "root-drift.bin", b"payload")

    assert list(root.iterdir()) == []
    assert list(bound_root.iterdir()) == []
    await handler.close()


def test_prepared_transfer_root_matches_platform_capability(tmp_path):
    """The bound root is a descriptor on POSIX and a path handle elsewhere.

    Platforms without ``dir_fd`` keep the namespace containment checks but
    cannot bind an inode, so the handle type must track the platform rather
    than silently degrading a POSIX deployment.
    """

    root = tmp_path / "transfer-root"
    lexical_root, handle, root_stat = handler_module._prepare_transfer_root(str(root))

    assert lexical_root == os.path.abspath(root)
    assert stat.S_ISDIR(root_stat.st_mode)
    if handler_module._DIRECTORY_HANDLE_SUPPORTED:
        assert isinstance(handle, int)
        assert os.fstat(handle).st_ino == root_stat.st_ino
        os.close(handle)
        return

    assert isinstance(handle, handler_module._PathDirectoryHandle)
    assert handle.path == os.path.realpath(root)
    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        handler_module._join_directory_entry(handle, "..")
    handler_module._close_directory(handle)


@requires_descriptor_root
@requires_unreadable_directories
@pytest.mark.asyncio
async def test_transfer_root_binds_under_unreadable_ancestor(tmp_path):
    """A deployment may deny reading the ancestors it still lets us traverse.

    fnOS applications reach their own ``data`` directory while a read-only open
    of the volume above it is refused.  The root must bind and stay usable
    instead of rejecting every file transfer.
    """

    volume = tmp_path / "vol2"
    root = volume / "@appshare" / "langbot" / "data" / "lbp"
    root.mkdir(parents=True)
    os.chmod(volume, 0o111)
    try:
        handler = Handler(ProtocolConnection(), file_storage_dir=root)
        try:
            file_key = f"ft1_{'8' * 64}.bin"
            await _write_chunk(handler, file_key, b"unreadable-ancestor")
            assert await handler.read_local_file(file_key) == b"unreadable-ancestor"
        finally:
            await handler.close()
    finally:
        os.chmod(volume, 0o755)

    assert stat.S_IMODE(root.stat().st_mode) == 0o700


@requires_descriptor_root
@pytest.mark.asyncio
async def test_transfer_root_binds_below_sandboxed_ancestors(tmp_path, monkeypatch):
    """A profile that grants only the application subtree still binds the root.

    Confinement profiles (fnOS app sandboxes, hardened containers) deny the
    walk above the granted subtree even though the subtree itself is reachable
    by absolute path, so binding has to start at the deepest directory the
    profile still allows without dropping the checks below that point.
    """

    granted = tmp_path / "vol2" / "@appshare" / "langbot" / "data" / "lbp"
    granted.mkdir(parents=True)
    _confine_absolute_opens(monkeypatch, granted)

    with pytest.raises(PermissionError):
        os.open(tmp_path, os.O_RDONLY)

    handler = Handler(ProtocolConnection(), file_storage_dir=granted)
    try:
        file_key = f"ft1_{'9' * 64}.bin"
        await _write_chunk(handler, file_key, b"sandboxed-ancestors")
        assert await handler.read_local_file(file_key) == b"sandboxed-ancestors"
    finally:
        await handler.close()


@requires_descriptor_root
@pytest.mark.asyncio
async def test_transfer_root_creates_missing_root_below_sandboxed_ancestors(
    tmp_path, monkeypatch
):
    """A missing storage root is still created inside the granted subtree."""

    granted = tmp_path / "vol2" / "@appshare" / "langbot" / "data"
    granted.mkdir(parents=True)
    root = granted / "lbp"
    _confine_absolute_opens(monkeypatch, granted)

    handler = Handler(ProtocolConnection(), file_storage_dir=root)
    try:
        file_key = f"ft2_{'9' * 64}.bin"
        await _write_chunk(handler, file_key, b"created-in-sandbox")
        assert await handler.read_local_file(file_key) == b"created-in-sandbox"
    finally:
        await handler.close()

    assert stat.S_IMODE(root.stat().st_mode) == 0o700


@requires_descriptor_root
@requires_symlinks
def test_transfer_root_rejects_symlinked_ancestor_under_sandbox(tmp_path, monkeypatch):
    """The re-anchored walk still refuses the ancestors it can inspect."""

    external = tmp_path / "external"
    (external / "lbp").mkdir(parents=True)
    volume = tmp_path / "volume"
    volume.symlink_to(external, target_is_directory=True)
    root = volume / "lbp"
    # A profile grants the resolved subtree, exactly like a Landlock rule.
    _confine_absolute_opens(monkeypatch, external / "lbp")

    with pytest.raises(ValueError, match="Invalid file transfer root"):
        handler_module._prepare_transfer_root(str(root))

    assert list((external / "lbp").iterdir()) == []


@requires_descriptor_root
def test_transfer_root_rejects_when_no_ancestor_is_reachable(tmp_path, monkeypatch):
    """A profile that grants nothing reachable still rejects the root."""

    root = tmp_path / "vol2" / "lbp"
    root.mkdir(parents=True)
    _confine_absolute_opens(monkeypatch, tmp_path / "elsewhere")

    with pytest.raises(ValueError, match="Invalid file transfer root"):
        handler_module._prepare_transfer_root(str(root))


@requires_descriptor_root
def test_symlink_inspection_skips_ancestors_the_profile_denies(tmp_path, monkeypatch):
    """An ancestor nobody can inspect cannot be proven to be a symlink.

    The re-anchored walk verifies every ancestor it can see and only skips
    the ones the profile itself refuses to describe.
    """

    components = [
        part for part in str(tmp_path / "outer" / "lbp").split(os.sep) if part
    ]
    real_lstat = os.lstat

    def deny_outer(path, *args, **kwargs):
        if os.fspath(path) == str(tmp_path / "outer"):
            raise PermissionError(
                errno.EACCES, "denied by confinement profile", os.fspath(path)
            )
        return real_lstat(path, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "lstat", deny_outer)

    handler_module._reject_symlinked_root_prefixes(components, len(components))


@requires_descriptor_root
@requires_path_only_open
@pytest.mark.asyncio
async def test_transfer_root_walks_when_filesystem_root_is_unreadable(
    tmp_path, monkeypatch
):
    """A sandbox that denies the whole chain is walked path-only from `/`.

    Landlock-style profiles refuse ``/`` and every ancestor while granting the
    application subtree, so the walk has to start path-only too instead of
    giving up on the first component.
    """

    root = tmp_path / "vol2" / "@appshare" / "langbot" / "data" / "lbp"
    root.mkdir(parents=True)
    real_open = os.open
    denied: list[str] = []

    def deny_read_only_system_root(path, flags, *args, **kwargs):
        target = os.fspath(path)
        if (
            target == os.sep
            and not flags & os.O_PATH
            and flags & os.O_ACCMODE == os.O_RDONLY
        ):
            denied.append(target)
            raise PermissionError(errno.EACCES, "denied by confinement profile", target)
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "open", deny_read_only_system_root)

    handler = Handler(ProtocolConnection(), file_storage_dir=root)
    try:
        file_key = f"ft3_{'7' * 64}.bin"
        await _write_chunk(handler, file_key, b"path-only-walk")
        assert await handler.read_local_file(file_key) == b"path-only-walk"
    finally:
        await handler.close()

    assert denied


@requires_descriptor_root
@requires_path_only_open
def test_transfer_root_path_stat_falls_back_to_path_only_open(tmp_path, monkeypatch):
    """The drift check re-opens the root by path when ``stat`` is refused.

    Denying the ancestors also denies ``stat`` on the full path, and a
    path-only open answers the same identity question without following a
    symlink.
    """

    root = tmp_path / "transfer-root"
    root.mkdir()
    expected = os.stat(root)
    real_stat = os.stat
    denied: list[str] = []

    def deny_root_path(path, *args, **kwargs):
        if os.fspath(path) == str(root):
            denied.append(os.fspath(path))
            raise PermissionError(
                errno.EACCES, "denied by confinement profile", os.fspath(path)
            )
        return real_stat(path, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "stat", deny_root_path)

    root_stat = handler_module._transfer_root_path_stat(str(root))

    assert denied
    assert stat.S_ISDIR(root_stat.st_mode)
    assert (root_stat.st_dev, root_stat.st_ino) == (expected.st_dev, expected.st_ino)

    # Anything the path-only retry cannot fix still fails: a vanished path is
    # not a permission problem.
    with pytest.raises(OSError):
        handler_module._transfer_root_path_stat(str(root / "missing"))


@requires_descriptor_root
@requires_symlinks
def test_transfer_root_still_rejects_symlinked_ancestor(tmp_path):
    """Relaxing the ancestor open must not relax the symlink refusal."""

    external = tmp_path / "external"
    (external / "data" / "lbp").mkdir(parents=True)
    link = tmp_path / "volume"
    link.symlink_to(external, target_is_directory=True)

    with pytest.raises(ValueError, match="Invalid file transfer root"):
        handler_module._prepare_transfer_root(str(link / "data" / "lbp"))

    assert list((external / "data" / "lbp").iterdir()) == []


@requires_descriptor_root
def test_transfer_root_rejects_non_directory_ancestor(tmp_path):
    """A component that is a file is refused, not created around."""

    blocker = tmp_path / "data"
    blocker.write_bytes(b"not a directory")

    with pytest.raises(ValueError, match="Invalid file transfer root"):
        handler_module._prepare_transfer_root(str(blocker / "lbp"))


@requires_descriptor_root
@requires_unreadable_directories
def test_transfer_root_rejects_unreadable_non_directory_ancestor(tmp_path):
    """The path-only retry still refuses something that is not a directory."""

    blocker = tmp_path / "data"
    blocker.write_bytes(b"not a directory")
    os.chmod(blocker, 0o000)
    try:
        with pytest.raises(ValueError, match="Invalid file transfer root"):
            handler_module._prepare_transfer_root(str(blocker / "lbp"))
    finally:
        os.chmod(blocker, 0o644)


def test_transfer_root_rejects_filesystem_root():
    """The storage root may not be the filesystem root itself."""

    with pytest.raises(ValueError, match="Invalid file transfer root"):
        handler_module._prepare_transfer_root(os.sep)


@requires_descriptor_root
@requires_symlinks
@requires_unreadable_directories
def test_transfer_root_rejects_symlinked_ancestor_below_unreadable_parent(
    tmp_path,
):
    """The path-only ancestor open keeps refusing links, not just the read open."""

    volume = tmp_path / "vol2"
    volume.mkdir()
    external = tmp_path / "external"
    (external / "lbp").mkdir(parents=True)
    (volume / "data").symlink_to(external, target_is_directory=True)
    os.chmod(volume, 0o111)
    try:
        with pytest.raises(ValueError, match="Invalid file transfer root"):
            handler_module._prepare_transfer_root(str(volume / "data" / "lbp"))
    finally:
        os.chmod(volume, 0o755)

    assert list((external / "lbp").iterdir()) == []


@pytest.mark.asyncio
@requires_descriptor_root
async def test_root_swap_after_validation_keeps_write_anchored_to_bound_inode(
    tmp_path,
    monkeypatch,
):
    root = tmp_path / "transfer-root"
    handler = Handler(ProtocolConnection(), file_storage_dir=root)
    displaced = tmp_path / "bound-root"
    swapped = False

    def swap_after_validation(event, **_details):
        nonlocal swapped
        if event == "after_root_validation" and not swapped:
            swapped = True
            root.rename(displaced)
            root.mkdir()

    monkeypatch.setattr(handler, "_transfer_race_hook", swap_after_validation)

    await _write_chunk(handler, "anchored.bin", b"payload")

    assert swapped is True
    assert (displaced / "unbound" / "anchored.bin").read_bytes() == b"payload"
    assert list(root.iterdir()) == []


@pytest.mark.asyncio
async def test_repeated_close_keeps_bound_root_open_until_cleanup_succeeds(
    tmp_path,
    monkeypatch,
):
    connection = QueueConnection()
    handler = Handler(connection, file_storage_dir=tmp_path)
    file_key = f"ft1_{'6' * 64}.bin"
    await _write_chunk(handler, file_key, b"retry-close")
    real_remove = os.remove
    failed = False

    def fail_quarantine_once(path, *args, **kwargs):
        nonlocal failed
        if _transfer_entry_name(path).startswith(".quarantine-") and not failed:
            failed = True
            raise OSError("simulated cleanup failure")
        return real_remove(path, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "remove", fail_quarantine_once)

    await handler.close()
    assert handler._file_storage_root_fd_closed is False
    assert handler._owned_transfer_files

    await handler.close()
    assert handler._file_storage_root_fd_closed is True
    assert handler._owned_transfer_files == set()
    assert connection.close_calls == 1


@pytest.mark.asyncio
async def test_handlers_sharing_root_cannot_interleave_capability_chunks(tmp_path):
    binding = _installation_binding()
    first = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    second = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'8' * 64}.bin"

    await _write_chunk(first, file_key, b"first-", binding=binding, index=0, amount=2)
    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await _write_chunk(
            second, file_key, b"intruder", binding=binding, index=1, amount=2
        )
    await _write_chunk(first, file_key, b"second", binding=binding, index=1, amount=2)

    assert await first.read_local_file(file_key) == b"first-second"


@pytest.mark.asyncio
async def test_stale_handler_cleanup_cannot_delete_reclaimed_capability(tmp_path):
    binding = _installation_binding()
    stale = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    current = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'9' * 64}.bin"
    await _write_chunk(stale, file_key, b"old", binding=binding)

    await current.delete_local_file(file_key, action_context=binding)
    await _write_chunk(current, file_key, b"new", binding=binding)
    # Simulate lifecycle loss of the in-memory active-owner hint. Durable claim
    # identity must still prevent stale cleanup after delete/reclaim.
    handler_module._set_active_transfer_handler(
        (current.file_storage_dir, file_key), None
    )
    await stale._cleanup_owned_transfers()

    assert await current.read_local_file(file_key, action_context=binding) == b"new"


@pytest.mark.asyncio
async def test_owner_checked_delete_is_atomic_with_same_process_cross_handler_reclaim(
    tmp_path,
    monkeypatch,
):
    binding = _installation_binding()
    # The serialization contract is intentionally process-local: these distinct
    # handlers share the runtime interpreter and transfer-root lock registry.
    deleting = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    reclaiming = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'b' * 64}.bin"
    await _write_chunk(deleting, file_key, b"old", binding=binding)

    owner_checked = threading.Event()
    continue_delete = threading.Event()
    reclaim_started = threading.Event()
    real_access_check = deleting._context_can_access_transfer
    real_reclaim_delete = reclaiming._delete_transfer_sync
    paused = False

    def pause_inside_locked_delete(effective_context, stored_context):
        nonlocal paused
        allowed = real_access_check(effective_context, stored_context)
        if not paused:
            paused = True
            owner_checked.set()
            assert continue_delete.wait(timeout=2)
        return allowed

    def note_reclaim_started(*args):
        reclaim_started.set()
        return real_reclaim_delete(*args)

    monkeypatch.setattr(
        deleting, "_context_can_access_transfer", pause_inside_locked_delete
    )
    monkeypatch.setattr(reclaiming, "_delete_transfer_sync", note_reclaim_started)

    delete_task = asyncio.create_task(
        deleting.delete_local_file(file_key, action_context=binding)
    )
    assert await asyncio.to_thread(owner_checked.wait, 2)

    async def reclaim() -> None:
        await reclaiming.delete_local_file(file_key, action_context=binding)
        await _write_chunk(reclaiming, file_key, b"new", binding=binding)

    reclaim_task = asyncio.create_task(reclaim())
    assert await asyncio.to_thread(reclaim_started.wait, 2)
    assert not reclaim_task.done()

    continue_delete.set()
    await asyncio.wait_for(asyncio.gather(delete_task, reclaim_task), timeout=2)

    assert await reclaiming.read_local_file(file_key, action_context=binding) == b"new"


@pytest.mark.asyncio
async def test_cleanup_retains_owner_record_until_file_delete_retry_succeeds(
    tmp_path,
    monkeypatch,
):
    binding = _installation_binding()
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'a' * 64}.bin"
    await _write_chunk(handler, file_key, b"retry", binding=binding)
    real_remove = os.remove
    failed = False

    def fail_file_once(path, *args, **kwargs):
        nonlocal failed
        if _transfer_entry_name(path).startswith(".quarantine-") and not failed:
            failed = True
            raise OSError("simulated file delete failure")
        return real_remove(path, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "remove", fail_file_once)
    await handler._cleanup_owned_transfers()

    owner_records = list((tmp_path / ".transfer-owners").iterdir())
    assert len(owner_records) == 1
    assert await handler.read_local_file(file_key, action_context=binding) == b"retry"

    await handler._cleanup_owned_transfers()
    assert not owner_records[0].exists()
    with pytest.raises(FileNotFoundError):
        await handler.read_local_file(file_key, action_context=binding)


@pytest.mark.asyncio
async def test_cleanup_retries_owner_delete_after_data_file_is_removed(
    tmp_path,
    monkeypatch,
):
    binding = _installation_binding()
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'e' * 64}.bin"
    await _write_chunk(handler, file_key, b"retry-owner", binding=binding)
    real_remove = os.remove
    failed = False
    quarantine_removes = 0

    def fail_owner_once(path, *args, **kwargs):
        nonlocal failed, quarantine_removes
        if _transfer_entry_name(path).startswith(".quarantine-"):
            quarantine_removes += 1
        if quarantine_removes == 2 and not failed:
            failed = True
            raise OSError("simulated owner delete failure")
        return real_remove(path, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "remove", fail_owner_once)
    await handler._cleanup_owned_transfers()

    owner_records = list((tmp_path / ".transfer-owners").iterdir())
    assert len(owner_records) == 1
    assert len(handler._owned_transfer_files) == 1

    await handler._cleanup_owned_transfers()
    assert not owner_records[0].exists()
    assert handler._owned_transfer_files == set()


@pytest.mark.asyncio
@pytest.mark.parametrize("failed_name", ["payload", "owner"])
async def test_explicit_delete_failure_raises_and_retains_capacity_for_retry(
    tmp_path,
    monkeypatch,
    failed_name,
):
    monkeypatch.setattr(handler_module, "MAX_ACTIVE_FILE_TRANSFERS", 1)
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'f' * 64}.bin"
    next_key = f"ft1_{'0' * 64}.bin"
    await _write_chunk(handler, file_key, b"retry-delete")
    owner_record = next((tmp_path / ".transfer-owners").iterdir())
    real_remove = os.remove
    failed = False
    quarantine_removes = 0

    def fail_once(path, *args, **kwargs):
        nonlocal failed, quarantine_removes
        if _transfer_entry_name(path).startswith(".quarantine-"):
            quarantine_removes += 1
        is_target = (
            quarantine_removes == 1
            if failed_name == "payload"
            else quarantine_removes == 2
        )
        if is_target and not failed:
            failed = True
            raise OSError(f"simulated {failed_name} delete failure")
        return real_remove(path, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "remove", fail_once)

    with pytest.raises(OSError, match=f"simulated {failed_name} delete failure"):
        await handler.delete_local_file(file_key)

    assert owner_record.exists()
    assert len(handler._owned_transfer_files) == 1
    with pytest.raises(ValueError, match="transfer capacity"):
        await _write_chunk(handler, next_key, b"still-full")

    await handler.delete_local_file(file_key)
    assert not owner_record.exists()
    assert handler._owned_transfer_files == set()
    await _write_chunk(handler, next_key, b"capacity-released")


@pytest.mark.asyncio
async def test_close_retries_failed_transfer_cleanup_without_reclosing_connection(
    tmp_path,
    monkeypatch,
):
    connection = QueueConnection()
    handler = Handler(connection, file_storage_dir=tmp_path)
    file_key = f"ft1_{'1' * 64}.bin"
    await _write_chunk(handler, file_key, b"retry-close")
    payload = tmp_path / "unbound" / file_key
    owner_record = next((tmp_path / ".transfer-owners").iterdir())
    real_remove = os.remove
    failed = False

    def fail_payload_once(path, *args, **kwargs):
        nonlocal failed
        if _transfer_entry_name(path).startswith(".quarantine-") and not failed:
            failed = True
            raise OSError("simulated close cleanup failure")
        return real_remove(path, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "remove", fail_payload_once)

    await handler.close()
    assert payload.exists()
    assert owner_record.exists()
    assert len(handler._owned_transfer_files) == 1
    assert connection.close_calls == 1

    await handler.close()
    assert not payload.exists()
    assert not owner_record.exists()
    assert handler._owned_transfer_files == set()
    assert connection.close_calls == 1


@pytest.mark.asyncio
@pytest.mark.parametrize("failure_point", ["serialize", "fsync"])
async def test_failed_new_owner_record_is_removed_so_same_capability_can_retry(
    tmp_path,
    monkeypatch,
    failure_point,
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'2' * 64}.bin"

    if failure_point == "serialize":
        real_serialize = handler._serialize_transfer_record
        failed = False

        def fail_serialize_once(*args):
            nonlocal failed
            if not failed:
                failed = True
                raise RuntimeError("simulated owner serialization failure")
            return real_serialize(*args)

        monkeypatch.setattr(handler, "_serialize_transfer_record", fail_serialize_once)
    else:
        real_fsync = os.fsync
        failed = False

        def fail_fsync_once(fd):
            nonlocal failed
            if not failed:
                failed = True
                raise OSError("simulated owner fsync failure")
            return real_fsync(fd)

        monkeypatch.setattr(handler_module.os, "fsync", fail_fsync_once)

    with pytest.raises((OSError, RuntimeError), match="simulated owner"):
        await _write_chunk(handler, file_key, b"first")

    owner_dir = tmp_path / ".transfer-owners"
    assert not owner_dir.exists() or list(owner_dir.iterdir()) == []
    assert handler._owned_transfer_files == set()
    assert handler._owned_transfer_claims == {}

    await _write_chunk(handler, file_key, b"second")
    assert await handler.read_local_file(file_key) == b"second"


@pytest.mark.asyncio
async def test_rejected_capability_keys_do_not_leak_owner_sidecars(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(handler_module, "MAX_ACTIVE_FILE_TRANSFERS", 1)
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    await _write_chunk(handler, f"ft1_{0:064x}.bin", b"accepted")

    for number in range(1, 33):
        with pytest.raises(ValueError, match="transfer capacity"):
            await _write_chunk(handler, f"ft1_{number:064x}.bin", b"rejected")

    assert len(list((tmp_path / ".transfer-owners").iterdir())) == 1


@pytest.mark.asyncio
async def test_failed_first_chunk_rolls_back_capacity_reservation_and_owner_claim(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(handler_module, "MAX_ACTIVE_FILE_TRANSFERS", 1)
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    failed_key = f"ft1_{'c' * 64}.bin"
    accepted_key = f"ft1_{'d' * 64}.bin"
    real_open = os.open
    fail_data_open = True

    def fail_first_data_open(path, flags, *args, **kwargs):
        nonlocal fail_data_open
        if os.path.basename(os.fspath(path)) == failed_key and fail_data_open:
            fail_data_open = False
            raise OSError("simulated data-file open failure")
        return real_open(path, flags, *args, **kwargs)

    monkeypatch.setattr(handler_module.os, "open", fail_first_data_open)
    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await _write_chunk(handler, failed_key, b"rejected")

    assert handler._owned_transfer_files == set()
    assert handler._owned_transfer_contexts == {}
    assert handler._owned_transfer_claims == {}
    owner_dir = tmp_path / ".transfer-owners"
    assert not owner_dir.exists() or list(owner_dir.iterdir()) == []

    await _write_chunk(handler, accepted_key, b"accepted")
    assert await handler.read_local_file(accepted_key) == b"accepted"


@pytest.mark.asyncio
async def test_payload_inode_swap_during_delete_never_unlinks_replacement(
    tmp_path,
    monkeypatch,
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'7' * 64}.bin"
    await _write_chunk(handler, file_key, b"expected")
    payload = tmp_path / "unbound" / file_key
    displaced = tmp_path / "unbound" / "displaced-payload"
    swapped = False

    def swap_payload(event, **details):
        nonlocal swapped
        if event == "before_quarantine_rename" and details["role"] == "payload":
            swapped = True
            payload.rename(displaced)
            payload.write_bytes(b"replacement")

    monkeypatch.setattr(handler, "_transfer_race_hook", swap_payload)

    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await handler.delete_local_file(file_key)

    assert swapped is True
    assert any(
        path.read_bytes() == b"replacement"
        for path in (tmp_path / "unbound").iterdir()
        if path.is_file()
    )
    assert displaced.read_bytes() == b"expected"


@pytest.mark.asyncio
async def test_owner_inode_swap_during_delete_never_unlinks_replacement(
    tmp_path,
    monkeypatch,
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'8' * 64}.bin"
    await _write_chunk(handler, file_key, b"expected")
    owner = next((tmp_path / ".transfer-owners").iterdir())
    displaced = owner.with_name("displaced-owner")
    replacement = b'{"replacement":true}'
    swapped = False

    def swap_owner(event, **details):
        nonlocal swapped
        if event == "before_quarantine_rename" and details["role"] == "owner":
            swapped = True
            owner.rename(displaced)
            owner.write_bytes(replacement)
            owner.chmod(0o600)

    monkeypatch.setattr(handler, "_transfer_race_hook", swap_owner)

    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await handler.delete_local_file(file_key)

    assert swapped is True
    assert any(
        path.read_bytes() == replacement
        for path in (tmp_path / ".transfer-owners").iterdir()
        if path.is_file()
    )
    assert displaced.exists()


@pytest.mark.asyncio
async def test_failed_payload_creation_never_rolls_back_swapped_owner_name(
    tmp_path,
    monkeypatch,
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'9' * 64}.bin"
    replacement = b'{"replacement":true}'
    swapped_owner = None

    def swap_owner_then_fail(event, **_details):
        nonlocal swapped_owner
        if event != "before_owner_link":
            return
        owner = next((tmp_path / ".transfer-owners").glob(".owner-*.tmp"))
        swapped_owner = owner.with_name("displaced-owner")
        owner.rename(swapped_owner)
        owner.write_bytes(replacement)
        owner.chmod(0o600)
        raise OSError("simulated payload creation failure")

    monkeypatch.setattr(handler, "_transfer_race_hook", swap_owner_then_fail)

    with pytest.raises(OSError, match="simulated payload creation failure"):
        await _write_chunk(handler, file_key, b"payload")

    assert swapped_owner is not None and swapped_owner.exists()
    owner_files = list((tmp_path / ".transfer-owners").iterdir())
    assert all(not path.name.endswith(".json") for path in owner_files)
    assert swapped_owner.read_bytes() != replacement
    assert not any(path.read_bytes() == replacement for path in owner_files)


@pytest.mark.asyncio
async def test_canonical_replacement_immediately_before_write_is_not_modified(
    tmp_path, monkeypatch
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'a' * 64}.bin"
    payload = tmp_path / "unbound" / file_key
    replaced = False

    def install_replacement(event, **_details):
        nonlocal replaced
        if event == "before_staging_write" and not replaced:
            replaced = True
            payload.write_bytes(b"replacement")

    monkeypatch.setattr(handler, "_transfer_race_hook", install_replacement)

    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await _write_chunk(handler, file_key, b"incoming")

    assert replaced is True
    assert payload.read_bytes() == b"replacement"
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == [payload]


@pytest.mark.asyncio
async def test_quarantine_mismatch_retry_retains_replacement_and_owner_authority(
    tmp_path, monkeypatch
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'b' * 64}.bin"
    await _write_chunk(handler, file_key, b"owned")
    payload = tmp_path / "unbound" / file_key
    displaced = payload.with_name("externally-displaced")
    swapped = False

    def swap_payload(event, **details):
        nonlocal swapped
        if event == "before_quarantine_rename" and details["role"] == "payload":
            swapped = True
            payload.rename(displaced)
            payload.write_bytes(b"replacement")

    monkeypatch.setattr(handler, "_transfer_race_hook", swap_payload)

    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await handler.delete_local_file(file_key)
    monkeypatch.setattr(handler, "_transfer_race_hook", lambda *_args, **_kwargs: None)
    with pytest.raises(ValueError, match="Invalid file transfer capability"):
        await handler.delete_local_file(file_key)

    assert displaced.read_bytes() == b"owned"
    assert any(
        path.read_bytes() == b"replacement"
        for path in (tmp_path / "unbound").iterdir()
        if path.is_file()
    )
    assert len(list((tmp_path / ".transfer-owners").glob("*.json"))) == 1


@pytest.mark.asyncio
@requires_descriptor_root
async def test_owner_link_directory_fsync_failure_is_tracked_and_close_cleans(
    tmp_path, monkeypatch
):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path)
    file_key = f"ft1_{'c' * 64}.bin"
    real_fsync = os.fsync
    failed = False

    def fail_after_owner_link(fd):
        nonlocal failed
        owner_files = list((tmp_path / ".transfer-owners").glob("*.json"))
        if owner_files and stat.S_ISDIR(os.fstat(fd).st_mode) and not failed:
            failed = True
            raise OSError("simulated owner directory fsync failure")
        return real_fsync(fd)

    monkeypatch.setattr(handler_module.os, "fsync", fail_after_owner_link)

    with pytest.raises(OSError, match="owner directory fsync"):
        await _write_chunk(handler, file_key, b"published")

    assert failed is True
    assert handler._owned_transfer_files
    assert len(list((tmp_path / ".transfer-owners").glob("*.json"))) == 1
    monkeypatch.setattr(handler_module.os, "fsync", real_fsync)
    await handler.close()
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


@pytest.mark.asyncio
async def test_oversized_first_chunks_leave_no_transfer_artifacts(tmp_path):
    handler = Handler(ProtocolConnection(), file_storage_dir=tmp_path, max_file_bytes=1)

    for number in range(5):
        with pytest.raises(ValueError, match="configured size limit"):
            await _write_chunk(handler, f"ft1_{number:064x}.bin", b"xx")

    assert handler._owned_transfer_files == set()
    assert [path for path in tmp_path.rglob("*") if path.is_file()] == []


@requires_descriptor_root
def test_invalid_max_file_bytes_is_rejected_before_root_fd_is_acquired(
    tmp_path, monkeypatch
):
    prepare_called = False

    def unexpected_prepare(_root):
        nonlocal prepare_called
        prepare_called = True
        raise AssertionError("persistent root must not be acquired")

    monkeypatch.setattr(handler_module, "_prepare_transfer_root", unexpected_prepare)
    before = len(os.listdir("/proc/self/fd"))
    with pytest.raises(ValueError, match="max_file_bytes"):
        Handler(ProtocolConnection(), file_storage_dir=tmp_path, max_file_bytes=0)
    after = len(os.listdir("/proc/self/fd"))

    assert prepare_called is False
    assert after == before


@pytest.mark.asyncio
async def test_file_transfer_io_uses_backpressure_aware_executor(tmp_path, monkeypatch):
    handler = Handler(
        ProtocolConnection(),
        file_storage_dir=tmp_path / "rpc-transfer",
    )
    scopes = []

    async def fake_to_thread(fn, *args, **kwargs):
        scopes.append(current_blocking_work_scope())
        return fn(*args, **kwargs)

    monkeypatch.setattr(handler_module.asyncio, "to_thread", fake_to_thread)
    with blocking_work_scope("workspace-a"):
        await handler.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": "backpressure.bin",
                "chunk_base64": base64.b64encode(b"payload").decode("ascii"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
        assert await handler.read_local_file("backpressure.bin") == b"payload"
        await handler.delete_local_file("backpressure.bin")

    assert scopes == ["workspace-a", "workspace-a", "workspace-a"]


@pytest.mark.asyncio
async def test_file_chunk_action_enforces_aggregate_handler_limit(tmp_path):
    handler = Handler(
        ProtocolConnection(),
        file_storage_dir=tmp_path / "rpc-transfer",
        max_file_bytes=5,
    )
    chunk_handler = handler.actions[CommonAction.FILE_CHUNK.value]
    base = {
        "file_key": "limited.bin",
        "chunk_amount": 2,
    }

    await chunk_handler(
        {
            **base,
            "chunk_base64": base64.b64encode(b"1234").decode("ascii"),
            "chunk_index": 0,
        }
    )
    with pytest.raises(ValueError, match="configured size limit"):
        await chunk_handler(
            {
                **base,
                "chunk_base64": base64.b64encode(b"56").decode("ascii"),
                "chunk_index": 1,
            }
        )

    with pytest.raises(FileNotFoundError):
        await handler.read_local_file("limited.bin")


@pytest.mark.asyncio
async def test_send_file_rejects_oversized_payload_before_hashing(
    tmp_path,
    monkeypatch,
):
    handler = Handler(
        ProtocolConnection(),
        file_storage_dir=tmp_path,
        max_file_bytes=5,
    )
    hash_called = False

    def fail_if_hashed(*args, **kwargs):
        nonlocal hash_called
        hash_called = True
        raise AssertionError("oversized payload must be rejected before hashing")

    monkeypatch.setattr(
        "langbot_plugin.runtime.io.handler.hashlib.sha256",
        fail_if_hashed,
    )

    with pytest.raises(ValueError, match="configured size limit"):
        await handler.send_file(b"123456", "bin")

    assert hash_called is False


@pytest.mark.asyncio
async def test_file_chunk_action_rejects_oversized_chunk_before_decode(
    tmp_path,
    monkeypatch,
):
    handler = Handler(
        ProtocolConnection(),
        file_storage_dir=tmp_path,
        max_file_bytes=FILE_CHUNK_LENGTH * 2,
    )
    decode_called = False

    def fail_if_decoded(*args, **kwargs):
        nonlocal decode_called
        decode_called = True
        raise AssertionError("oversized payload must be rejected before decoding")

    monkeypatch.setattr(
        "langbot_plugin.runtime.io.handler.base64.b64decode",
        fail_if_decoded,
    )

    with pytest.raises(ValueError, match="protocol limit"):
        await handler.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": "oversized.bin",
                "chunk_base64": "A" * ((((FILE_CHUNK_LENGTH + 2) // 3) * 4) + 1),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
    assert not decode_called


@pytest.mark.asyncio
async def test_file_chunk_action_bounds_active_transfers_and_close_cleans_files(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setattr(handler_module, "MAX_ACTIVE_FILE_TRANSFERS", 2)
    handler = Handler(
        ProtocolConnection(),
        file_storage_dir=tmp_path,
        max_file_bytes=1024,
    )
    chunk_handler = handler.actions[CommonAction.FILE_CHUNK.value]

    async def write(file_key: str) -> None:
        await chunk_handler(
            {
                "file_key": file_key,
                "chunk_base64": base64.b64encode(b"x").decode("ascii"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )

    await write("first.bin")
    await write("second.bin")
    with pytest.raises(ValueError, match="transfer capacity"):
        await write("third.bin")

    await handler.delete_local_file("first.bin")
    await write("third.bin")
    await handler.close()

    assert not (tmp_path / "second.bin").exists()
    assert not (tmp_path / "third.bin").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "file_key",
    [
        "../secret.txt",
        "/tmp/secret.txt",
        "nested/secret.txt",
        r"nested\secret.txt",
        "opaque..txt",
        r"C:\secret.txt",
        " surrounded.txt ",
        123,
    ],
)
async def test_file_transfer_rejects_path_syntax(file_key, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    handler = Handler(ProtocolConnection())
    chunk_handler = handler.actions[CommonAction.FILE_CHUNK.value]

    with pytest.raises(ValueError, match="Invalid file transfer key"):
        await chunk_handler(
            {
                "file_key": file_key,
                "chunk_base64": base64.b64encode(b"secret").decode("utf-8"),
                "chunk_index": 0,
                "chunk_amount": 1,
            }
        )
    with pytest.raises(ValueError, match="Invalid file transfer key"):
        await handler.read_local_file(file_key)
    with pytest.raises(ValueError, match="Invalid file transfer key"):
        await handler.delete_local_file(file_key)


@pytest.mark.asyncio
async def test_send_file_rejects_extension_with_path_syntax(monkeypatch):
    handler = Handler(ProtocolConnection())

    with pytest.raises(ValueError, match="Invalid file transfer extension"):
        await handler.send_file(b"payload", "../txt")


@pytest.mark.asyncio
async def test_call_action_generator_wraps_unexpected_error():
    conn = ProtocolConnection()
    handler = Handler(conn)

    captured: dict[str, str] = {}

    async def consume():
        try:
            async for _ in handler.call_action_generator(
                SampleAction.STREAM, {}, timeout=1
            ):
                pass
        except ActionCallError as exc:
            captured["error"] = str(exc)

    task = asyncio.create_task(consume())
    [request] = await conn.sent_messages(1)
    # A malformed queue item (has no `.code`) is wrapped as ActionCallError,
    # mirroring the same guard in call_action.
    await handler.resp_queues[request["seq_id"]].put(object())  # type: ignore[arg-type]

    await task
    assert "AttributeError" in captured["error"]
    assert handler.resp_queues == {}


@pytest.mark.asyncio
async def test_run_dispatches_file_chunk_action_and_writes_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    conn = ProtocolConnection()
    handler = Handler(conn)

    run_task = asyncio.create_task(handler.run())

    payload = b"streamed-through-run"
    file_key = "via-run.bin"
    await conn.send_peer_request(
        CommonAction.FILE_CHUNK.value,
        {
            "file_key": file_key,
            "chunk_base64": base64.b64encode(payload).decode("utf-8"),
            "chunk_index": 0,
            "chunk_amount": 1,
        },
        seq_id=21,
    )
    [response] = await conn.sent_messages(1)
    assert response["seq_id"] == 21
    assert response["code"] == 0

    # The __file_chunk action was dispatched through run() and written to disk.
    assert await handler.read_local_file(file_key) == payload

    await conn.close_peer()
    await run_task


@pytest.mark.asyncio
async def test_run_ignores_malformed_message_without_crashing():
    conn = ProtocolConnection()
    handler = Handler(conn)

    @handler.action(SampleAction.ECHO)
    async def echo(data):
        return ActionResponse.success(data)

    run_task = asyncio.create_task(handler.run())

    # A message with neither "action" nor "code" is silently ignored...
    await conn.incoming.put(json.dumps({"seq_id": 1, "unexpected": "shape"}))

    # ...and the loop keeps serving subsequent requests.
    await conn.send_peer_request("echo", {"alive": True}, seq_id=2)
    [response] = await conn.sent_messages(1)
    assert response["seq_id"] == 2
    assert response["data"] == {"alive": True}

    await conn.close_peer()
    await run_task
