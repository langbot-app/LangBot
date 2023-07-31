import importlib
import json
import os
import shutil
import threading
import time

import logging
import sys
import traceback

sys.path.append(".")

from pkg.utils.log import init_runtime_log_file, reset_logging

try:
    import colorlog
except ImportError:
    # 尝试安装
    import pkg.utils.pkgmgr as pkgmgr
    try:
        pkgmgr.install_requirements("requirements.txt")
        pkgmgr.install_upgrade("websockets")
        import colorlog
    except ImportError:
        print("依赖不满足,请查看 https://github.com/RockChinQ/qcg-installer/issues/15")
        sys.exit(1)
import colorlog

import requests
import websockets.exceptions
from urllib3.exceptions import InsecureRequestWarning
import pkg.utils.context


# 是否使用override.json覆盖配置
# 仅在启动时提供 --override 或 -r 参数时生效
use_override = False


def init_db():
    import pkg.database.manager
    database = pkg.database.manager.DatabaseManager()

    database.initialize_database()


def ensure_dependencies():
    import pkg.utils.pkgmgr as pkgmgr
    pkgmgr.run_pip(["install", "openai", "Pillow", "nakuru-project-idk", "CallingGPT", "tiktoken", "--upgrade",
                    "-i", "https://pypi.tuna.tsinghua.edu.cn/simple",
                    "--trusted-host", "pypi.tuna.tsinghua.edu.cn"])


known_exception_caught = False


def override_config():
    import config
    # 检查override.json覆盖
    if os.path.exists("override.json") and use_override:
        override_json = json.load(open("override.json", "r", encoding="utf-8"))
        overrided = []
        for key in override_json:
            if hasattr(config, key):
                setattr(config, key, override_json[key])
                # logging.info("覆写配置[{}]为[{}]".format(key, override_json[key]))
                overrided.append(key)
            else:
                logging.error("无法覆写配置[{}]为[{}]，该配置不存在，请检查override.json是否正确".format(key, override_json[key]))
        if len(overrided) > 0:
            logging.info("已根据override.json覆写配置项: {}".format(", ".join(overrided)))


# 临时函数，用于加载config和上下文，未来统一放在config类
def load_config():
    logging.info("检查config模块完整性.")
    # 完整性校验
    non_exist_keys = []

    is_integrity = True
    config_template = importlib.import_module('config-template')
    config = importlib.import_module('config')
    for key in dir(config_template):
        if not key.startswith("__") and not hasattr(config, key):
            setattr(config, key, getattr(config_template, key))
            # logging.warning("[{}]不存在".format(key))
            non_exist_keys.append(key)
            is_integrity = False
    
    if not is_integrity:
        logging.warning("以下配置字段不存在: {}".format(", ".join(non_exist_keys)))

    # 检查override.json覆盖
    override_config()

    if not is_integrity:
        logging.warning("以上不存在的配置已被设为默认值，您可以依据config-template.py检查config.py，将在3秒后继续启动... ")
        time.sleep(3)

    # 存进上下文
    pkg.utils.context.set_config(config)


def complete_tips():
    """根据tips-custom-template模块补全tips模块的属性"""
    non_exist_keys = []

    is_integrity = True
    logging.info("检查tips模块完整性.")
    tips_template = importlib.import_module('tips-custom-template')
    tips = importlib.import_module('tips')
    for key in dir(tips_template):
        if not key.startswith("__") and not hasattr(tips, key):
            setattr(tips, key, getattr(tips_template, key))
            # logging.warning("[{}]不存在".format(key))
            non_exist_keys.append(key)
            is_integrity = False

    if not is_integrity:
        logging.warning("以下提示语字段不存在: {}".format(", ".join(non_exist_keys)))
        logging.warning("tips模块不完整，您可以依据tips-custom-template.py检查tips.py")
        logging.warning("以上配置已被设为默认值，将在3秒后继续启动... ")
        time.sleep(3)


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
            import pkg.qqbot.cmds.aamgr
            
            try:
                pkg.openai.dprompt.register_all()
                pkg.qqbot.cmds.aamgr.register_all()
                pkg.qqbot.cmds.aamgr.apply_privileges()
            except Exception as e:
                logging.error(e)
                traceback.print_exc()

            # 配置OpenAI proxy
            import openai
            openai.proxy = None  # 先重置，因为重载后可能需要清除proxy
            if "http_proxy" in config.openai_config and config.openai_config["http_proxy"] is not None:
                openai.proxy = config.openai_config["http_proxy"]

            # 配置openai api_base
            if "reverse_proxy" in config.openai_config and config.openai_config["reverse_proxy"] is not None:
                openai.api_base = config.openai_config["reverse_proxy"]

            # 主启动流程
            database = pkg.database.manager.DatabaseManager()

            database.initialize_database()

            openai_interact = pkg.openai.manager.OpenAIInteract(config.openai_config['api_key'])

            # 加载所有未超时的session
            pkg.openai.session.load_sessions()

            # 初始化qq机器人
            qqbot = pkg.qqbot.manager.QQBotManager(first_time_init=first_time_init)

            # 加载插件
            import pkg.plugin.host
            pkg.plugin.host.load_plugins()

            pkg.plugin.host.initialize_plugins()

            if first_time_init:  # 不是热重载之后的启动,则启动新的bot线程

                import mirai.exceptions

                def run_bot_wrapper():
                    global known_exception_caught
                    try:
                        logging.debug("使用账号: {}".format(qqbot.bot_account_id))
                        qqbot.adapter.run_sync()
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
                            import traceback
                            traceback.print_exc()
                            logging.error(
                                "捕捉到未知异常:{}, 请前往 https://github.com/RockChinQ/QChatGPT/issues 查找或提issue".format(e))
                            known_exception_caught = True
                            raise e
                    finally:
                        time.sleep(12)
                threading.Thread(
                    target=run_bot_wrapper
                ).start()
        except Exception as e:
            traceback.print_exc()
            if isinstance(e, KeyboardInterrupt):
                logging.info("程序被用户中止")
                sys.exit(0)
            elif isinstance(e, SyntaxError):
                logging.error("配置文件存在语法错误，请检查配置文件：\n1. 是否存在中文符号\n2. 是否已按照文件中的说明填写正确")
                sys.exit(1)
            else:
                logging.error("初始化失败:{}".format(e))
                sys.exit(1)
    finally:
        # 判断若是Windows，输出选择模式可能会暂停程序的警告
        if os.name == 'nt':
            time.sleep(2)
            logging.info("您正在使用Windows系统，若命令行窗口处于“选择”模式，程序可能会被暂停，此时请右键点击窗口空白区域使其取消选择模式。")

        time.sleep(12)
        
        if first_time_init:
            if not known_exception_caught:
                import config
                if config.msg_source_adapter == "yirimirai":
                    logging.info("QQ: {}, MAH: {}".format(config.mirai_http_api_config['qq'], config.mirai_http_api_config['host']+":"+str(config.mirai_http_api_config['port'])))
                    logging.critical('程序启动完成,如长时间未显示 "成功登录到账号xxxxx" ,并且不回复消息,解决办法(请勿到群里问): '
                                'https://github.com/RockChinQ/QChatGPT/issues/37')
                elif config.msg_source_adapter == 'nakuru':
                    logging.info("host: {}, port: {}, http_port: {}".format(config.nakuru_config['host'], config.nakuru_config['port'], config.nakuru_config['http_port']))
                    logging.critical('程序启动完成,如长时间未显示 "Protocol: connected" ,并且不回复消息,请检查config.py中的nakuru_config是否正确')
            else:
                sys.exit(1)
        else:
            logging.info('热重载完成')

    # 发送赞赏码
    if config.encourage_sponsor_at_start \
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
            logging.info("新版本可用，请发送 !update 进行自动更新\n更新日志:\n{}".format("\n".join(pkg.utils.updater.get_rls_notes())))
        else:
            # logging.info("当前已是最新版本")
            pass

    except Exception as e:
        logging.warning("检查更新失败:{}".format(e))

    try:
        import pkg.utils.announcement as announcement
        new_announcement = announcement.fetch_new()
        if len(new_announcement) > 0:
            for announcement in new_announcement:
                logging.critical("[公告]<{}> {}".format(announcement['time'], announcement['content']))
    except Exception as e:
        logging.warning("获取公告失败:{}".format(e))

    return qqbot

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
    # 检查是否有banlist.py,如果没有就把banlist-template.py复制一份
    if not os.path.exists('banlist.py'):
        shutil.copy('res/templates/banlist-template.py', 'banlist.py')

    # 检查是否有sensitive.json
    if not os.path.exists("sensitive.json"):
        shutil.copy("res/templates/sensitive-template.json", "sensitive.json")

    # 检查是否有scenario/default.json
    if not os.path.exists("scenario/default.json"):
        shutil.copy("scenario/default-template.json", "scenario/default.json")

    # 检查cmdpriv.json
    if not os.path.exists("cmdpriv.json"):
        shutil.copy("res/templates/cmdpriv-template.json", "cmdpriv.json")

    # 检查tips_custom
    if not os.path.exists("tips.py"):
        shutil.copy("tips-custom-template.py", "tips.py")

    # 检查temp目录
    if not os.path.exists("temp/"):
        os.mkdir("temp/")

    # 检查并创建plugins、prompts目录
    check_path = ["plugins", "prompts"]
    for path in check_path:
        if not os.path.exists(path):
            os.mkdir(path)

    # 配置文件存在性校验
    if not os.path.exists('config.py'):
        shutil.copy('config-template.py', 'config.py')
        print('请先在config.py中填写配置')
        sys.exit(0)


def main():
    global use_override
    # 检查是否携带了 --override 或 -r 参数
    if '--override' in sys.argv or '-r' in sys.argv:
        use_override = True

    # 初始化相关文件
    check_file()

    # 初始化logging
    init_runtime_log_file()
    pkg.utils.context.context['logger_handler'] = reset_logging()

    # 加载配置
    load_config()
    config = pkg.utils.context.get_config()

    # 检查tips模块
    complete_tips()

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

