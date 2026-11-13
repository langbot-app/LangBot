"""Exercise Box file transfer through authenticated WebSocket action RPC."""

from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
import datetime as dt
import hashlib
import logging
from types import SimpleNamespace

from aiohttp.test_utils import TestServer
import pytest
import websockets

from langbot_plugin.box.actions import LangBotToBoxAction
from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.errors import BoxError
from langbot_plugin.box.host_backend import HostProcessBackend
from langbot_plugin.box.models import BoxHostMountMode, BoxSpec
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.security import BOX_CONTROL_TOKEN_HEADER, BOX_INSTANCE_HEADER
from langbot_plugin.box.server import create_app
from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.handler import FILE_CHUNK_LENGTH, Handler
from langbot_plugin.runtime.security import PLUGIN_FILE_STORAGE_DIR_ENV


_CONTEXT = ActionContext(
    instance_uuid="file-transfer-instance",
    workspace_uuid="workspace-a",
    placement_generation=1,
)
_TOKEN = "file-transfer-test-control-token-32-bytes"
_MAX_BYTES = 2 * 1024 * 1024


@pytest.fixture
async def network_box(tmp_path, monkeypatch):
    """Keep Core staging and Runtime workspace in separate directory trees."""
    monkeypatch.delenv("LANGBOT_BOX_CONFIG", raising=False)
    runtime_root = tmp_path / "runtime"
    runtime_root.mkdir()
    workspace = runtime_root / "workspace"
    workspace.mkdir()
    transfer_root = runtime_root / "transfers"
    monkeypatch.setenv(PLUGIN_FILE_STORAGE_DIR_ENV, str(transfer_root))
    logger = logging.getLogger(__name__)
    runtime = BoxRuntime(
        logger,
        backends=[HostProcessBackend(logger)],
        instance_id=_CONTEXT.instance_uuid,
        data_dir=runtime_root / "identity",
    )
    runtime.init({"backend": "host", "limits": {"max_rpc_file_bytes": _MAX_BYTES}})
    await runtime.initialize()
    test_server = TestServer(
        create_app(
            runtime,
            control_token=_TOKEN,
            trusted_instance_uuid=_CONTEXT.instance_uuid,
        )
    )
    await test_server.start_server()
    core_root = tmp_path / "core"
    core_root.mkdir()
    connection_count = 0

    @asynccontextmanager
    async def connect():
        nonlocal connection_count
        connection_count += 1
        core_transfers = core_root / str(connection_count)
        url = str(test_server.make_url("/rpc/ws")).replace("http://", "ws://", 1)
        async with websockets.connect(
            url,
            additional_headers={
                BOX_CONTROL_TOKEN_HEADER: _TOKEN,
                BOX_INSTANCE_HEADER: _CONTEXT.instance_uuid,
            },
            proxy=None,
        ) as websocket:
            handler = Handler(
                WebSocketConnection(websocket),
                file_storage_dir=core_transfers,
                max_file_bytes=_MAX_BYTES,
            )
            task = asyncio.create_task(handler.run())
            client = ActionRPCBoxClient(logger)
            client.set_handler(handler)
            try:
                yield client, handler
            finally:
                await handler.close()
                await asyncio.gather(task, return_exceptions=True)

    try:
        async with connect() as (client, handler):
            await client.create_session(
                BoxSpec(session_id="files", host_path=str(workspace)),
                action_context=_CONTEXT,
            )
            yield SimpleNamespace(
                client=client,
                handler=handler,
                connect=connect,
                runtime=runtime,
                workspace=workspace,
                transfer_root=transfer_root,
                core_root=core_root,
            )
    finally:
        await test_server.close()
        await runtime.shutdown()


@pytest.mark.asyncio
@pytest.mark.parametrize("content", [b"", bytes(range(256)) * 5000])
async def test_websocket_roundtrip_and_retry(network_box, content):
    client = network_box.client
    path = "/workspace/inputs/payload.bin"
    expected = {
        "path": path,
        "size": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    result = await client.upload_file("files", path, content, action_context=_CONTEXT)
    assert result == expected
    assert await client.download_file("files", path, action_context=_CONTEXT) == content
    assert (
        await client.upload_file("files", path, content, action_context=_CONTEXT)
        == expected
    )
    assert (network_box.workspace / "inputs/payload.bin").read_bytes() == content
    assert not list(network_box.core_root.rglob("*.bin"))


@pytest.mark.asyncio
async def test_transfer_uses_bound_backend_after_default_changes(
    network_box, monkeypatch
):
    runtime = network_box.runtime
    runtime.max_sessions = 1
    different_backend = HostProcessBackend(logging.getLogger(__name__))

    async def reject_default(*args, **kwargs):
        raise AssertionError("Existing session must keep its original backend")

    monkeypatch.setattr(different_backend, "upload_file", reject_default)
    monkeypatch.setattr(different_backend, "download_file", reject_default)
    runtime._backend = different_backend
    content = b"bound session content"
    await network_box.client.upload_file(
        "files", "/workspace/bound.bin", content, action_context=_CONTEXT
    )
    assert (
        await network_box.client.download_file(
            "files", "/workspace/bound.bin", action_context=_CONTEXT
        )
        == content
    )
    assert (network_box.workspace / "bound.bin").read_bytes() == content
    assert len(runtime._sessions) == 1


@pytest.mark.asyncio
async def test_transfer_lease_protects_session_from_idle_expiry(
    network_box, monkeypatch
):
    runtime = network_box.runtime
    await runtime.stop_background_reaper()
    session_id, session = next(iter(runtime._sessions.items()))
    session.idle_ttl_sec = 1
    runtime._expirable_session_ids.add(session_id)
    started, resume = asyncio.Event(), asyncio.Event()
    download_file = session.backend.download_file

    async def pause_download(*args, **kwargs):
        started.set()
        await resume.wait()
        return await download_file(*args, **kwargs)

    (network_box.workspace / "lease.bin").write_bytes(b"leased")
    monkeypatch.setattr(session.backend, "download_file", pause_download)
    download = asyncio.create_task(
        network_box.client.download_file(
            "files", "/workspace/lease.bin", action_context=_CONTEXT
        )
    )
    try:
        await asyncio.wait_for(started.wait(), timeout=5)
        session.info.last_used_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            seconds=5
        )
        async with runtime._lock:
            assert runtime._session_leases[session_id] == 1
            assert await runtime._reap_expired_sessions_locked() == []
        resume.set()
        assert await download == b"leased"
        assert not runtime._session_leases
        session.info.last_used_at = dt.datetime.now(dt.timezone.utc) - dt.timedelta(
            seconds=5
        )
        async with runtime._lock:
            cleanup = await runtime._reap_expired_sessions_locked()
        assert len(cleanup) == 1
        await asyncio.gather(*cleanup)
        assert session_id not in runtime._sessions
    finally:
        resume.set()
        await asyncio.gather(download, return_exceptions=True)


@pytest.mark.asyncio
async def test_file_operations_require_exact_workspace_and_instance(network_box):
    client = network_box.client
    path = "/workspace/private.bin"
    await client.upload_file("files", path, b"private", action_context=_CONTEXT)
    contexts = [
        None,
        _CONTEXT.model_copy(update={"workspace_uuid": "workspace-b"}),
        _CONTEXT.model_copy(update={"instance_uuid": "another-instance"}),
    ]
    for context in contexts:
        with pytest.raises((BoxError, ValueError)):
            await client.download_file("files", path, action_context=context)
        with pytest.raises((BoxError, ValueError)):
            await client.upload_file("files", path, b"changed", action_context=context)
    assert (
        await client.download_file("files", path, action_context=_CONTEXT) == b"private"
    )


@pytest.mark.asyncio
async def test_file_operations_reject_stale_generation(network_box):
    client = network_box.client
    newer = _CONTEXT.model_copy(update={"placement_generation": 2})
    await client.get_sessions(action_context=newer)
    with pytest.raises(BoxError):
        await client.upload_file(
            "files", "/workspace/stale.bin", b"stale", action_context=_CONTEXT
        )
    assert not (network_box.workspace / "stale.bin").exists()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "path",
    [
        "relative.bin",
        "/workspace/../escape.bin",
        "/etc/passwd",
        "/workspace//file.bin",
        "/workspace/./file.bin",
    ],
)
async def test_invalid_paths_are_rejected(network_box, path):
    with pytest.raises((BoxError, ValueError)):
        await network_box.client.upload_file(
            "files", path, b"invalid", action_context=_CONTEXT
        )
    with pytest.raises((BoxError, ValueError)):
        await network_box.client.download_file("files", path, action_context=_CONTEXT)


@pytest.mark.asyncio
async def test_symlinks_cannot_redirect_upload_or_download(network_box, tmp_path):
    outside = tmp_path / "outside"
    outside.mkdir()
    secret = outside / "secret.bin"
    secret.write_bytes(b"outside")
    (network_box.workspace / "directory-link").symlink_to(
        outside, target_is_directory=True
    )
    (network_box.workspace / "file-link").symlink_to(secret)
    for path in ("/workspace/directory-link/secret.bin", "/workspace/file-link"):
        with pytest.raises(BoxError):
            await network_box.client.download_file(
                "files", path, action_context=_CONTEXT
            )
        with pytest.raises(BoxError):
            await network_box.client.upload_file(
                "files", path, b"overwrite", action_context=_CONTEXT
            )
    assert secret.read_bytes() == b"outside"


@pytest.mark.asyncio
async def test_read_only_workspace_rejects_upload(network_box, tmp_path):
    readonly = tmp_path / "readonly"
    readonly.mkdir()
    (readonly / "existing.bin").write_bytes(b"original")
    await network_box.client.create_session(
        BoxSpec(
            session_id="readonly",
            host_path=str(readonly),
            host_path_mode=BoxHostMountMode.READ_ONLY,
        ),
        action_context=_CONTEXT,
    )
    assert (
        await network_box.client.download_file(
            "readonly", "/workspace/existing.bin", action_context=_CONTEXT
        )
        == b"original"
    )
    with pytest.raises(BoxError):
        await network_box.client.upload_file(
            "readonly", "/workspace/existing.bin", b"changed", action_context=_CONTEXT
        )
    assert (readonly / "existing.bin").read_bytes() == b"original"


@pytest.mark.asyncio
async def test_file_limits_preserve_existing_destination(network_box):
    destination = network_box.workspace / "existing.bin"
    destination.write_bytes(b"original")
    with pytest.raises((BoxError, ValueError)):
        await network_box.client.upload_file(
            "files",
            "/workspace/existing.bin",
            b"x" * (_MAX_BYTES + 1),
            action_context=_CONTEXT,
        )
    assert destination.read_bytes() == b"original"
    large = network_box.workspace / "large.bin"
    with large.open("wb") as file:
        file.truncate(_MAX_BYTES + 1)
    with pytest.raises(BoxError):
        await network_box.client.download_file(
            "files", "/workspace/large.bin", action_context=_CONTEXT
        )


@pytest.mark.asyncio
async def test_partial_network_upload_is_private_and_disconnect_cleans_it(network_box):
    """An interrupted wire transfer must never become a sandbox input."""
    async with network_box.connect() as (client, handler):
        await handler.call_action(
            CommonAction.FILE_CHUNK,
            {
                "file_key": "ft1_" + "ab" * 32 + ".bin",
                "file_length": FILE_CHUNK_LENGTH * 2,
                "chunk_index": 0,
                "chunk_amount": 2,
                "chunk_size": FILE_CHUNK_LENGTH,
                "chunk_base64": base64.b64encode(b"x" * FILE_CHUNK_LENGTH).decode(),
            },
            action_context=_CONTEXT,
        )
        assert not list(network_box.workspace.iterdir())
    # Closing the server handler is asynchronous to the peer's close handshake.
    for _ in range(100):
        payloads = [
            p
            for p in network_box.transfer_root.rglob("*")
            if p.is_file() and not p.name.endswith(".lock")
        ]
        if not payloads:
            break
        await asyncio.sleep(0.01)
    assert not payloads


@pytest.mark.asyncio
async def test_cancelled_upload_preserves_destination_and_can_retry(
    network_box, monkeypatch
):
    destination = network_box.workspace / "cancelled.bin"
    destination.write_bytes(b"original")
    first_chunk = asyncio.Event()
    pause = asyncio.Event()
    call_action = network_box.handler.call_action
    interrupted = False

    async def interrupt_after_first_chunk(action, data, **kwargs):
        nonlocal interrupted
        response = await call_action(action, data, **kwargs)
        if action == CommonAction.FILE_CHUNK and not interrupted:
            interrupted = True
            first_chunk.set()
            await pause.wait()
        return response

    monkeypatch.setattr(network_box.handler, "call_action", interrupt_after_first_chunk)
    content = b"new" * FILE_CHUNK_LENGTH
    upload = asyncio.create_task(
        network_box.client.upload_file(
            "files", "/workspace/cancelled.bin", content, action_context=_CONTEXT
        )
    )
    try:
        await asyncio.wait_for(first_chunk.wait(), timeout=5)
    finally:
        upload.cancel()
        with pytest.raises(asyncio.CancelledError):
            await upload
    assert destination.read_bytes() == b"original"
    assert not [
        path
        for path in network_box.transfer_root.rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    ]
    await network_box.client.upload_file(
        "files", "/workspace/cancelled.bin", content, action_context=_CONTEXT
    )
    assert (
        await network_box.client.download_file(
            "files", "/workspace/cancelled.bin", action_context=_CONTEXT
        )
        == content
    )


@pytest.mark.asyncio
async def test_upload_receipt_mismatch_keeps_destination(network_box):
    destination = network_box.workspace / "existing.bin"
    destination.write_bytes(b"original")
    content = b"new content"
    key = await network_box.handler.send_file(content, "", action_context=_CONTEXT)
    with pytest.raises(BoxError):
        await network_box.client._call(
            LangBotToBoxAction.UPLOAD_FILE,
            {
                "session_id": "files",
                "path": "/workspace/existing.bin",
                "file_key": key,
                "size": len(content),
                "sha256": "0" * 64,
            },
            action_context=_CONTEXT,
        )
    assert destination.read_bytes() == b"original"


@pytest.mark.asyncio
async def test_cancelled_download_cleans_partial_receiver_and_can_retry(
    network_box, monkeypatch
):
    content = b"download" * FILE_CHUNK_LENGTH
    (network_box.workspace / "download.bin").write_bytes(content)
    first_chunk = asyncio.Event()
    resume_receiver = asyncio.Event()
    receive_chunk = network_box.handler.actions[CommonAction.FILE_CHUNK.value]
    interrupted = False

    async def pause_first_received_chunk(data):
        nonlocal interrupted
        response = await receive_chunk(data)
        if not interrupted:
            interrupted = True
            first_chunk.set()
            await resume_receiver.wait()
        return response

    monkeypatch.setitem(
        network_box.handler.actions,
        CommonAction.FILE_CHUNK.value,
        pause_first_received_chunk,
    )
    download = asyncio.create_task(
        network_box.client.download_file(
            "files", "/workspace/download.bin", action_context=_CONTEXT
        )
    )
    try:
        await asyncio.wait_for(first_chunk.wait(), timeout=5)
        assert network_box.handler._transfer_stages
    finally:
        download.cancel()
        try:
            with pytest.raises(asyncio.CancelledError):
                await download
        finally:
            resume_receiver.set()
    assert not network_box.handler._transfer_stages
    assert not [
        path
        for path in network_box.core_root.rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    ]
    assert (
        await network_box.client.download_file(
            "files", "/workspace/download.bin", action_context=_CONTEXT
        )
        == content
    )


@pytest.mark.asyncio
async def test_another_workspace_cannot_delete_partial_transfer(network_box):
    key = "ft1_" + "cd" * 32
    chunk = b"owned" * (FILE_CHUNK_LENGTH // 5)
    content = chunk * 2

    async def send_chunk(index):
        await network_box.handler.call_action(
            CommonAction.FILE_CHUNK,
            {
                "file_key": key,
                "file_length": len(content),
                "chunk_index": index,
                "chunk_amount": 2,
                "chunk_size": len(chunk),
                "chunk_base64": base64.b64encode(chunk).decode(),
            },
            action_context=_CONTEXT,
        )

    await send_chunk(0)
    with pytest.raises(BoxError):
        await network_box.client._call(
            LangBotToBoxAction.DELETE_FILE_TRANSFER,
            {"file_key": key},
            action_context=_CONTEXT.model_copy(
                update={"workspace_uuid": "workspace-b"}
            ),
        )
    # The owning Workspace must still be able to finish and publish its upload.
    await send_chunk(1)
    await network_box.client._call(
        LangBotToBoxAction.UPLOAD_FILE,
        {
            "session_id": "files",
            "path": "/workspace/owned.bin",
            "file_key": key,
            "size": len(content),
            "sha256": hashlib.sha256(content).hexdigest(),
        },
        action_context=_CONTEXT,
    )
    assert (
        await network_box.client.download_file(
            "files", "/workspace/owned.bin", action_context=_CONTEXT
        )
        == content
    )


@pytest.mark.asyncio
async def test_download_cleanup_survives_repeated_cancellation(
    network_box, monkeypatch
):
    content = b"completed download"
    (network_box.workspace / "cleanup.bin").write_bytes(content)
    handler = network_box.handler
    read_file = handler.read_local_file
    delete_file = handler.delete_local_file
    cleanup_started = asyncio.Event()
    lock_held = False

    async def hold_lock_after_read(file_key, **kwargs):
        nonlocal lock_held
        result = await read_file(file_key, **kwargs)
        await handler._file_transfer_lock.acquire()
        lock_held = True
        return result

    async def record_cleanup(file_key, **kwargs):
        cleanup_started.set()
        await delete_file(file_key, **kwargs)

    monkeypatch.setattr(handler, "read_local_file", hold_lock_after_read)
    monkeypatch.setattr(handler, "delete_local_file", record_cleanup)
    download = asyncio.create_task(
        network_box.client.download_file(
            "files", "/workspace/cleanup.bin", action_context=_CONTEXT
        )
    )
    try:
        await asyncio.wait_for(cleanup_started.wait(), timeout=5)
        assert handler._owned_transfer_files
        download.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not download.done()
        download.cancel()
        await asyncio.sleep(0)
        await asyncio.sleep(0)
        assert not download.done()
    finally:
        if lock_held:
            handler._file_transfer_lock.release()
        if not cleanup_started.is_set():
            download.cancel()
        with pytest.raises(asyncio.CancelledError):
            await download
    assert not handler._transfer_stages
    assert not handler._owned_transfer_files
    assert not [
        path
        for path in network_box.core_root.rglob("*")
        if path.is_file() and not path.name.endswith(".lock")
    ]
    monkeypatch.setattr(handler, "read_local_file", read_file)
    monkeypatch.setattr(handler, "delete_local_file", delete_file)
    assert (
        await network_box.client.download_file(
            "files", "/workspace/cleanup.bin", action_context=_CONTEXT
        )
        == content
    )


@pytest.mark.asyncio
async def test_download_timeout_cleans_partial_receiver_and_can_retry(
    network_box, monkeypatch
):
    content = b"deadline" * FILE_CHUNK_LENGTH
    (network_box.workspace / "timeout.bin").write_bytes(content)
    handler = network_box.handler
    receive_chunk = handler.actions[CommonAction.FILE_CHUNK.value]
    call_action = handler.call_action
    first_chunk = asyncio.Event()
    resume_receiver = asyncio.Event()
    interrupted = False

    async def pause_first_received_chunk(data):
        nonlocal interrupted
        response = await receive_chunk(data)
        if not interrupted:
            interrupted = True
            first_chunk.set()
            await resume_receiver.wait()
        return response

    async def shorten_download_deadline(action, data, **kwargs):
        if action == LangBotToBoxAction.DOWNLOAD_FILE:
            kwargs["timeout"] = 0.05
        return await call_action(action, data, **kwargs)

    monkeypatch.setitem(
        handler.actions, CommonAction.FILE_CHUNK.value, pause_first_received_chunk
    )
    monkeypatch.setattr(handler, "call_action", shorten_download_deadline)
    download = asyncio.create_task(
        network_box.client.download_file(
            "files", "/workspace/timeout.bin", action_context=_CONTEXT
        )
    )
    try:
        await asyncio.wait_for(first_chunk.wait(), timeout=5)
        assert handler._transfer_stages
        with pytest.raises(BoxError, match="timed out"):
            await download
        assert not handler._transfer_stages
        assert not handler._owned_transfer_files
        assert not [
            path
            for path in network_box.core_root.rglob("*")
            if path.is_file() and not path.name.endswith(".lock")
        ]
    finally:
        resume_receiver.set()
        if not download.done():
            download.cancel()
        await asyncio.gather(download, return_exceptions=True)
    monkeypatch.setattr(handler, "call_action", call_action)
    assert (
        await network_box.client.download_file(
            "files", "/workspace/timeout.bin", action_context=_CONTEXT
        )
        == content
    )
