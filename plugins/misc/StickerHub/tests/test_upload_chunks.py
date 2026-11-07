"""Chunked upload keeps the HTTP body constant regardless of image size."""

from __future__ import annotations

import asyncio
import base64
import json
import time

import pytest

from stickerlib import UPLOAD_CHUNK_BYTES

PNG = b"\x89PNG\r\n\x1a\n" + b"\x00" * 16


def run(coro):
    return asyncio.run(coro)


def big_png(total: int) -> bytes:
    return b"\x89PNG\r\n\x1a\n" + b"\x00" * (total - 8)


def test_upload_round_trips_through_chunks(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        payload = big_png(UPLOAD_CHUNK_BYTES * 2 + 10)
        session = (await plugin.begin_upload())["session"]

        received = 0
        for index in range(0, (len(payload) + UPLOAD_CHUNK_BYTES - 1) // UPLOAD_CHUNK_BYTES):
            piece = payload[index * UPLOAD_CHUNK_BYTES:(index + 1) * UPLOAD_CHUNK_BYTES]
            result = await plugin.put_upload_chunk(
                session, index, base64.b64encode(piece).decode("ascii")
            )
            received = result["received"]
        assert received == len(payload)

        item = await plugin.finish_upload("chunked", session)
        assert item["slug"] == "chunked"
        stored = await plugin.get_sticker_bytes("chunked")
        assert stored is not None and stored[0] == payload
    run(scenario())


def test_chunk_bytes_contract_is_constant(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        begin = await plugin.begin_upload()
        assert begin["chunk_bytes"] == UPLOAD_CHUNK_BYTES == 256 * 1024
        # The page splits on that number, so one request never exceeds it.
        assert begin["chunk_bytes"] <= 256 * 1024
    run(scenario())


def test_upload_rejects_a_gap(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        session = (await plugin.begin_upload())["session"]
        await plugin.put_upload_chunk(session, 0, base64.b64encode(PNG).decode())
        await plugin.put_upload_chunk(session, 2, base64.b64encode(PNG).decode())
        with pytest.raises(ValueError, match="gap"):
            await plugin.finish_upload("gappy", session)
    run(scenario())


def test_upload_enforces_the_size_limit(make_plugin):
    async def scenario():
        plugin, _ = make_plugin({"max_sticker_mb": 1})
        session = (await plugin.begin_upload())["session"]
        payload = big_png(1024 * 1024 + 32)
        with pytest.raises(ValueError, match="exceeds"):
            await plugin.put_upload_chunk(
                session, 0, base64.b64encode(payload).decode()
            )
    run(scenario())


def test_upload_rejects_a_bad_session(make_plugin):
    async def scenario():
        plugin, _ = make_plugin()
        with pytest.raises(ValueError, match="invalid upload session"):
            await plugin.put_upload_chunk("bad.session", 0, base64.b64encode(PNG).decode())
        with pytest.raises(ValueError, match="invalid upload session"):
            await plugin.finish_upload("cat", "../escape")
    run(scenario())


def test_finish_drops_the_session(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        session = (await plugin.begin_upload())["session"]
        await plugin.put_upload_chunk(session, 0, base64.b64encode(PNG).decode())
        await plugin.finish_upload("cat", session)
        assert not [key for key in host.data if ":upload:" in key]
    run(scenario())


def test_abandoned_sessions_are_reaped(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        stale = (await plugin.begin_upload())["session"]
        await plugin.put_upload_chunk(stale, 0, base64.b64encode(PNG).decode())
        # Age the marker past the TTL, then open a fresh session.
        key = next(k for k in host.data if ":upload:" in k and k.endswith(":000000"))
        host.data[key] = json.dumps({"created_at": time.time() - 20 * 60}).encode()
        await plugin.begin_upload()
        assert not [k for k in host.data if f":upload:{stale}:" in k]
    run(scenario())


def test_abort_drops_the_session(make_plugin):
    async def scenario():
        plugin, host = make_plugin()
        session = (await plugin.begin_upload())["session"]
        await plugin.put_upload_chunk(session, 0, base64.b64encode(PNG).decode())
        await plugin.abort_upload(session)
        assert not [k for k in host.data if ":upload:" in k]
    run(scenario())
