from __future__ import annotations

import asyncio
from contextlib import contextmanager
from contextvars import ContextVar
from datetime import datetime
import logging
import os
import re
import secrets
import sys
import threading
from typing import TextIO

DEFAULT_LOG_DATEFMT = "%m-%d %H:%M:%S"
_BASE_LOG_FORMAT = "[%(asctime)s.%(msecs)03d] %(filename)s (%(lineno)d) - [%(levelname)s] : %(message)s"
_PREFIXED_LOG_FORMAT = "[%(asctime)s.%(msecs)03d] ({process_name}) %(filename)s (%(lineno)d) - [%(levelname)s] : %(message)s"


def build_process_log_format(process_name: str | None = None) -> str:
    if process_name:
        return _PREFIXED_LOG_FORMAT.format(process_name=process_name)
    return _BASE_LOG_FORMAT


trace_id = ContextVar("log_trace_id", default="-")
workspace_id = ContextVar("log_workspace_id", default="-")
_ANSI = re.compile(r"\x1b\[[0-?]*[ -/]*[@-~]")


@contextmanager
def log_scope(trace=None, workspace=None):
    current = trace_id.get()
    token = trace_id.set(
        trace or (current if current != "-" else "Y-" + secrets.token_hex(8))
    )
    ws_token = workspace_id.set(workspace or workspace_id.get())
    try:
        yield
    finally:
        workspace_id.reset(ws_token)
        trace_id.reset(token)


class HTTPStatusFilter(logging.Filter):
    def filter(self, record):
        if isinstance(record.args, dict):
            status = str(record.args.get("s", ""))
            record.levelno = (
                logging.ERROR
                if status.startswith("5")
                else logging.WARNING
                if status.startswith("4")
                else logging.INFO
            )
            record.levelname = logging.getLevelName(record.levelno)
        return True


class ServiceFormatter(logging.Formatter):
    def __init__(self, service: str, stream=None):
        super().__init__()
        self.service = service
        self.color = (
            stream is not None and stream.isatty() and "NO_COLOR" not in os.environ
        )

    def subsystem(self, record):
        if record.name.startswith("hypercorn."):
            return "HTTP"
        if record.name in (
            "root",
            "langbot",
            "langbot.box",
            "langbot_plugin",
        ) or record.name.startswith(("langbot.box.", "langbot_plugin.")):
            path = "/" + record.pathname.replace("\\", "/")
            for marker in ("/langbot/pkg/", "/langbot_plugin/"):
                _, found, relative = path.rpartition(marker)
                if found:
                    parts = relative.split("/")
                    if len(parts) > 1 and parts[0].upper() == self.service:
                        parts = parts[1:]
                    return parts[0].removesuffix(".py").upper() or "MAIN"
            return "MAIN"
        return record.name.removeprefix("langbot.pkg.").split(".")[0].upper()

    def format(self, record):
        module = (
            getattr(record, "log_module", None)
            or f"{self.service}.{self.subsystem(record)}"
        )
        level = {"WARNING": "WARN", "CRITICAL": "FATAL"}.get(
            record.levelname, record.levelname
        )
        now = (
            datetime.fromtimestamp(record.created)
            .astimezone()
            .isoformat(" ", timespec="microseconds")
        )
        try:
            task = asyncio.current_task()
        except RuntimeError:
            task = None
        msg = " ".join(record.getMessage().splitlines())
        stack = ""
        if record.exc_info and record.exc_info[1] is not None:
            exc = record.exc_info[1]
            summary = " ".join((str(exc) or repr(exc)).splitlines())
            msg = f"{msg} {type(exc).__name__}: {summary}".lstrip()
            stack = "".join(
                "\n\t" + line
                for line in self.formatException(record.exc_info).splitlines()
            )
        line = (
            f"[{now}] {level:<5} [{module}] {record.funcName} ({record.filename}:{record.lineno}) "
            f"[{record.process}][{record.threadName}/{task.get_name() if task else '-'}]"
            f"[ws={getattr(record, 'log_workspace_id', None) or workspace_id.get()}]"
            f"[{getattr(record, 'log_trace_id', None) or trace_id.get()}] {msg}{stack}"
        )
        line = _ANSI.sub("", line)
        if self.color:
            color = (
                31
                if record.levelno >= logging.ERROR
                else 33
                if record.levelno >= logging.WARNING
                else 37
            )
            return f"\x1b[{color}m{line}\x1b[0m"
        return line


def install_exception_logging():
    logger = logging.getLogger("unhandled")
    logging.captureWarnings(True)

    def unhandled(kind, value, tb):
        logger.error("Unhandled exception", exc_info=(kind, value, tb))

    sys.excepthook = unhandled
    threading.excepthook = lambda args: unhandled(
        args.exc_type, args.exc_value, args.exc_traceback
    )


def install_loop_logging():
    logger = logging.getLogger("asyncio")
    loop = asyncio.get_running_loop()

    def loop_error(loop, context):
        logger.error(
            context.get("message", "Unhandled asyncio exception"),
            exc_info=context.get("exception"),
        )

    loop.set_exception_handler(loop_error)


def configure_process_logging(
    *,
    level: int = logging.INFO,
    process_name: str | None = None,
    service: str = "RUNTIME",
    stream: TextIO | None = None,
) -> None:
    """Configure a consistent log format for standalone SDK entrypoints."""
    handler = logging.StreamHandler(stream)
    handler.setFormatter(ServiceFormatter(process_name or service, handler.stream))
    logging.basicConfig(level=logging.WARNING, handlers=[handler], force=True)
    logging.getLogger("langbot_plugin").setLevel(level)
    logging.getLogger("langbot.box").setLevel(level)
    if service.startswith("PLUGIN."):
        logging.getLogger().setLevel(level)
    install_exception_logging()
