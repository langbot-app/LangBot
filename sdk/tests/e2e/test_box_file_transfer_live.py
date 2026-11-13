"""Opt-in, single-sandbox file smoke via LANGBOT_FILE_TRANSFER_BACKEND."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
import hashlib
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
import uuid

from aiohttp.test_utils import TestServer
import pytest
import websockets

from langbot_plugin.box.backend import DockerBackend
from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.e2b_backend import E2BSandboxBackend
from langbot_plugin.box.errors import BoxError
from langbot_plugin.box.models import BoxSpec, E2BConnectionConfig
from langbot_plugin.box.nsjail_backend import NsjailBackend
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.security import BOX_CONTROL_TOKEN_HEADER, BOX_INSTANCE_HEADER
from langbot_plugin.box.server import create_app
from langbot_plugin.box.tenancy import namespace_session_id
from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.entities.io.context import ActionContext
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.runtime.io.handler import Handler
from langbot_plugin.runtime.security import PLUGIN_FILE_STORAGE_DIR_ENV


_BACKEND = os.environ.get("LANGBOT_FILE_TRANSFER_BACKEND", "")
_MAX_BYTES = 64 * 1024
pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.skipif(
        not _BACKEND, reason="select one real file-transfer backend explicitly"
    ),
]


def _event(step, outcome):
    print(
        json.dumps({"backend": _BACKEND, "step": step, "outcome": outcome}), flush=True
    )


async def _step(name, operation):
    _event(name, "started")
    try:
        result = await asyncio.wait_for(operation, timeout=20)
    except BaseException as exc:
        _event(name, type(exc).__name__)
        raise
    _event(name, "passed")
    return result


async def _docker(*args):
    process = await asyncio.create_subprocess_exec(
        "docker", *args, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    try:
        output, _ = await asyncio.wait_for(process.communicate(), timeout=5)
    finally:
        if process.returncode is None:
            process.kill()
            await process.communicate()
    return process.returncode, output.decode().strip()


@pytest.fixture
async def live_network_box(tmp_path, monkeypatch):
    if _BACKEND not in {"docker", "nsjail", "e2b"}:
        pytest.fail("LANGBOT_FILE_TRANSFER_BACKEND must select docker, nsjail or e2b")
    monkeypatch.delenv("LANGBOT_BOX_CONFIG", raising=False)
    monkeypatch.delenv("LANGBOT_BOX_INSTANCE_ID", raising=False)
    monkeypatch.setenv(PLUGIN_FILE_STORAGE_DIR_ENV, str(tmp_path / "runtime-transfers"))
    logger = logging.getLogger(__name__)
    instance = "file-transfer-live-" + uuid.uuid4().hex
    context = ActionContext(
        instance_uuid=instance, workspace_uuid="workspace", placement_generation=1
    )
    workspace = tmp_path / "runtime-workspace"
    workspace.mkdir()
    created_e2b = []
    e2b_connection = None
    config = {
        "backend": _BACKEND,
        "limits": {"max_sessions": 1, "max_rpc_file_bytes": _MAX_BYTES},
    }
    if _BACKEND == "docker":
        code, _ = await _step(
            "check_existing_image", _docker("image", "inspect", "python:3.12-alpine")
        )
        assert code == 0, (
            "python:3.12-alpine must already exist; this smoke never pulls images"
        )
        backend = DockerBackend(logger)
    elif _BACKEND == "nsjail":
        backend = NsjailBackend(logger, base_dir=str(tmp_path / "nsjail-sessions"))
        build_args = backend._build_nsjail_args

        def diagnostic_args(*args):
            return [value for value in build_args(*args) if value != "--really_quiet"]

        monkeypatch.setattr(backend, "_build_nsjail_args", diagnostic_args)
    else:
        from e2b import AsyncSandbox

        required = ("E2B_API_KEY", "E2B_API_URL", "E2B_SANDBOX_URL")
        assert all(os.environ.get(name) for name in required), (
            "selected E2B smoke requires E2B_API_KEY, E2B_API_URL and E2B_SANDBOX_URL"
        )
        e2b_connection = E2BConnectionConfig(
            api_url=os.environ["E2B_API_URL"],
            sandbox_url=os.environ["E2B_SANDBOX_URL"],
            api_key=os.environ["E2B_API_KEY"],
            template=os.environ.get("E2B_TEMPLATE") or "base",
        )
        for name in (*required, "E2B_DOMAIN", "E2B_TEMPLATE"):
            monkeypatch.delenv(name, raising=False)
        original_create = AsyncSandbox.create

        async def create_bounded_sandbox(**kwargs):
            assert not created_e2b, "this smoke creates exactly one sandbox"
            kwargs.update(timeout=120, request_timeout=15)
            kwargs["metadata"] = {
                **kwargs.get("metadata", {}),
                "file-transfer-validation": instance,
            }
            sandbox = await original_create(**kwargs)
            created_e2b.append(sandbox)
            (tmp_path / "created-sandbox.json").write_text(
                json.dumps({"sandbox_id": sandbox.sandbox_id})
            )
            return sandbox

        monkeypatch.setattr(AsyncSandbox, "create", create_bounded_sandbox)
        config["backend"] = "docker"
        backend = DockerBackend(logger)
    backends = [backend]
    if _BACKEND == "e2b":
        backends.append(E2BSandboxBackend(logger))
    runtime = BoxRuntime(
        logger,
        backends=backends,
        instance_id=instance,
        data_dir=tmp_path / "identity",
        session_ttl_sec=0,
    )
    runtime.init(config)
    token = "live-file-transfer-control-" + uuid.uuid4().hex
    server = TestServer(
        create_app(runtime, control_token=token, trusted_instance_uuid=instance)
    )
    info = None

    async def require_e2b_presence(expected):
        from e2b import AsyncSandbox
        from e2b.sandbox.sandbox_api import SandboxQuery, SandboxState

        pager = AsyncSandbox.list(
            query=SandboxQuery(
                metadata={"file-transfer-validation": instance},
                state=[SandboxState.RUNNING, SandboxState.PAUSED],
            ),
            limit=10,
            request_timeout=5,
            **e2b_connection.model_dump(exclude={"template"}),
        )
        found = False
        for _ in range(3):
            items = await pager.next_items()
            found |= any(item.sandbox_id == created_e2b[0].sandbox_id for item in items)
            if not pager.has_next:
                break
        assert not pager.has_next, "Sandbox listing exceeds the validation query budget"
        assert found == expected, (
            "Exact E2B sandbox presence differs from expected state"
        )

    @asynccontextmanager
    async def connect():
        url = str(server.make_url("/rpc/ws")).replace("http://", "ws://", 1)
        async with websockets.connect(
            url,
            additional_headers={
                BOX_CONTROL_TOKEN_HEADER: token,
                BOX_INSTANCE_HEADER: instance,
            },
            proxy=None,
        ) as websocket:
            handler = Handler(
                WebSocketConnection(websocket),
                file_storage_dir=tmp_path / "core-transfers",
                max_file_bytes=_MAX_BYTES,
            )
            handler_task = asyncio.create_task(handler.run())
            box_client = ActionRPCBoxClient(logger)
            box_client.set_handler(handler)
            try:
                yield box_client, handler
            finally:
                await handler.close()
                await asyncio.gather(handler_task, return_exceptions=True)

    spec = BoxSpec(
        session_id="files",
        backend="e2b" if _BACKEND == "e2b" else None,
        e2b_config=e2b_connection,
        host_path=None if _BACKEND == "e2b" else str(workspace),
        image="python:3.12-alpine"
        if _BACKEND == "docker"
        else "rockchin/langbot-sandbox:latest",
        network="off",
        timeout_sec=5,
        cpus=0.25,
        memory_mb=128,
        pids_limit=32,
    )
    try:
        await _step("initialize", runtime.initialize())
        if _BACKEND == "e2b":
            assert runtime._backend is backend and backend.name == "docker"
            _event("default_backend_is_docker", "passed")
        await server.start_server()
        async with connect() as (client, handler):
            try:
                await _step(
                    "create_single_session",
                    client.create_session(spec, action_context=context),
                )
                session = runtime._sessions[namespace_session_id(context, "files")]
                info = session.info
                if _BACKEND == "e2b":
                    assert runtime._backend is backend and info.backend_name == "e2b"
                    assert session.backend.connection_config == e2b_connection
                    assert len(created_e2b) == 1
                    _event("explicit_session_backend_is_e2b", "passed")
                    await _step(
                        "verify_exact_sandbox_exists", require_e2b_presence(True)
                    )
                yield SimpleNamespace(
                    client=client,
                    handler=handler,
                    context=context,
                    spec=spec,
                    tmp_path=tmp_path,
                )
            finally:
                if info is not None:
                    await _step(
                        "delete_exact_session",
                        client.delete_session("files", action_context=context),
                    )
    finally:
        try:
            try:
                await server.close()
            finally:
                await _step("shutdown", runtime.shutdown())
        finally:
            if _BACKEND == "e2b" and created_e2b:
                await _step("verify_exact_sandbox_removed", require_e2b_presence(False))
            elif info is not None and _BACKEND == "docker":
                code, remaining = await _step(
                    "verify_exact_container_removed",
                    _docker(
                        "container",
                        "ls",
                        "--all",
                        "--filter",
                        f"name=^/{info.backend_session_id}$",
                        "--format",
                        "{{.ID}}",
                    ),
                )
                assert code == 0, "Cannot verify cleanup against the Docker daemon"
                assert not remaining, "The exact created Docker container still exists"
            elif info is not None:
                assert not Path(info.backend_session_id).exists(), (
                    "The exact nsjail session directory still exists"
                )
                _event("verify_exact_session_removed", "passed")


async def test_single_sandbox_file_transfer(live_network_box, monkeypatch):
    box = live_network_box
    client, context = box.client, box.context
    content = bytes(range(256)) * 256
    expected_digest = hashlib.sha256(content).hexdigest()
    receipt = await _step(
        "upload_64k",
        client.upload_file("files", "/workspace/input.bin", content, context),
    )
    assert receipt == {
        "path": "/workspace/input.bin",
        "size": len(content),
        "sha256": expected_digest,
    }
    result = await _step(
        "sandbox_read_and_copy",
        client.execute(
            box.spec.model_copy(
                update={
                    "cmd": "sha256sum /workspace/input.bin && cp /workspace/input.bin /workspace/output.bin"
                }
            ),
            action_context=context,
        ),
    )
    assert result.ok, result.stderr
    assert result.stdout.split()[0] == expected_digest
    assert (
        await _step(
            "download_64k",
            client.download_file("files", "/workspace/output.bin", context),
        )
        == content
    )
    await _step(
        "upload_empty",
        client.upload_file("files", "/workspace/empty.bin", b"", context),
    )
    assert (
        await _step(
            "download_empty",
            client.download_file("files", "/workspace/empty.bin", context),
        )
        == b""
    )

    async def reject_path():
        with pytest.raises(BoxError):
            await client.upload_file(
                "files", "/workspace/../escape.bin", b"invalid", context
            )

    await _step("reject_path", reject_path())
    handler = box.handler
    call_action = handler.call_action
    first_chunk = asyncio.Event()
    pause = asyncio.Event()
    interrupted = False

    async def pause_after_first_ack(action, data, **kwargs):
        nonlocal interrupted
        response = await call_action(action, data, **kwargs)
        if action == CommonAction.FILE_CHUNK and not interrupted:
            interrupted = True
            first_chunk.set()
            await pause.wait()
        return response

    async def cancel_upload():
        monkeypatch.setattr(handler, "call_action", pause_after_first_ack)
        upload = asyncio.create_task(
            client.upload_file(
                "files", "/workspace/cancelled.bin", b"c" * 49152, context
            )
        )
        try:
            await asyncio.wait_for(first_chunk.wait(), timeout=5)
        finally:
            upload.cancel()
            try:
                with pytest.raises(asyncio.CancelledError):
                    await upload
            finally:
                monkeypatch.setattr(handler, "call_action", call_action)
        assert not [
            path
            for path in (box.tmp_path / "runtime-transfers").rglob("*")
            if path.is_file() and not path.name.endswith(".lock")
        ]

    await _step("cancel_upload_after_first_ack", cancel_upload())

    async def reject_oversize():
        with pytest.raises((BoxError, ValueError)):
            await client.upload_file(
                "files", "/workspace/oversize.bin", b"x" * (_MAX_BYTES + 1), context
            )

    await _step("reject_oversize_upload", reject_oversize())
