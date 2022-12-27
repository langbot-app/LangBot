import os
import shutil
import sys
import threading
import time

import logging
import colorlog

import sys

sys.path.append(".")

log_colors_config = {
    'DEBUG': 'green',  # cyan white
    'INFO': 'white',
    'WARNING': 'yellow',
    'ERROR': 'red',
    'CRITICAL': 'bold_red',
}


def init_db():
    import pkg.database.manager
    database = pkg.database.manager.DatabaseManager()

    database.initialize_database()


def main():
    # 导入config.py
    assert os.path.exists('config.py')
    import config

    logging.basicConfig(level=config.logging_level,  # 设置日志输出格式
                        filename='qchatgpt.log',  # log日志输出的文件位置和文件名
                        format="[%(asctime)s.%(msecs)03d] %(filename)s (%(lineno)d) - [%(levelname)s] : %(message)s",
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

    import pkg.openai.manager
    import pkg.database.manager
    import pkg.openai.session
    import pkg.qqbot.manager

    # 主启动流程
    database = pkg.database.manager.DatabaseManager()

    database.initialize_database()

    openai_interact = pkg.openai.manager.OpenAIInteract(config.openai_config['api_key'])

    # 加载所有未超时的session
    pkg.openai.session.load_sessions()

    # 初始化qq机器人
    qqbot = pkg.qqbot.manager.QQBotManager(mirai_http_api_config=config.mirai_http_api_config,
                                           timeout=config.process_message_timeout, retry=config.retry_times)

    qq_bot_thread = threading.Thread(target=qqbot.bot.run, args=(), daemon=True)
    qq_bot_thread.start()

    logging.info('程序启动完成')

    while True:
        try:
            time.sleep(86400)
        except KeyboardInterrupt:
            try:
                pkg.openai.manager.get_inst().key_mgr.dump_fee()
                for session in pkg.openai.session.sessions:
                    logging.info('持久化session: %s', session)
                    pkg.openai.session.sessions[session].persistence()
            except Exception as e:
                if not isinstance(e, KeyboardInterrupt):
                    raise e
            print("程序退出")
            sys.exit(0)


if __name__ == '__main__':
    # 检查是否有config.py,如果没有就把config-template.py复制一份,并退出程序
    if not os.path.exists('config.py'):
        shutil.copy('config-template.py', 'config.py')
        print('请先在config.py中填写配置')
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == 'init_db':
        init_db()
        sys.exit(0)

    main()
