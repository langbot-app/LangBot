import os
import shutil
import threading
import time

import logging
import sys
try:
    import colorlog
except ImportError:
    print("未安装colorlog,请查看 https://github.com/RockChinQ/qcg-installer/issues/15")
    sys.exit(1)
import colorlog

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


def main(first_time_init=False):
    # 导入config.py
    assert os.path.exists('config.py')

    # 检查是否设置了管理员
    import config
    if not (hasattr(config, 'admin_qq') and config.admin_qq != 0):
        logging.warning("未设置管理员QQ,管理员权限指令及运行告警将无法使用,如需设置请修改config.py中的admin_qq字段")

    import pkg.utils.context
    if pkg.utils.context.context['logger_handler'] is not None:
        logging.getLogger().removeHandler(pkg.utils.context.context['logger_handler'])

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

    pkg.utils.context.context['logger_handler'] = sh
    # 主启动流程
    database = pkg.database.manager.DatabaseManager()

    database.initialize_database()

    openai_interact = pkg.openai.manager.OpenAIInteract(config.openai_config['api_key'])

    # 加载所有未超时的session
    pkg.openai.session.load_sessions()

    # 初始化qq机器人
    qqbot = pkg.qqbot.manager.QQBotManager(mirai_http_api_config=config.mirai_http_api_config,
                                           timeout=config.process_message_timeout, retry=config.retry_times,
                                           first_time_init=first_time_init)

    if first_time_init:  # 不是热重载之后的启动,则不启动新的bot线程
        qq_bot_thread = threading.Thread(target=qqbot.bot.run, args=(), daemon=True)
        qq_bot_thread.start()

    time.sleep(2)
    logging.info('程序启动完成', ',如长时间未显示 ”成功登录到账号xxxxx“ ,并且不回复消息,请查看 https://github.com/RockChinQ/QChatGPT/issues/37' if first_time_init else '')

    while True:
        try:
            time.sleep(10000)
            if qqbot != pkg.utils.context.get_qqbot_manager():  # 已经reload了
                logging.info("以前的main流程由于reload退出")
                break
        except KeyboardInterrupt:
            stop()

            print("程序退出")
            sys.exit(0)


def stop():
    import pkg.utils.context
    import pkg.qqbot.manager
    import pkg.openai.session
    try:
        qqbot_inst = pkg.utils.context.get_qqbot_manager()
        assert isinstance(qqbot_inst, pkg.qqbot.manager.QQBotManager)

        pkg.utils.context.get_openai_manager().key_mgr.dump_fee()
        for session in pkg.openai.session.sessions:
            logging.info('持久化session: %s', session)
            pkg.openai.session.sessions[session].persistence()
    except Exception as e:
        if not isinstance(e, KeyboardInterrupt):
            raise e


if __name__ == '__main__':
    # 检查是否有config.py,如果没有就把config-template.py复制一份,并退出程序
    if not os.path.exists('config.py'):
        shutil.copy('config-template.py', 'config.py')
        print('请先在config.py中填写配置')
        sys.exit(0)

    if len(sys.argv) > 1 and sys.argv[1] == 'init_db':
        init_db()
        sys.exit(0)

    elif len(sys.argv) > 1 and sys.argv[1] == 'update':
        try:
            from dulwich import porcelain
            repo = porcelain.open_repo('.')
            porcelain.pull(repo)
        except ModuleNotFoundError:
            print("dulwich模块未安装,请查看 https://github.com/RockChinQ/QChatGPT/issues/77")
        sys.exit(0)

    main(True)
