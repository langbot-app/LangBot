# Plugin log buffer: captures a plugin subprocess's stderr (where Python
# `logging` output is emitted) into a bounded in-memory ring buffer so that
# LangBot can display per-plugin logs on the plugin detail page.

from __future__ import annotations

import asyncio
import collections
import logging
import re
import time
import typing

logger = logging.getLogger(__name__)

# Matches the standard SDK log line produced by
# `langbot_plugin.utils.log.configure_process_logging`, e.g.:
#   [06-13 10:30:00.123] main.py (45) - [INFO] : This is an info message
# We only need the level here; the rest is kept verbatim as the message text.
_LEVEL_RE = re.compile(r"^\[[^\]]+\]\s.*?-\s\[(?P<level>[A-Z]+)\]\s:\s")

# Known logging level names, used to validate the parsed token.
_KNOWN_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}

# Default ring-buffer capacity (number of log lines retained per plugin).
DEFAULT_MAX_LINES = 1000
MAX_LOG_LINE_BYTES = 64 * 1024
_LOG_READ_CHUNK_BYTES = 64 * 1024


class PluginLogBuffer:
    """A bounded ring buffer holding recent log lines for a single plugin.

    Each entry is a dict: {"ts": float, "level": str, "text": str}.
    `level` is best-effort parsed from the line; continuation lines (e.g.
    multi-line tracebacks) inherit the previous entry's level.
    """

    def __init__(self, max_lines: int = DEFAULT_MAX_LINES) -> None:
        self._buffer: collections.deque[dict[str, typing.Any]] = collections.deque(
            maxlen=max_lines
        )
        self._last_level: str = "INFO"
        self._reader_task: asyncio.Task | None = None

    def add_line(self, raw_line: str) -> None:
        """Parse and append a single raw stderr line to the buffer."""
        text = raw_line.rstrip("\n").rstrip("\r")
        if text.strip() == "":
            return

        match = _LEVEL_RE.match(text)
        if match:
            level = match.group("level")
            if level not in _KNOWN_LEVELS:
                level = self._last_level
            else:
                self._last_level = level
        else:
            # Continuation line (traceback / multi-line message): inherit level.
            level = self._last_level

        self._buffer.append(
            {
                "ts": time.time(),
                "level": level,
                "text": text,
            }
        )

    def add_entry(self, level: str, text: str) -> None:
        """Append a synthetic log entry not read from the plugin stderr stream."""
        normalized_level = level.upper()
        if normalized_level not in _KNOWN_LEVELS:
            normalized_level = "INFO"
        self._last_level = normalized_level
        self._buffer.append(
            {
                "ts": time.time(),
                "level": normalized_level,
                "text": text,
            }
        )

    @property
    def has_active_reader(self) -> bool:
        """Whether this buffer is currently reading a plugin stderr stream."""
        return self._reader_task is not None and not self._reader_task.done()

    def get_logs(
        self,
        limit: int = 200,
        level: str | None = None,
    ) -> list[dict[str, typing.Any]]:
        """Return the most recent log entries.

        Args:
            limit: Max number of entries to return (most recent first-in-order).
            level: Optional minimum level filter (e.g. "WARNING" returns
                WARNING/ERROR/CRITICAL only). None returns all levels.
        """
        entries = list(self._buffer)

        if level:
            min_no = logging.getLevelName(level)
            if isinstance(min_no, int):
                entries = [e for e in entries if _level_no(e["level"]) >= min_no]

        if limit and limit > 0:
            entries = entries[-limit:]

        return entries

    def clear(self) -> None:
        self._buffer.clear()

    async def attach_stream(self, stream: asyncio.StreamReader) -> None:
        """Continuously drain stderr without retaining an unbounded log line."""
        pending = bytearray()
        truncated = False

        def flush_line() -> None:
            nonlocal truncated
            if not pending and not truncated:
                return
            text = bytes(pending).decode("utf-8", errors="replace")
            if truncated:
                text += f"... [log line clipped at {MAX_LOG_LINE_BYTES} bytes]"
            self.add_line(text)
            pending.clear()
            truncated = False

        try:
            while True:
                chunk = await stream.read(_LOG_READ_CHUNK_BYTES)
                if not chunk:
                    break
                offset = 0
                while offset < len(chunk):
                    newline = chunk.find(b"\n", offset)
                    end = len(chunk) if newline < 0 else newline + 1
                    part = chunk[offset:end]
                    remaining = MAX_LOG_LINE_BYTES - len(pending)
                    if remaining > 0:
                        pending.extend(part[:remaining])
                    if len(part) > remaining:
                        truncated = True
                    offset = end
                    if newline >= 0:
                        flush_line()
            flush_line()
        except Exception as e:  # noqa: BLE001 - reader must never crash the runtime
            logger.debug(f"Plugin log stream reader stopped: {e}")

    def start_reader(self, stream: asyncio.StreamReader) -> None:
        """Spawn a background task reading the given stream into the buffer."""
        if self._reader_task is not None and not self._reader_task.done():
            return
        self._reader_task = asyncio.create_task(self.attach_stream(stream))

    def stop_reader(self) -> None:
        if self._reader_task is not None and not self._reader_task.done():
            self._reader_task.cancel()
        self._reader_task = None


def _level_no(level_name: str) -> int:
    no = logging.getLevelName(level_name)
    return no if isinstance(no, int) else logging.INFO
