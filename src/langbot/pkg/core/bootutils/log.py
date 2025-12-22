import logging
import logging.handlers
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


async def init_logging(extra_handlers: list[logging.Handler] = None) -> logging.Logger:
    # Remove all existing loggers
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    level = logging.INFO

    if constants.debug_mode:
        level = logging.DEBUG

    log_file_name = 'data/logs/langbot-%s.log' % time.strftime('%Y-%m-%d', time.localtime())

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

    # Use RotatingFileHandler to prevent unbounded log file growth
    rotating_file_handler = logging.handlers.RotatingFileHandler(
        log_file_name,
        encoding='utf-8',
        maxBytes=LOG_FILE_MAX_BYTES,
        backupCount=LOG_FILE_BACKUP_COUNT,
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
