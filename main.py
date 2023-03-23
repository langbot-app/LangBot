import importlib
import os
import shutil
import threading
import time

import logging
import sys

try:
    import colorlog
except ImportError:
    # 尝试安装
    import pkg.utils.pkgmgr as pkgmgr
    pkgmgr.install_requirements("requirements.txt")
    try:
        import colorlog
    except ImportError:
        print("依赖不满足,请查看 https://github.com/RockChinQ/qcg-installer/issues/15")
        sys.exit(1)
import colorlog

import requests
import websockets.exceptions
from urllib3.exceptions import InsecureRequestWarning
import pkg.utils.context

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


def ensure_dependencies():
    import pkg.utils.pkgmgr as pkgmgr
    pkgmgr.run_pip(["install", "openai", "Pillow", "--upgrade",
                    "-i", "https://pypi.douban.com/simple/",
                    "--trusted-host", "pypi.douban.com"])


known_exception_caught = False

log_file_name = "qchatgpt.log"


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

    if pkg.utils.context.context['logger_handler'] is not None:
        logging.getLogger().removeHandler(pkg.utils.context.context['logger_handler'])

    for handler in logging.getLogger().handlers:
        logging.getLogger().removeHandler(handler)

    logging.basicConfig(level=config.logging_level,  # 设置日志输出格式
                        filename=log_file_name,  # log日志输出的文件位置和文件名
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
    pkg.utils.context.context['logger_handler'] = sh
    return sh


# 临时函数，用于加载config和上下文，未来统一放在config类
def load_config():
    # 完整性校验
    is_integrity = True
    config_template = importlib.import_module('config-template')
    config = importlib.import_module('config')
    for key in dir(config_template):
        if not key.startswith("__") and not hasattr(config, key):
            setattr(config, key, getattr(config_template, key))
            logging.warning("[{}]不存在".format(key))
            is_integrity = False
    if not is_integrity:
        logging.warning("配置文件不完整，请依据config-template.py检查config.py")
        logging.warning("以上配置已被设为默认值，将在5秒后继续启动... ")
        time.sleep(5)

    # 存进上下文
    pkg.utils.context.set_config(config)


def start(first_time_init=False):
    """启动流程，reload之后会被执行"""

    global known_exception_caught
    import pkg.utils.context

    config = pkg.utils.context.get_config()
    # 更新openai库到最新版本
    if not hasattr(config, 'upgrade_dependencies') or config.upgrade_dependencies:
        print("正在更新依赖库，请等待...")
        if not hasattr(config, 'upgrade_dependencies'):
            print("这个操作不是必须的,如果不想更新,请在config.py中添加upgrade_dependencies=False")
        else:
            print("这个操作不是必须的,如果不想更新,请在config.py中将upgrade_dependencies设置为False")
        try:
            ensure_dependencies()
        except Exception as e:
            print("更新openai库失败:{}, 请忽略或自行更新".format(e))

    known_exception_caught = False
    try:

        sh = reset_logging()

        pkg.utils.context.context['logger_handler'] = sh

        # 检查是否设置了管理员
        if not (hasattr(config, 'admin_qq') and config.admin_qq != 0):
            # logging.warning("未设置管理员QQ,管理员权限指令及运行告警将无法使用,如需设置请修改config.py中的admin_qq字段")
            while True:
                try:
                    config.admin_qq = int(input("未设置管理员QQ,管理员权限指令及运行告警将无法使用,请输入管理员QQ号: "))
                    # 写入到文件

                    # 读取文件
                    config_file_str = ""
                    with open("config.py", "r", encoding="utf-8") as f:
                        config_file_str = f.read()
                    # 替换
                    config_file_str = config_file_str.replace("admin_qq = 0", "admin_qq = " + str(config.admin_qq))
                    # 写入
                    with open("config.py", "w", encoding="utf-8") as f:
                        f.write(config_file_str)

                    print("管理员QQ已设置，如需修改请修改config.py中的admin_qq字段")
                    time.sleep(4)
                    break
                except ValueError:
                    print("请输入数字")

        import pkg.openai.manager
        import pkg.database.manager
        import pkg.openai.session
        import pkg.qqbot.manager
        import pkg.openai.dprompt

        pkg.openai.dprompt.read_prompt_from_file()

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

        # 加载插件
        import pkg.plugin.host
        pkg.plugin.host.load_plugins()

        pkg.plugin.host.initialize_plugins()

        if first_time_init:  # 不是热重载之后的启动,则启动新的bot线程

            import mirai.exceptions

            def run_bot_wrapper():
                global known_exception_caught
                try:
                    qqbot.bot.run()
                except TypeError as e:
                    if str(e).__contains__("argument 'debug'"):
                        logging.error(
                            "连接bot失败:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/82".format(e))
                        known_exception_caught = True
                    elif str(e).__contains__("As of 3.10, the *loop*"):
                        logging.error(
                            "Websockets版本过低:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/5".format(e))
                        known_exception_caught = True

                except websockets.exceptions.InvalidStatus as e:
                    logging.error(
                        "mirai-api-http端口无法使用:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/22".format(
                            e))
                    known_exception_caught = True
                except mirai.exceptions.NetworkError as e:
                    logging.error("连接mirai-api-http失败:{}, 请检查是否已按照文档启动mirai".format(e))
                    known_exception_caught = True
                except Exception as e:
                    if str(e).__contains__("404"):
                        logging.error(
                            "mirai-api-http端口无法使用:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/22".format(
                                e))
                        known_exception_caught = True
                    elif str(e).__contains__("signal only works in main thread"):
                        logging.error(
                            "hypercorn异常:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/86".format(
                                e))
                        known_exception_caught = True
                    elif str(e).__contains__("did not receive a valid HTTP"):
                        logging.error(
                            "mirai-api-http端口无法使用:{}, 解决方案: https://github.com/RockChinQ/QChatGPT/issues/22".format(
                                e))
                    else:
                        logging.error(
                            "捕捉到未知异常:{}, 请前往 https://github.com/RockChinQ/QChatGPT/issues 查找或提issue".format(e))
                        known_exception_caught = True
                        raise e
                finally:
                    time.sleep(12)
            threading.Thread(
                target=run_bot_wrapper
            ).start()
            # 机器人暂时不能放在线程池中
            # pkg.utils.context.get_thread_ctl().submit_sys_task(
            #     run_bot_wrapper
            # )
    finally:
        if first_time_init:
            if not known_exception_caught:
                logging.info('程序启动完成,如长时间未显示 ”成功登录到账号xxxxx“ ,并且不回复消息,请查看 '
                             'https://github.com/RockChinQ/QChatGPT/issues/37')
            else:
                sys.exit(1)
        else:
            logging.info('热重载完成')

    # 发送赞赏码
    if hasattr(config, 'encourage_sponsor_at_start') \
        and config.encourage_sponsor_at_start \
        and pkg.utils.context.get_openai_manager().audit_mgr.get_total_text_length() >= 2048:

        logging.info("发送赞赏码")
        from mirai import MessageChain, Plain, Image
        import pkg.utils.constants
        message_chain = MessageChain([
            Plain("自2022年12月初以来，开发者已经花费了大量时间和精力来维护本项目，如果您觉得本项目对您有帮助，欢迎赞赏开发者，"
                  "以支持项目稳定运行😘"),
            Image(base64=pkg.utils.constants.alipay_qr_b64),
            Image(base64=pkg.utils.constants.wechat_qr_b64),
            Plain("BTC: 3N4Azee63vbBB9boGv9Rjf4N5SocMe5eCq\nXMR: 89LS21EKQuDGkyQoe2nDupiuWXk4TVD6FALvSKv5owfmeJEPFpHeMsZLYtLiJ6GxLrhsRe5gMs6MyMSDn4GNQAse2Mae4KE\n\n"),
            Plain("(本消息仅在启动时发送至管理员，如果您不想再看到此消息，请在config.py中将encourage_sponsor_at_start设置为False)")
        ])
        pkg.utils.context.get_qqbot_manager().notify_admin_message_chain(message_chain)

    time.sleep(5)
    import pkg.utils.updater
    try:
        if pkg.utils.updater.is_new_version_available():
            pkg.utils.context.get_qqbot_manager().notify_admin("新版本可用，请发送 !update 进行自动更新\n更新日志:\n{}".format("\n".join(pkg.utils.updater.get_rls_notes())))
        else:
            logging.info("当前已是最新版本")

    except Exception as e:
        logging.warning("检查更新失败:{}".format(e))


def stop():
    import pkg.qqbot.manager
    import pkg.openai.session
    try:
        import pkg.plugin.host
        pkg.plugin.host.unload_plugins()

        qqbot_inst = pkg.utils.context.get_qqbot_manager()
        assert isinstance(qqbot_inst, pkg.qqbot.manager.QQBotManager)

        for session in pkg.openai.session.sessions:
            logging.info('持久化session: %s', session)
            pkg.openai.session.sessions[session].persistence()
        pkg.utils.context.get_database_manager().close()
    except Exception as e:
        if not isinstance(e, KeyboardInterrupt):
            raise e


def check_file():
    # 配置文件存在性校验
    if not os.path.exists('config.py'):
        shutil.copy('config-template.py', 'config.py')
        print('请先在config.py中填写配置')
        sys.exit(0)

    # 检查是否有banlist.py,如果没有就把banlist-template.py复制一份
    if not os.path.exists('banlist.py'):
        shutil.copy('banlist-template.py', 'banlist.py')

    # 检查是否有sensitive.json
    if not os.path.exists("sensitive.json"):
        shutil.copy("sensitive-template.json", "sensitive.json")

    # 检查temp目录
    if not os.path.exists("temp/"):
        os.mkdir("temp/")

    # 检查并创建plugins、prompts目录
    check_path = ["plugins", "prompts"]
    for path in check_path:
        if not os.path.exists(path):
            os.mkdir(path)


def main():
    # 初始化相关文件
    check_file()

    # 初始化logging
    init_runtime_log_file()
    pkg.utils.context.context['logger_handler'] = reset_logging()

    # 加载配置
    load_config()
    config = pkg.utils.context.get_config()

    # 配置线程池
    from pkg.utils import ThreadCtl
    thread_ctl = ThreadCtl(
        sys_pool_num=config.sys_pool_num,
        admin_pool_num=config.admin_pool_num,
        user_pool_num=config.user_pool_num
    )
    # 存进上下文
    pkg.utils.context.set_thread_ctl(thread_ctl)

    # 启动指令处理
    if len(sys.argv) > 1 and sys.argv[1] == 'init_db':
        init_db()
        sys.exit(0)

    elif len(sys.argv) > 1 and sys.argv[1] == 'update':
        print("正在进行程序更新...")
        import pkg.utils.updater as updater
        updater.update_all(cli=True)
        sys.exit(0)

    # 关闭urllib的http警告
    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)

    pkg.utils.context.get_thread_ctl().submit_sys_task(
        start,
        True
    )

    # 主线程循环
    while True:
        try:
            time.sleep(0xFF)
        except:
            stop()
            pkg.utils.context.get_thread_ctl().shutdown()
            import platform
            if platform.system() == 'Windows':
                cmd = "taskkill /F /PID {}".format(os.getpid())
            elif platform.system() in ['Linux', 'Darwin']:
                cmd = "kill -9 {}".format(os.getpid())
            os.system(cmd)


if __name__ == '__main__':
    main()

