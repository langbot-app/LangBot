import logging
import os
import sys
import time

import colorlog


log_colors_config = {
    "DEBUG": "green",  # cyan white
    "INFO": "white",
    "WARNING": "yellow",
    "ERROR": "red",
    "CRITICAL": "cyan",
}


async def init_logging() -> logging.Logger:
    # 删除所有现有的logger
    for handler in logging.root.handlers[:]:
        logging.root.removeHandler(handler)

    level = logging.INFO

    if "DEBUG" in os.environ and os.environ["DEBUG"] in ["true", "1"]:
        level = logging.DEBUG

    log_file_name = "data/logs/qcg-%s.log" % time.strftime(
        "%Y-%m-%d-%H-%M-%S", time.localtime()
    )

    qcg_logger = logging.getLogger("qcg")

    qcg_logger.setLevel(level)

    color_formatter = colorlog.ColoredFormatter(
        fmt="%(log_color)s[%(asctime)s.%(msecs)03d] %(pathname)s (%(lineno)d) - [%(levelname)s] :\n    %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors=log_colors_config,
    )

    stream_handler = logging.StreamHandler(sys.stdout)

    log_handlers: logging.Handler = [stream_handler, logging.FileHandler(log_file_name)]

    for handler in log_handlers:
        handler.setLevel(level)
        handler.setFormatter(color_formatter)
        qcg_logger.addHandler(handler)

    qcg_logger.debug("日志初始化完成，日志级别：%s" % level)
    logging.basicConfig(
        level=logging.CRITICAL,  # 设置日志输出格式
        format="[DEPR][%(asctime)s.%(msecs)03d] %(pathname)s (%(lineno)d) - [%(levelname)s] :\n%(message)s",
        # 日志输出的格式
        # -8表示占位符，让输出左对齐，输出长度都为8位
        datefmt="%Y-%m-%d %H:%M:%S",  # 时间输出的格式
        handlers=[logging.NullHandler()],
    )

    return qcg_logger
