import logging
import logging.handlers
import os
import sys
import time

import colorlog

from ...utils import constants


log_colors_config = {
    'DEBUG': 'green',  # cyan white
    'INFO': 'white',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'cyan',
}

# Log rotation configuration to prevent unbounded log file growth
LOG_FILE_MAX_BYTES = 10 * 1024 * 1024  # 10MB per file
LOG_FILE_BACKUP_COUNT = 5  # Keep 5 backup files (total ~50MB max)

LOG_DIR = 'data/logs'


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

    def __init__(self, log_dir: str, max_bytes: int, backup_count: int, encoding: str = 'utf-8'):
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
        return os.path.join(self.log_dir, 'langbot-%s.log' % date_str)

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
    # Remove all existing loggers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    level = logging.INFO

    if constants.debug_mode:
        level = logging.DEBUG

    qcg_logger = logging.getLogger('langbot')

    qcg_logger.setLevel(level)

    color_formatter = colorlog.ColoredFormatter(
        fmt='%(log_color)s[%(asctime)s.%(msecs)03d] %(filename)s (%(lineno)d) - [%(levelname)s] : %(message)s',
        datefmt='%m-%d %H:%M:%S',
        log_colors=log_colors_config,
    )

    stream_handler = logging.StreamHandler(sys.stdout)
    # stream_handler.setLevel(level)
    # stream_handler.setFormatter(color_formatter)
    stream_handler.stream = open(sys.stdout.fileno(), mode='w', encoding='utf-8', buffering=1)

    # Rotate by size within a day and switch files when the date changes,
    # so long-running processes still produce a log file for the current day.
    rotating_file_handler = DailyGroupedRotatingFileHandler(
        LOG_DIR,
        max_bytes=LOG_FILE_MAX_BYTES,
        backup_count=LOG_FILE_BACKUP_COUNT,
        encoding='utf-8',
    )

    log_handlers: list[logging.Handler] = [
        stream_handler,
        rotating_file_handler,
    ]
    log_handlers += extra_handlers if extra_handlers is not None else []

    for handler in log_handlers:
        handler.setLevel(level)
        handler.setFormatter(color_formatter)
        qcg_logger.addHandler(handler)

    qcg_logger.debug('Logging initialized, log level: %s' % level)
    logging.basicConfig(
        level=logging.CRITICAL,  # Set log output format
        format='[DEPR][%(asctime)s.%(msecs)03d] %(pathname)s (%(lineno)d) - [%(levelname)s] :\n%(message)s',
        # Log output format
        # -8 is a placeholder, left-align the output, and output length is 8
        datefmt='%Y-%m-%d %H:%M:%S',  # Time output format
        handlers=[logging.NullHandler()],
    )

    return qcg_logger
