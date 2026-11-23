from __future__ import annotations

import io
import logging
import re

from langbot_plugin.utils.log import (
    ServiceFormatter,
    build_process_log_format,
    configure_process_logging,
)


def test_build_process_log_format_supports_optional_prefix():
    assert (
        build_process_log_format()
        == "[%(asctime)s.%(msecs)03d] %(filename)s (%(lineno)d) - [%(levelname)s] : %(message)s"
    )
    assert (
        build_process_log_format("BoxRuntime")
        == "[%(asctime)s.%(msecs)03d] (BoxRuntime) %(filename)s (%(lineno)d) - [%(levelname)s] : %(message)s"
    )


def test_configure_process_logging_uses_unified_formatter():
    stream = io.StringIO()
    logger = logging.getLogger("langbot_plugin.tests.log")

    configure_process_logging(stream=stream)
    logger.info("hello logging")

    output = stream.getvalue().strip()
    assert re.match(
        r"^\[\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{6}[+-]\d{2}:\d{2}\] INFO  "
        r"\[RUNTIME.TESTS\] \S+ \(test_log.py:\d+\) \[\d+\]\[MainThread/-\]\[ws=-\]\[-\] hello logging$",
        output,
    )


def test_file_exception_is_plain_and_has_tabbed_stack():
    import sys

    try:
        raise TimeoutError()
    except TimeoutError:
        record = logging.LogRecord(
            "langbot.pkg.pipeline.x",
            logging.CRITICAL,
            "pipeline.py",
            42,
            "\x1b[31mrequest failed\x1b[0m",
            (),
            sys.exc_info(),
            "run",
        )
    text = ServiceFormatter("CORE", io.StringIO()).format(record)
    first, *stack = text.splitlines()
    assert "FATAL [CORE.PIPELINE] run (pipeline.py:42)" in first
    assert first.endswith("request failed TimeoutError: TimeoutError()")
    assert "\x1b" not in text and stack and all(line.startswith("\t") for line in stack)
