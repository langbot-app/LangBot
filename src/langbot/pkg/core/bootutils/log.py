import logging
import logging.handlers
import os
import queue
import sys
import threading
import time

from langbot_plugin.utils.log import ServiceFormatter, install_exception_logging, install_loop_logging

from ...utils import constants


# Log rotation configuration to prevent unbounded log file growth
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10MB per file
LOG_FILE_BACKUP_COUNT = 5  # Keep 5 backup files (total ~50MB max)

LOG_DIR = 'data/logs'

CONSOLE_QUEUE_CAPACITY = 256
CONSOLE_RECORD_MAX_BYTES = 16 * 1024
CONSOLE_CLOSE_TIMEOUT = 0.2


class NonBlockingConsoleHandler(logging.Handler):
    """Isolate a stalled console from callers with at most 4 MiB of queued bytes.

    Only formatted UTF-8 bytes cross the thread boundary, so queued records do
    not retain arguments or exception frames. Overflow drops console copies;
    other handlers still receive the original records.
    """

    def __init__(self, stream, *, capacity: int = CONSOLE_QUEUE_CAPACITY):
        if capacity <= 0:
            raise ValueError('Console queue capacity must be positive')
        # Drain startup prints before the worker can fill the pipe. Otherwise
        # interpreter finalization could block flushing the original stream.
        stream.flush()
        super().__init__()
        self._queue: queue.Queue[bytes | None] = queue.Queue(maxsize=capacity)
        # logging.shutdown holds Handler.lock while joining the worker.
        self._state_lock = threading.Lock()
        self._failed = threading.Event()
        self.dropped_records = 0
        self.write_error: str | None = None
        # The worker owns this descriptor. Do not share a buffered Python stream
        # lock with the main thread or interpreter finalization.
        self._fd = os.dup(stream.fileno())
        self._worker = threading.Thread(target=self._consume, name='langbot-console-log', daemon=True)
        try:
            self._worker.start()
        except Exception:
            os.close(self._fd)
            super().close()
            raise

    def emit(self, record: logging.LogRecord) -> None:
        with self._state_lock:
            if self._closed or self._failed.is_set() or self._queue.full():
                self.dropped_records += 1
                return
            try:
                text = self.format(record)
                payload = (text[:CONSOLE_RECORD_MAX_BYTES] + '\n').encode('utf-8', errors='backslashreplace')
                if len(text) > CONSOLE_RECORD_MAX_BYTES or len(payload) > CONSOLE_RECORD_MAX_BYTES:
                    marker = b'\n[console log truncated]\n'
                    payload = (
                        payload[: CONSOLE_RECORD_MAX_BYTES - len(marker)]
                        .decode('utf-8', errors='ignore')
                        .encode('utf-8')
                        + marker
                    )
                self._queue.put_nowait(payload)
            except queue.Full:
                self.dropped_records += 1
            except Exception:
                # Logging's default handleError writes to stderr, which may
                # share the same stalled container logging driver.
                self.dropped_records += 1

    def _write(self, payload: bytes) -> None:
        remaining = memoryview(payload)
        while remaining:
            written = os.write(self._fd, remaining)
            if written == 0:
                raise OSError('Console write made no progress')
            remaining = remaining[written:]

    def _consume(self) -> None:
        reported_drops = 0
        try:
            while (payload := self._queue.get()) is not None:
                self._write(payload)
                with self._state_lock:
                    dropped = self.dropped_records
                if dropped > reported_drops:
                    self._write(
                        f'[WARNING] Console logging dropped {dropped - reported_drops} records.\n'.encode('utf-8')
                    )
                    reported_drops = dropped
        except OSError as exc:
            with self._state_lock:
                self.write_error = str(exc)
                self._failed.set()
                self.dropped_records += 1
        finally:
            os.close(self._fd)
            with self._state_lock:
                while True:
                    try:
                        if self._queue.get_nowait() is not None:
                            self.dropped_records += 1
                    except queue.Empty:
                        break

    def close(self) -> None:
        with self._state_lock:
            if self._closed:
                return
            super().close()
            # A full queue must not make shutdown wait for the writer.
            while True:
                try:
                    self._queue.put_nowait(None)
                    break
                except queue.Full:
                    try:
                        self._queue.get_nowait()
                        self.dropped_records += 1
                    except queue.Empty:
                        # The writer consumed the last record after Full;
                        # retry inserting the shutdown sentinel.
                        continue
        self._worker.join(timeout=CONSOLE_CLOSE_TIMEOUT)


class DailyGroupedRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """File handler that writes to ``data/logs/langbot-YYYY-MM-DD.log``.

    It combines two rotation triggers:

    * **Size** — within a single day the file is rotated once it exceeds
      ``maxBytes``, producing numbered backups (``langbot-DATE.log.1`` etc.),
      exactly like :class:`~logging.handlers.RotatingFileHandler`.
    * **Date** — when the local date changes, logging switches to a fresh
      ``langbot-<new date>.log`` file. This happens even within a single
      long-running process, so a bot started on day N keeps writing to that
      day's file and rolls over to day N+1's file at midnight, instead of
      appending every subsequent day's logs to the start-day file.

    The on-disk naming stays compatible with the log-retention cleanup in
    ``api/http/service/maintenance.py`` (``LOG_FILE_PATTERN``).
    """

    def __init__(self, log_dir: str, max_bytes: int, backup_count: int, encoding: str = 'utf-8', suffix: str = ''):
        self.suffix = suffix
        self.log_dir = log_dir
        self._current_date = self._today()
        super().__init__(
            self._build_path(self._current_date),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding=encoding,
        )

    @staticmethod
    def _today() -> str:
        return time.strftime('%Y-%m-%d', time.localtime())

    def _build_path(self, date_str: str) -> str:
        return os.path.join(self.log_dir, f'langbot-{date_str}.log{self.suffix}')

    def shouldRollover(self, record):
        # Roll over when the day changes, regardless of file size.
        if self._today() != self._current_date:
            return True
        return super().shouldRollover(record)

    def doRollover(self):
        today = self._today()
        if today != self._current_date:
            # Date changed: point the handler at the new day's file.
            # This is a date switch, not a size-based numbered rotation.
            if self.stream:
                self.stream.close()
                self.stream = None
            self._current_date = today
            self.baseFilename = os.path.abspath(self._build_path(today))
            if not self.delay:
                self.stream = self._open()
        else:
            # Same day, file exceeded maxBytes: numbered rotation.
            super().doRollover()


async def init_logging(extra_handlers: list[logging.Handler] = None) -> logging.Logger:
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)
        if getattr(handler, '_langbot_owned', False):
            handler.close()

    level = logging.INFO

    if constants.debug_mode:
        level = logging.DEBUG

    qcg_logger = logging.getLogger('langbot')

    for handler in qcg_logger.handlers[:]:
        qcg_logger.removeHandler(handler)
        handler.close()

    qcg_logger.setLevel(level)

    qcg_logger.propagate = True
    logging.root.setLevel(logging.WARNING)
    stream_handler = NonBlockingConsoleHandler(sys.stdout)
    stream_handler.setFormatter(ServiceFormatter('CORE', sys.stdout))
    handlers = [stream_handler]
    for suffix in ('', '.wf'):
        handler = DailyGroupedRotatingFileHandler(LOG_DIR, LOG_FILE_MAX_BYTES, LOG_FILE_BACKUP_COUNT, suffix=suffix)
        handler.setLevel(logging.WARNING if suffix else level)
        handlers.append(handler)
    handlers.extend(extra_handlers or [])
    for handler in handlers:
        if handler is not stream_handler:
            handler.setFormatter(ServiceFormatter('CORE'))
        handler._langbot_owned = True
        logging.root.addHandler(handler)
    install_exception_logging()
    install_loop_logging()
    return qcg_logger
