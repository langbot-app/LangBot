from __future__ import annotations

import asyncio

from langbot_plugin.runtime.plugin.logbuffer import MAX_LOG_LINE_BYTES, PluginLogBuffer


def test_parses_standard_log_line_level():
    buf = PluginLogBuffer()
    buf.add_line("[06-13 10:30:00.123] main.py (45) - [INFO] : hello world")
    logs = buf.get_logs()
    assert len(logs) == 1
    assert logs[0]["level"] == "INFO"
    assert logs[0]["text"].endswith("hello world")


def test_continuation_line_inherits_level():
    buf = PluginLogBuffer()
    buf.add_line("[06-13 10:30:00.123] main.py (45) - [ERROR] : boom")
    buf.add_line("Traceback (most recent call last):")
    buf.add_line('  File "x.py", line 1, in <module>')
    logs = buf.get_logs()
    assert len(logs) == 3
    assert all(e["level"] == "ERROR" for e in logs)


def test_level_filter():
    buf = PluginLogBuffer()
    buf.add_line("[06-13 10:30:00.1] a.py (1) - [INFO] : i")
    buf.add_line("[06-13 10:30:00.2] a.py (2) - [WARNING] : w")
    buf.add_line("[06-13 10:30:00.3] a.py (3) - [ERROR] : e")
    warn_and_up = buf.get_logs(level="WARNING")
    assert [e["level"] for e in warn_and_up] == ["WARNING", "ERROR"]


def test_ring_buffer_cap():
    buf = PluginLogBuffer(max_lines=5)
    for i in range(20):
        buf.add_line(f"[06-13 10:30:00.1] a.py (1) - [INFO] : line {i}")
    logs = buf.get_logs(limit=100)
    assert len(logs) == 5
    assert logs[-1]["text"].endswith("line 19")


def test_limit():
    buf = PluginLogBuffer()
    for i in range(50):
        buf.add_line(f"[06-13 10:30:00.1] a.py (1) - [INFO] : line {i}")
    logs = buf.get_logs(limit=10)
    assert len(logs) == 10
    assert logs[-1]["text"].endswith("line 49")


def test_empty_lines_skipped():
    buf = PluginLogBuffer()
    buf.add_line("")
    buf.add_line("   \n")
    assert buf.get_logs() == []


def test_add_entry_appends_synthetic_log():
    buf = PluginLogBuffer()
    buf.add_entry("ERROR", "deferred response failed")

    logs = buf.get_logs()

    assert logs == [
        {
            "ts": logs[0]["ts"],
            "level": "ERROR",
            "text": "deferred response failed",
        }
    ]


def test_has_active_reader_reports_reader_state():
    async def run():
        reader = asyncio.StreamReader()
        buf = PluginLogBuffer()
        buf.start_reader(reader)
        assert buf.has_active_reader is True
        reader.feed_eof()
        await asyncio.sleep(0)
        return buf.has_active_reader

    assert asyncio.run(run()) is False


def test_attach_stream_reads_to_eof():
    async def run():
        reader = asyncio.StreamReader()
        reader.feed_data(b"[06-13 10:30:00.1] a.py (1) - [INFO] : streamed\n")
        reader.feed_eof()
        buf = PluginLogBuffer()
        await buf.attach_stream(reader)
        return buf.get_logs()

    logs = asyncio.run(run())
    assert len(logs) == 1
    assert logs[0]["text"].endswith("streamed")


def test_attach_stream_drains_and_clips_line_without_newline():
    async def run():
        reader = asyncio.StreamReader(limit=1024)
        reader.feed_data(b"x" * (MAX_LOG_LINE_BYTES * 3))
        reader.feed_eof()
        buf = PluginLogBuffer()
        await buf.attach_stream(reader)
        return buf.get_logs()

    logs = asyncio.run(run())
    assert len(logs) == 1
    assert logs[0]["text"].startswith("x" * 100)
    assert f"clipped at {MAX_LOG_LINE_BYTES} bytes" in logs[0]["text"]
    assert len(logs[0]["text"]) < MAX_LOG_LINE_BYTES + 100
