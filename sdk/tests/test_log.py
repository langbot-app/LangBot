from __future__ import annotations

import io
import logging
import re

from langbot_plugin.utils.log import build_process_log_format, configure_process_logging


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
        r"^\[\d{2}-\d{2} \d{2}:\d{2}:\d{2}\.\d{3}\] test_log\.py \(\d+\) - \[INFO\] : hello logging$",
        output,
    )
