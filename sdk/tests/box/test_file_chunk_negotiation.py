"""Only mutually compatible Box peers use larger, ordered file chunks."""

from __future__ import annotations

import asyncio
import base64
import binascii
import hashlib
import json
import logging
import os
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.box.actions import LangBotToBoxAction
from langbot_plugin.box.client import ActionRPCBoxClient
from langbot_plugin.box.server import BoxServerHandler
from langbot_plugin.entities.io.actions.enums import CommonAction
from langbot_plugin.entities.io.errors import ActionCallTimeoutError
from langbot_plugin.entities.io.resp import ActionResponse
from langbot_plugin.runtime.io.handler import (
    BOX_FILE_CHUNK_LENGTH,
    FILE_CHUNK_LENGTH,
    Handler,
)
from langbot_plugin.runtime.security import PLUGIN_FILE_STORAGE_DIR_ENV
from tests.box import test_file_transfer as transfer_fixtures
from tests.helpers.protocol import ProtocolConnection


network_box = transfer_fixtures.network_box
_CONTEXT = transfer_fixtures._CONTEXT
_LOGGER = logging.getLogger(__name__)


@pytest.fixture
async def wire_handler(tmp_path):
    handler = Handler(
        ProtocolConnection(), file_storage_dir=tmp_path / "core-transfers"
    )
    try:
        yield handler
    finally:
        await handler.close()


@pytest.fixture
async def box_handler(tmp_path, monkeypatch):
    monkeypatch.setenv(PLUGIN_FILE_STORAGE_DIR_ENV, str(tmp_path / "box-transfers"))
    runtime = SimpleNamespace(
        max_rpc_file_bytes=2 * 1024 * 1024,
        max_admission_records=100,
        network_workspace=False,
        init=Mock(),
    )
    handler = BoxServerHandler(
        ProtocolConnection(),
        runtime,
        host_control_authenticated=True,
        trusted_instance_uuid=_CONTEXT.instance_uuid,
    )
    try:
        yield handler, runtime
    finally:
        await handler.close()


async def receive_chunk(handler, key, content, *, index=0, amount=1, context=_CONTEXT):
    token = handler._current_action_context.set(context)
    try:
        return await handler.actions[CommonAction.FILE_CHUNK.value](
            {
                "file_key": key,
                "chunk_base64": base64.b64encode(content).decode(),
                "chunk_index": index,
                "chunk_amount": amount,
            }
        )
    finally:
        handler._current_action_context.reset(token)


@pytest.mark.asyncio
async def test_generic_channels_keep_legacy_chunks(wire_handler, monkeypatch):
    calls = []

    async def capture(action, data, **kwargs):
        assert action is CommonAction.FILE_CHUNK
        calls.append(data)
        return {}

    monkeypatch.setattr(wire_handler, "call_action", capture)
    await wire_handler.send_file(os.urandom(FILE_CHUNK_LENGTH * 2 + 1), "bin")
    assert [chunk["chunk_size"] for chunk in calls] == [
        FILE_CHUNK_LENGTH,
        FILE_CHUNK_LENGTH,
        1,
    ]
    assert wire_handler._file_chunk_receive_limit == FILE_CHUNK_LENGTH


@pytest.mark.asyncio
@pytest.mark.parametrize("ack", [None, False, 1, "true", True])
async def test_client_requires_an_exact_capability_ack(wire_handler, monkeypatch, ack):
    call = AsyncMock(return_value={"initialized": True, "file_chunk_256k": ack})
    monkeypatch.setattr(wire_handler, "call_action", call)
    client = ActionRPCBoxClient(_LOGGER)
    client.set_handler(wire_handler)
    config = {"backend": "docker"}
    await client.init(config)
    assert config == {"backend": "docker"}
    assert call.await_args.args[1] == {"backend": "docker", "file_chunk_256k": True}
    assert wire_handler._file_chunk_length == (
        BOX_FILE_CHUNK_LENGTH if ack is True else FILE_CHUNK_LENGTH
    )
    # Offering receive capacity does not imply that the peer accepted larger sends.
    assert wire_handler._file_chunk_receive_limit == BOX_FILE_CHUNK_LENGTH


@pytest.mark.asyncio
async def test_new_client_with_old_init_ack_keeps_legacy_sends(
    wire_handler, monkeypatch
):
    monkeypatch.setattr(
        wire_handler, "call_action", AsyncMock(return_value={"initialized": True})
    )
    client = ActionRPCBoxClient(_LOGGER)
    client.set_handler(wire_handler)
    await client.init({"backend": "docker"})
    assert wire_handler._file_chunk_length == FILE_CHUNK_LENGTH


@pytest.mark.asyncio
async def test_custom_handler_without_chunk_capability_does_not_offer_it():
    handler = SimpleNamespace(call_action=AsyncMock(return_value={"initialized": True}))
    client = ActionRPCBoxClient(_LOGGER)
    client.set_handler(handler)
    config = {"backend": "docker", "file_chunk_256k": True}
    await client.init(config)
    assert handler.call_action.await_args.args[1] == {"backend": "docker"}
    assert config["file_chunk_256k"] is True


@pytest.mark.asyncio
@pytest.mark.parametrize("offer", [None, False, 1, "true", True])
async def test_server_requires_exact_offer_and_strips_transport_config(
    box_handler, offer
):
    handler, runtime = box_handler
    config = {"backend": "docker", "file_chunk_256k": offer}
    response = await handler.actions[LangBotToBoxAction.INIT.value](config)
    runtime.init.assert_called_once_with({"backend": "docker"})
    assert config == {"backend": "docker", "file_chunk_256k": offer}
    assert response.data.get("file_chunk_256k") is (True if offer is True else None)
    assert handler._file_chunk_length == (
        BOX_FILE_CHUNK_LENGTH if offer is True else FILE_CHUNK_LENGTH
    )
    assert handler._file_chunk_receive_limit == handler._file_chunk_length


@pytest.mark.asyncio
async def test_old_client_and_new_server_keep_the_original_init_response(box_handler):
    handler, runtime = box_handler
    response = await handler.actions[LangBotToBoxAction.INIT.value](
        {"backend": "docker"}
    )
    assert response.data == {
        "initialized": True,
        "network_workspace": False,
        "directory_archive": True,
        "artifact_cache_preflight": True,
    }
    assert (
        handler._file_chunk_length
        == handler._file_chunk_receive_limit
        == FILE_CHUNK_LENGTH
    )


@pytest.mark.asyncio
async def test_init_failure_or_unauthenticated_control_cannot_enable_large_chunks(
    box_handler,
):
    handler, runtime = box_handler
    handler._host_control_authenticated = False
    with pytest.raises(PermissionError):
        await handler.actions[LangBotToBoxAction.INIT.value]({"file_chunk_256k": True})
    runtime.init.assert_not_called()
    assert handler._file_chunk_receive_limit == FILE_CHUNK_LENGTH
    handler._host_control_authenticated = True
    runtime.init.side_effect = ValueError("Invalid runtime configuration")
    with pytest.raises(ValueError, match="Invalid runtime configuration"):
        await handler.actions[LangBotToBoxAction.INIT.value]({"file_chunk_256k": True})
    assert (
        handler._file_chunk_length
        == handler._file_chunk_receive_limit
        == FILE_CHUNK_LENGTH
    )


@pytest.mark.asyncio
async def test_client_accepts_a_large_download_before_the_init_ack(
    wire_handler, monkeypatch
):
    key, content = "ft1_" + "a" * 64 + ".bin", os.urandom(BOX_FILE_CHUNK_LENGTH)

    async def init_then_download(action, data, **kwargs):
        assert action is LangBotToBoxAction.INIT and data["file_chunk_256k"] is True
        assert wire_handler._file_chunk_length == FILE_CHUNK_LENGTH
        await receive_chunk(wire_handler, key, content)
        return {"initialized": True, "file_chunk_256k": True}

    monkeypatch.setattr(wire_handler, "call_action", init_then_download)
    client = ActionRPCBoxClient(_LOGGER)
    client.set_handler(wire_handler)
    await client.init({"backend": "docker"})
    assert await wire_handler.read_local_file(key, action_context=_CONTEXT) == content
    assert wire_handler._file_chunk_length == BOX_FILE_CHUNK_LENGTH


@pytest.mark.asyncio
@pytest.mark.parametrize("large", [False, True])
@pytest.mark.parametrize("extra", [1, 4])
async def test_unnegotiated_or_over_cap_chunks_are_rejected(wire_handler, large, extra):
    if large:
        wire_handler._configure_box_file_chunks(True)
    limit = BOX_FILE_CHUNK_LENGTH if large else FILE_CHUNK_LENGTH
    key = "ft1_" + "b" * 64 + ".bin"
    with pytest.raises(ValueError, match="protocol limit"):
        await receive_chunk(wire_handler, key, b"x" * (limit + extra))
    assert not wire_handler._transfer_stages
    with pytest.raises(FileNotFoundError):
        await wire_handler.read_local_file(key, action_context=_CONTEXT)


@pytest.mark.asyncio
async def test_large_chunk_total_limit_discards_the_private_stage(wire_handler):
    wire_handler._configure_box_file_chunks(True)
    wire_handler.max_file_bytes = BOX_FILE_CHUNK_LENGTH + 1
    key = "ft1_" + "e" * 64 + ".bin"
    await receive_chunk(wire_handler, key, os.urandom(BOX_FILE_CHUNK_LENGTH), amount=2)
    assert wire_handler._transfer_stages
    with pytest.raises(ValueError, match="configured size limit"):
        await receive_chunk(wire_handler, key, b"xx", index=1, amount=2)
    assert (
        not wire_handler._transfer_stages
        and key not in wire_handler._owned_transfer_files
    )
    assert not list(Path(wire_handler.file_storage_dir).rglob(".payload-*.tmp"))
    with pytest.raises(FileNotFoundError):
        await wire_handler.read_local_file(key, action_context=_CONTEXT)


@pytest.mark.asyncio
async def test_invalid_base64_releases_the_transfer_lock_without_a_stage(wire_handler):
    wire_handler._configure_box_file_chunks(True)
    key = "ft1_" + "f" * 64 + ".bin"
    token = wire_handler._current_action_context.set(_CONTEXT)
    try:
        with pytest.raises(binascii.Error):
            await wire_handler.actions[CommonAction.FILE_CHUNK.value](
                {
                    "file_key": key,
                    "chunk_base64": "%%%%",
                    "chunk_index": 0,
                    "chunk_amount": 1,
                }
            )
    finally:
        wire_handler._current_action_context.reset(token)
    assert (
        not wire_handler._file_transfer_lock.locked()
        and not wire_handler._transfer_stages
    )
    assert not list(Path(wire_handler.file_storage_dir).rglob(".payload-*.tmp"))
    await receive_chunk(wire_handler, key, b"valid retry")
    assert (
        await wire_handler.read_local_file(key, action_context=_CONTEXT)
        == b"valid retry"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("initial_large", [False, True])
async def test_chunk_length_is_captured_and_receive_limit_does_not_shrink(
    wire_handler, monkeypatch, initial_large
):
    wire_handler._configure_box_file_chunks(initial_large)
    length = BOX_FILE_CHUNK_LENGTH if initial_large else FILE_CHUNK_LENGTH
    lengths = []

    async def capture(action, data, **kwargs):
        lengths.append(data["chunk_size"])
        wire_handler._configure_box_file_chunks(not initial_large)
        return {}

    monkeypatch.setattr(wire_handler, "call_action", capture)
    await wire_handler.send_file(os.urandom(length * 2 + 1), "bin")
    assert lengths == [length, length, 1]
    assert wire_handler._file_chunk_length == (
        FILE_CHUNK_LENGTH if initial_large else BOX_FILE_CHUNK_LENGTH
    )
    assert wire_handler._file_chunk_receive_limit == BOX_FILE_CHUNK_LENGTH


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "negotiated,size,chunks_per_file,serialized",
    [
        (False, 2 * 16 * 1024, 2, False),
        (True, 2 * 256 * 1024, 2, True),
        (True, 4 * 1024, 1, False),
    ],
)
async def test_file_chunk_ack_serializes_only_large_chunks_without_blocking_ping(
    wire_handler, monkeypatch, negotiated, size, chunks_per_file, serialized
):
    wire_handler._configure_box_file_chunks(negotiated)
    content = os.urandom(size)
    keys = ["ft1_" + value * 64 + ".bin" for value in ("a", "b")]
    encoded_chunks = []
    encode = base64.b64encode

    def record_encode(chunk):
        encoded_chunks.append(chunk)
        return encode(chunk)

    monkeypatch.setattr(base64, "b64encode", record_encode)
    second_started = asyncio.Event()

    async def second_send():
        second_started.set()
        return await wire_handler.send_file(
            content, "bin", file_key=keys[1], action_context=_CONTEXT
        )

    first = asyncio.create_task(
        wire_handler.send_file(
            content, "bin", file_key=keys[0], action_context=_CONTEXT
        )
    )
    tasks = [first]
    try:
        await wire_handler.conn.sent_messages(1)
        second = asyncio.create_task(second_send())
        tasks.append(second)
        await second_started.wait()
        initial_chunks = 1 if serialized else 2
        await wire_handler.conn.sent_messages(initial_chunks)
        assert len(encoded_chunks) == initial_chunks

        ping = asyncio.create_task(wire_handler.call_action(CommonAction.PING, {}))
        tasks.append(ping)
        messages = await wire_handler.conn.sent_messages(initial_chunks + 1)
        ping_request = messages[-1]
        assert ping_request["action"] == CommonAction.PING.value
        wire_handler.resp_waiters[ping_request["seq_id"]].set_result(
            ActionResponse.success({})
        )
        assert await asyncio.wait_for(ping, 1) == {}
        assert not first.done() and not second.done()

        for acknowledged in range(chunks_per_file * 2):
            messages = await wire_handler.conn.sent_messages(acknowledged + 2)
            chunks = [
                message
                for message in messages
                if message["action"] == CommonAction.FILE_CHUNK.value
            ]
            if serialized:
                assert len(encoded_chunks) == acknowledged + 1
            request = chunks[acknowledged]
            assert request["context"] == _CONTEXT.model_dump(
                mode="json", exclude_none=True
            )
            wire_handler.resp_waiters[request["seq_id"]].set_result(
                ActionResponse.success({})
            )
        assert await asyncio.wait_for(asyncio.gather(first, second), 1) == keys
        assert len(encoded_chunks) == chunks_per_file * 2
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancelling_a_waiting_large_sender_does_not_encode_or_send_its_chunk(
    wire_handler, monkeypatch
):
    wire_handler._configure_box_file_chunks(True)
    content = os.urandom(BOX_FILE_CHUNK_LENGTH)
    encoded_chunks = []
    encode = base64.b64encode

    def record_encode(chunk):
        encoded_chunks.append(chunk)
        return encode(chunk)

    monkeypatch.setattr(base64, "b64encode", record_encode)
    first = asyncio.create_task(wire_handler.send_file(content, "bin"))
    tasks = [first]
    try:
        await wire_handler.conn.sent_messages(1)
        waiting_started = asyncio.Event()

        async def waiting_send():
            waiting_started.set()
            return await wire_handler.send_file(content, "bin")

        waiting = asyncio.create_task(waiting_send())
        tasks.append(waiting)
        await waiting_started.wait()
        waiting.cancel()
        with pytest.raises(asyncio.CancelledError):
            await waiting
        assert len(encoded_chunks) == 1 and len(wire_handler.conn.sent) == 1

        request = json.loads(wire_handler.conn.sent[0])
        wire_handler.resp_waiters[request["seq_id"]].set_result(
            ActionResponse.success({})
        )
        await asyncio.wait_for(first, 1)
        retry = asyncio.create_task(wire_handler.send_file(content, "bin"))
        tasks.append(retry)
        messages = await wire_handler.conn.sent_messages(2)
        assert len(encoded_chunks) == 2
        wire_handler.resp_waiters[messages[-1]["seq_id"]].set_result(
            ActionResponse.success({})
        )
        await asyncio.wait_for(retry, 1)
        assert not wire_handler.resp_waiters
    finally:
        for task in tasks:
            if not task.done():
                task.cancel()
        await asyncio.gather(*tasks, return_exceptions=True)


@pytest.mark.asyncio
async def test_timed_out_large_sender_does_not_hold_the_lock_or_send_a_chunk(
    wire_handler, monkeypatch
):
    wire_handler._configure_box_file_chunks(True)
    content = os.urandom(BOX_FILE_CHUNK_LENGTH)
    started, release = asyncio.Event(), asyncio.Event()
    sent = []
    wait = asyncio.wait

    async def short_lock_wait(tasks, timeout):
        return await wait(tasks, timeout=min(timeout, 0.05))

    async def acknowledge(action, data, **kwargs):
        assert action is CommonAction.FILE_CHUNK
        assert 0 < kwargs["timeout"] <= 15.0
        sent.append(data["file_key"])
        if len(sent) == 1:
            started.set()
            await release.wait()
        return {}

    monkeypatch.setattr(asyncio, "wait", short_lock_wait)
    monkeypatch.setattr(wire_handler, "call_action", acknowledge)
    first = asyncio.create_task(wire_handler.send_file(content, "bin"))
    try:
        await started.wait()
        with pytest.raises(ActionCallTimeoutError, match="__file_chunk call timed out"):
            await wire_handler.send_file(content, "bin")
        assert len(sent) == 1 and not first.done()
        release.set()
        await first
        await wire_handler.send_file(content, "bin")
        assert len(sent) == 2 and sent[0] != sent[1]
    finally:
        release.set()
        if not first.done():
            first.cancel()
        await asyncio.gather(first, return_exceptions=True)


@pytest.mark.asyncio
async def test_cancelling_the_sender_as_lock_acquire_finishes_releases_its_lock(
    wire_handler, monkeypatch
):
    wire_handler._configure_box_file_chunks(True)
    lock = wire_handler._large_file_chunk_send_lock
    content = os.urandom(BOX_FILE_CHUNK_LENGTH)
    acquire = lock.acquire
    parent = None
    encode = Mock(wraps=base64.b64encode)
    monkeypatch.setattr(base64, "b64encode", encode)

    async def acquire_then_cancel_parent():
        acquired = await acquire()
        parent.cancel()
        return acquired

    async def cancelled_send():
        nonlocal parent
        parent = asyncio.current_task()
        return await wire_handler.send_file(content, "bin")

    monkeypatch.setattr(lock, "acquire", acquire_then_cancel_parent)
    cancelled = asyncio.create_task(cancelled_send())
    with pytest.raises(asyncio.CancelledError):
        await cancelled
    assert not lock.locked()
    assert encode.call_count == 0 and not wire_handler.conn.sent

    monkeypatch.setattr(lock, "acquire", acquire)
    retry = asyncio.create_task(wire_handler.send_file(content, "bin"))
    try:
        messages = await wire_handler.conn.sent_messages(1)
        assert encode.call_count == 1
        wire_handler.resp_waiters[messages[0]["seq_id"]].set_result(
            ActionResponse.success({})
        )
        await asyncio.wait_for(retry, 1)
        assert not lock.locked() and not wire_handler.resp_waiters
    finally:
        if not retry.done():
            retry.cancel()
        await asyncio.gather(retry, return_exceptions=True)


@pytest.mark.asyncio
async def test_large_chunks_still_require_order_and_one_context(wire_handler):
    wire_handler._configure_box_file_chunks(True)
    key, content = "ft1_" + "c" * 64 + ".bin", os.urandom(BOX_FILE_CHUNK_LENGTH)
    with pytest.raises(ValueError):
        await receive_chunk(wire_handler, key, content, index=1, amount=2)
    await receive_chunk(wire_handler, key, content, amount=2)
    wire_handler._configure_box_file_chunks(False)
    other = _CONTEXT.model_copy(update={"workspace_uuid": "other-workspace"})
    with pytest.raises(ValueError):
        await receive_chunk(
            wire_handler, key, content, index=1, amount=2, context=other
        )
    with pytest.raises(FileNotFoundError):
        await wire_handler.read_local_file(key, action_context=_CONTEXT)
    await receive_chunk(wire_handler, key, content, index=1, amount=2)
    assert (
        await wire_handler.read_local_file(key, action_context=_CONTEXT) == content * 2
    )


@pytest.mark.asyncio
@pytest.mark.parametrize("peer", ["new-pair", "legacy-server", "legacy-client"])
async def test_incompressible_two_mib_roundtrip_negotiation_and_both_legacy_fallbacks(
    network_box, monkeypatch, peer
):
    if peer == "legacy-server":
        register = BoxServerHandler._register_actions

        def register_legacy_init(self):
            register(self)

            async def legacy_init(data):
                self._require_host_control()
                self._runtime.init(data)
                return ActionResponse.success({"initialized": True})

            self.actions[LangBotToBoxAction.INIT.value] = legacy_init

        monkeypatch.setattr(BoxServerHandler, "_register_actions", register_legacy_init)
    async with network_box.connect() as (client, handler):
        client_chunks, server_chunks = [], []
        client_call, server_call = handler.call_action, BoxServerHandler.call_action

        async def capture_client(action, data, **kwargs):
            if action is CommonAction.FILE_CHUNK:
                client_chunks.append(
                    (
                        data["chunk_index"],
                        data["chunk_amount"],
                        data["chunk_size"],
                        kwargs.get("action_context"),
                    )
                )
            return await client_call(action, data, **kwargs)

        async def capture_server(self, action, data, **kwargs):
            if action is CommonAction.FILE_CHUNK:
                server_chunks.append(
                    (
                        data["chunk_index"],
                        data["chunk_amount"],
                        data["chunk_size"],
                        kwargs.get("action_context"),
                    )
                )
            return await server_call(self, action, data, **kwargs)

        monkeypatch.setattr(handler, "call_action", capture_client)
        monkeypatch.setattr(BoxServerHandler, "call_action", capture_server)
        if peer == "legacy-client":
            # The old client sends the unextended INIT and ignores its response.
            await client._call(LangBotToBoxAction.INIT, {"backend": "host"})
        else:
            await client.init({"backend": "host"})
        content = os.urandom(2 * 1024 * 1024)
        result = await client.upload_file(
            "files", "/workspace/incompressible.bin", content, action_context=_CONTEXT
        )
        assert result["sha256"] == hashlib.sha256(content).hexdigest()
        assert (
            await client.download_file(
                "files", "/workspace/incompressible.bin", action_context=_CONTEXT
            )
            == content
        )
        count, length = (8, 256 * 1024) if peer == "new-pair" else (128, 16 * 1024)
        for chunks in (client_chunks, server_chunks):
            assert chunks == [
                (index, count, length, _CONTEXT) for index in range(count)
            ]
