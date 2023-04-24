import os
import time
import logging
import shutil


log_file_name = "qchatgpt.log"


log_colors_config = {
    'DEBUG': 'green',  # cyan white
    'INFO': 'white',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'cyan',
}


def init_runtime_log_file():
    """为此次运行生成日志文件
    格式: qchatgpt-yyyy-MM-dd-HH-mm-ss.log
    """
    global log_file_name

    # 检查logs目录是否存在
    if not os.path.exists("logs"):
        os.mkdir("logs")

    # 检查本目录是否有qchatgpt.log，若有，移动到logs目录
    if os.path.exists("qchatgpt.log"):
        shutil.move("qchatgpt.log", "logs/qchatgpt.legacy.log")

    log_file_name = "logs/qchatgpt-%s.log" % time.strftime("%Y-%m-%d-%H-%M-%S", time.localtime())
    

def reset_logging():
    global log_file_name

    import config
    import pkg.utils.context
    import colorlog

    if pkg.utils.context.context['logger_handler'] is not None:
        logging.getLogger().removeHandler(pkg.utils.context.context['logger_handler'])

    for handler in logging.getLogger().handlers:
        logging.getLogger().removeHandler(handler)

    logging.basicConfig(level=config.logging_level,  # 设置日志输出格式
                        filename=log_file_name,  # log日志输出的文件位置和文件名
                        format="[%(asctime)s.%(msecs)03d] %(pathname)s (%(lineno)d) - [%(levelname)s] :\n%(message)s",
                        # 日志输出的格式
                        # -8表示占位符，让输出左对齐，输出长度都为8位
                        datefmt="%Y-%m-%d %H:%M:%S"  # 时间输出的格式
                        )
    sh = logging.StreamHandler()
    sh.setLevel(config.logging_level)
    sh.setFormatter(colorlog.ColoredFormatter(
        fmt="%(log_color)s[%(asctime)s.%(msecs)03d] %(filename)s (%(lineno)d) - [%(levelname)s] : "
            "%(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
        log_colors=log_colors_config
    ))
    logging.getLogger().addHandler(sh)
    pkg.utils.context.context['logger_handler'] = sh
    return sh
