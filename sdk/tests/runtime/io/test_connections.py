from __future__ import annotations

import asyncio
import json

import pytest

from langbot_plugin.runtime.io.connection import split_utf8_chunks
from langbot_plugin.runtime.io.connections import stdio as stdio_module
from langbot_plugin.runtime.io.connections import ws as ws_module
from langbot_plugin.runtime.io.connections.stdio import StdioConnection
from langbot_plugin.runtime.io.connections.ws import WebSocketConnection
from langbot_plugin.entities.io.errors import ConnectionClosedError


class FakeStreamReader:
    def __init__(self, lines: list[bytes]):
        self.lines = lines

    async def readline(self):
        return self.lines.pop(0)


class FakeStreamWriter:
    def __init__(self):
        self.writes: list[bytes] = []
        self.closed = False

    def write(self, data: bytes):
        self.writes.append(data)

    async def drain(self):
        pass

    def close(self):
        self.closed = True


class BlockingStreamReader:
    def __init__(self):
        self.started = asyncio.Event()
        self.cancelled = asyncio.Event()

    async def readline(self):
        self.started.set()
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            self.cancelled.set()
            raise


class ExitedProcess:
    def __init__(self, reader: BlockingStreamReader):
        self.reader = reader

    async def wait(self):
        await self.reader.started.wait()
        return 0


class AsyncChunkIterator:
    def __init__(self, chunks: list[str]):
        self.chunks = chunks

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self.chunks:
            raise StopAsyncIteration
        return self.chunks.pop(0)


class FakeWebSocket:
    def __init__(self, receive_batches: list[list[str]] | None = None):
        self.sent: list[tuple[str, bool]] = []
        self.receive_batches = receive_batches or []
        self.closed = False

    async def send(self, data, text: bool = False):
        self.sent.append((data, text))

    def recv_streaming(self, decode: bool = False):
        return AsyncChunkIterator(self.receive_batches.pop(0))

    async def close(self):
        self.closed = True


async def test_stdio_connection_sends_small_message_with_newline():
    writer = FakeStreamWriter()
    connection = StdioConnection(FakeStreamReader([]), writer)

    await connection.send('{"ok": true}')

    assert writer.writes == [b'{"ok": true}\n']


async def test_stdio_connection_sends_large_message_as_json_chunks():
    writer = FakeStreamWriter()
    connection = StdioConnection(FakeStreamReader([]), writer, chunk_size=4)

    await connection.send("abcdefghi")

    payloads = [json.loads(line.decode()) for line in writer.writes]
    assert payloads[0] == {"type": "chunk_start", "total_size": 9}
    assert payloads[1:4] == [
        {"type": "chunk_data", "data": "abcd", "offset": 0},
        {"type": "chunk_data", "data": "efgh", "offset": 4},
        {"type": "chunk_data", "data": "i", "offset": 8},
    ]
    assert payloads[4] == {"type": "chunk_end"}


async def test_stdio_only_first_send_can_bypass_blocking_executor(monkeypatch):
    writer = FakeStreamWriter()
    calls = []

    async def run_ordinary(fn, *args):
        calls.append((fn, args))
        return fn(*args)

    monkeypatch.setattr(
        stdio_module,
        "run_blocking_with_backpressure",
        run_ordinary,
    )
    connection = StdioConnection(
        FakeStreamReader([]),
        writer,
        chunk_size=4,
        reserve_first_message_send=True,
    )

    await connection.send("abcdefghi")
    assert calls == []
    await connection.send("second")
    assert len(calls) == 2
    assert getattr(calls[0][0], "__self__", None) == "second"
    assert calls[1][0] is split_utf8_chunks


async def test_stdio_connection_rejects_excessive_outbound_fragment_count(
    monkeypatch,
):
    monkeypatch.setattr(stdio_module, "MAX_MESSAGE_FRAGMENTS", 2)
    connection = StdioConnection(
        FakeStreamReader([]),
        FakeStreamWriter(),
        chunk_size=4,
    )

    with pytest.raises(ValueError, match="too many stdio fragments"):
        await connection.send("abcdefghi")


async def test_stdio_connection_receives_json_message_after_blank_line():
    reader = FakeStreamReader([b"\n", b'{"type": "event", "id": 1}\n'])
    connection = StdioConnection(reader, FakeStreamWriter())

    assert await connection.receive() == '{"type": "event", "id": 1}'


async def test_stdio_connection_reassembles_chunked_message():
    chunk_lines = [
        {"type": "chunk_start", "total_size": 11},
        {"type": "chunk_data", "data": "hello ", "offset": 0},
        {"type": "chunk_data", "data": "world", "offset": 6},
        {"type": "chunk_end"},
    ]
    reader = FakeStreamReader(
        [json.dumps(chunk).encode() + b"\n" for chunk in chunk_lines]
    )
    connection = StdioConnection(reader, FakeStreamWriter())

    assert await connection.receive() == "hello world"


async def test_stdio_first_chunk_reassembly_stays_inline(monkeypatch):
    chunk_lines = [
        {"type": "chunk_start", "total_size": 11},
        {"type": "chunk_data", "data": "hello ", "offset": 0},
        {"type": "chunk_data", "data": "world", "offset": 6},
        {"type": "chunk_end"},
    ]
    reader = FakeStreamReader(
        [json.dumps(chunk).encode() + b"\n" for chunk in chunk_lines]
    )
    connection = StdioConnection(
        reader,
        FakeStreamWriter(),
        reserve_first_message_decode=True,
    )

    assert await connection.receive() == "hello world"


async def test_stdio_only_first_chunked_message_uses_transport_control(monkeypatch):
    messages = []
    for text in ("first", "second"):
        messages.extend(
            [
                {"type": "chunk_start", "total_size": len(text)},
                {"type": "chunk_data", "data": text, "offset": 0},
                {"type": "chunk_end"},
            ]
        )
    reader = FakeStreamReader(
        [json.dumps(chunk).encode() + b"\n" for chunk in messages]
    )
    ordinary_calls = []

    async def run_ordinary(fn, *args):
        ordinary_calls.append((fn, args))
        return fn(*args)

    monkeypatch.setattr(
        stdio_module,
        "run_blocking_with_backpressure",
        run_ordinary,
    )
    connection = StdioConnection(
        reader,
        FakeStreamWriter(),
        reserve_first_message_decode=True,
    )

    assert await connection.receive() == "first"
    assert await connection.receive() == "second"
    assert ordinary_calls == [("".join, (["second"],))]


async def test_stdio_unchunked_first_message_consumes_control_join(monkeypatch):
    lines = [
        b'{"action": "first"}\n',
        json.dumps({"type": "chunk_start", "total_size": 6}).encode() + b"\n",
        json.dumps({"type": "chunk_data", "data": "second", "offset": 0}).encode()
        + b"\n",
        json.dumps({"type": "chunk_end"}).encode() + b"\n",
    ]
    ordinary_calls = []

    async def run_ordinary(fn, *args):
        ordinary_calls.append((fn, args))
        return fn(*args)

    monkeypatch.setattr(
        stdio_module,
        "run_blocking_with_backpressure",
        run_ordinary,
    )
    connection = StdioConnection(
        FakeStreamReader(lines),
        FakeStreamWriter(),
        reserve_first_message_decode=True,
    )

    assert await connection.receive() == '{"action": "first"}'
    assert await connection.receive() == "second"
    assert ordinary_calls == [("".join, (["second"],))]


async def test_stdio_stdout_noise_does_not_consume_control_join(monkeypatch):
    lines = [
        b"plugin import noise\n",
        json.dumps({"type": "chunk_start", "total_size": 5}).encode() + b"\n",
        json.dumps({"type": "chunk_data", "data": "first", "offset": 0}).encode()
        + b"\n",
        json.dumps({"type": "chunk_end"}).encode() + b"\n",
    ]
    connection = StdioConnection(
        FakeStreamReader(lines),
        FakeStreamWriter(),
        reserve_first_message_decode=True,
    )

    assert await connection.receive() == "first"


async def test_stdio_connection_rejects_fragment_count_amplification(
    monkeypatch,
):
    monkeypatch.setattr(stdio_module, "MAX_MESSAGE_FRAGMENTS", 2)
    chunk_lines = [
        {"type": "chunk_start", "total_size": 0},
        {"type": "chunk_data", "data": "", "offset": 0},
        {"type": "chunk_data", "data": "", "offset": 0},
        {"type": "chunk_data", "data": "", "offset": 0},
    ]
    reader = FakeStreamReader(
        [json.dumps(chunk).encode() + b"\n" for chunk in chunk_lines]
    )
    connection = StdioConnection(reader, FakeStreamWriter())

    with pytest.raises(ConnectionClosedError):
        await connection.receive()


async def test_stdio_connection_close_closes_writer():
    writer = FakeStreamWriter()
    connection = StdioConnection(FakeStreamReader([]), writer)

    await connection.close()

    assert writer.closed is True


async def test_stdio_process_exit_cancels_pending_readline():
    reader = BlockingStreamReader()
    connection = StdioConnection(
        reader,
        FakeStreamWriter(),
        process=ExitedProcess(reader),
    )

    with pytest.raises(ConnectionClosedError):
        await connection.receive()

    assert reader.cancelled.is_set()


async def test_stdio_receive_cancellation_does_not_orphan_readline():
    reader = BlockingStreamReader()
    connection = StdioConnection(reader, FakeStreamWriter())
    receive_task = asyncio.create_task(connection.receive())
    await reader.started.wait()

    receive_task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await receive_task

    assert reader.cancelled.is_set()


async def test_websocket_connection_sends_small_message_directly():
    websocket = FakeWebSocket()
    connection = WebSocketConnection(websocket)

    await connection.send('{"ok": true}')

    assert websocket.sent == [('{"ok": true}', True)]


async def test_websocket_connection_sends_large_message_in_chunks():
    websocket = FakeWebSocket()
    connection = WebSocketConnection(websocket, chunk_size=4)

    await connection.send("abcdefghi")

    assert websocket.sent == [(["abcd", "efgh", "i"], False)]


async def test_websocket_connection_rejects_excessive_outbound_fragment_count(
    monkeypatch,
):
    monkeypatch.setattr(ws_module, "MAX_MESSAGE_FRAGMENTS", 2)
    connection = WebSocketConnection(FakeWebSocket(), chunk_size=4)

    with pytest.raises(ValueError, match="too many WebSocket fragments"):
        await connection.send("abcdefghi")


async def test_websocket_connection_receives_streamed_json_message():
    websocket = FakeWebSocket(receive_batches=[['{"ok": ', "true}"]])
    connection = WebSocketConnection(websocket)

    assert await connection.receive() == '{"ok": true}'


async def test_websocket_connection_rejects_fragment_count_amplification(
    monkeypatch,
):
    monkeypatch.setattr(ws_module, "MAX_MESSAGE_FRAGMENTS", 2)
    websocket = FakeWebSocket(receive_batches=[["", "", ""]])
    connection = WebSocketConnection(websocket)

    with pytest.raises(ConnectionClosedError):
        await connection.receive()

    assert websocket.closed is True


async def test_websocket_connection_returns_one_malformed_message_at_a_time():
    websocket = FakeWebSocket(receive_batches=[["not-json"], ['{"ok": true}']])
    connection = WebSocketConnection(websocket)

    assert await connection.receive() == "not-json"
    assert await connection.receive() == '{"ok": true}'


async def test_websocket_connection_close_closes_socket():
    websocket = FakeWebSocket()
    connection = WebSocketConnection(websocket)

    await connection.close()

    assert websocket.closed is True


def test_split_utf8_chunks_respects_byte_limit():
    chunks = split_utf8_chunks("a你b好", 4)

    assert "".join(chunks) == "a你b好"
    assert all(len(chunk.encode("utf-8")) <= 4 for chunk in chunks)


def test_split_utf8_chunks_rejects_impossible_limit():
    with pytest.raises(ValueError, match="UTF-8 code point"):
        split_utf8_chunks("你", 2)


def _reference_utf8_chunks(message, max_bytes):
    if max_bytes <= 0:
        raise ValueError("max_bytes must be positive")
    chunks, current = [], []
    current_size = 0
    for char in message:
        char_size = len(char.encode("utf-8"))
        if char_size > max_bytes:
            raise ValueError("max_bytes is smaller than one UTF-8 code point")
        if current and current_size + char_size > max_bytes:
            chunks.append("".join(current))
            current, current_size = [], 0
        current.append(char)
        current_size += char_size
    if current:
        chunks.append("".join(current))
    return chunks


def test_split_utf8_chunks_matches_reference_unicode_boundaries():
    import random

    randomizer = random.Random(2716)
    alphabet = [
        "a",
        "\x00",
        "\x7f",
        "\u0080",
        "\u07ff",
        "\u0800",
        "你",
        "\uffff",
        "\U00010000",
        "😀",
        "\U0010ffff",
    ]
    messages = ["", "a你b好", "a" * 65537, "a你😀" * 12000]
    for _ in range(200):
        messages.append(
            "".join(randomizer.choices(alphabet, k=randomizer.randrange(400)))
        )
    for message in messages:
        for limit in [1, 2, 3, 4, 5, 7, 64, 16384, 65536]:
            try:
                expected = _reference_utf8_chunks(message, limit)
            except ValueError as error:
                with pytest.raises(type(error), match=str(error)):
                    split_utf8_chunks(message, limit)
            else:
                assert split_utf8_chunks(message, limit) == expected


@pytest.mark.parametrize(
    "message", ["", "abc", "你😀", "abc\ud800", "你\ud800", "\ud800\udfff"]
)
@pytest.mark.parametrize(
    "limit", [-1, 0, False, True, 0.5, 2, 4, 4.5, float("inf"), float("nan"), None, "4"]
)
def test_split_utf8_chunks_preserves_invalid_input_errors(message, limit):
    try:
        expected = _reference_utf8_chunks(message, limit)
    except (ValueError, TypeError) as error:
        with pytest.raises(type(error)) as caught:
            split_utf8_chunks(message, limit)
        assert caught.value.args == error.args
    else:
        assert split_utf8_chunks(message, limit) == expected
