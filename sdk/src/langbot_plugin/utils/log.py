from __future__ import annotations

import logging
from typing import TextIO

DEFAULT_LOG_DATEFMT = "%m-%d %H:%M:%S"
_BASE_LOG_FORMAT = "[%(asctime)s.%(msecs)03d] %(filename)s (%(lineno)d) - [%(levelname)s] : %(message)s"
_PREFIXED_LOG_FORMAT = "[%(asctime)s.%(msecs)03d] ({process_name}) %(filename)s (%(lineno)d) - [%(levelname)s] : %(message)s"


def build_process_log_format(process_name: str | None = None) -> str:
    if process_name:
        return _PREFIXED_LOG_FORMAT.format(process_name=process_name)
    return _BASE_LOG_FORMAT


def configure_process_logging(
    *,
    level: int = logging.INFO,
    process_name: str | None = None,
    stream: TextIO | None = None,
) -> None:
    """Configure a consistent log format for standalone SDK entrypoints."""
    logging.basicConfig(
        level=level,
        format=build_process_log_format(process_name),
        datefmt=DEFAULT_LOG_DATEFMT,
        stream=stream,
        force=True,
    )
