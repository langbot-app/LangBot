from pkg.qqbot.cmds.model import command
import pkg.utils.context
import pkg.utils.updater
import pkg.utils.credit as credit
import config

import logging
import os
import threading
import traceback
import json

@command(
    "help",
    "获取帮助信息",
    "!help",
    [],
    False
)
def cmd_help(cmd: str, params: list, session_name: str, 
             text_message: str, launcher_type: str, launcher_id: int,
                sender_id: int, is_admin: bool) -> list:
    """获取帮助信息"""
    return ["[bot]" + config.help_message]


@command(
    "usage",
    "获取使用情况",
    "!usage",
    [],
    False
)
def cmd_usage(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """获取使用情况"""
    reply = []

    reply_str = "[bot]各api-key使用情况:\n\n"

    api_keys = pkg.utils.context.get_openai_manager().key_mgr.api_key
    for key_name in api_keys:
        text_length = pkg.utils.context.get_openai_manager().audit_mgr \
            .get_text_length_of_key(api_keys[key_name])
        image_count = pkg.utils.context.get_openai_manager().audit_mgr \
            .get_image_count_of_key(api_keys[key_name])
        reply_str += "{}:\n - 文本长度:{}\n - 图片数量:{}\n".format(key_name, int(text_length),
                                                                    int(image_count))
        # 获取此key的额度
        try:
            http_proxy = config.openai_config["http_proxy"] if "http_proxy" in config.openai_config else None
            credit_data = credit.fetch_credit_data(api_keys[key_name], http_proxy)
            reply_str += " - 使用额度:{:.2f}/{:.2f}\n".format(credit_data['total_used'],credit_data['total_granted'])
        except Exception as e:
            logging.warning("获取额度失败:{}".format(e))

    reply = [reply_str]
    return reply


@command(
    "version",
    "查看版本信息",
    "!version",
    [],
    False
)
def cmd_version(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """查看版本信息"""
    reply = []
    
    reply_str = "[bot]当前版本:\n{}\n".format(pkg.utils.updater.get_current_version_info())
    try:
        if pkg.utils.updater.is_new_version_available():
            reply_str += "\n有新版本可用，请使用命令 !update 进行更新"
    except:
        pass

    reply = [reply_str]

    return reply


@command(
    "reload",
    "执行热重载",
    "!reload",
    [],
    True
)
def cmd_reload(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """执行热重载"""
    import pkg.utils.reloader
    def reload_task():
        pkg.utils.reloader.reload_all()

    threading.Thread(target=reload_task, daemon=True).start()


@command(
    "update",
    "更新程序",
    "!update",
    [],
    True
)
def cmd_update(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """更新程序"""
    reply = []
    import pkg.utils.updater
    import pkg.utils.reloader
    import pkg.utils.context

    def update_task():
        try:
            if pkg.utils.updater.update_all():
                pkg.utils.reloader.reload_all(notify=False)
                pkg.utils.context.get_qqbot_manager().notify_admin("更新完成")
            else:
                pkg.utils.context.get_qqbot_manager().notify_admin("无新版本")
        except Exception as e0:
            traceback.print_exc()
            pkg.utils.context.get_qqbot_manager().notify_admin("更新失败:{}".format(e0))
            return

    threading.Thread(target=update_task, daemon=True).start()

    reply = ["[bot]正在更新，请耐心等待，请勿重复发起更新..."]


def config_operation(cmd, params):
    reply = []
    config = pkg.utils.context.get_config()
    reply_str = ""
    if len(params) == 0:
        reply = ["[bot]err:请输入配置项"]
    else:
        cfg_name = params[0]
        if cfg_name == 'all':
            reply_str = "[bot]所有配置项:\n\n"
            for cfg in dir(config):
                if not cfg.startswith('__') and not cfg == 'logging':
                    # 根据配置项类型进行格式化，如果是字典则转换为json并格式化
                    if isinstance(getattr(config, cfg), str):
                        reply_str += "{}: \"{}\"\n".format(cfg, getattr(config, cfg))
                    elif isinstance(getattr(config, cfg), dict):
                        # 不进行unicode转义，并格式化
                        reply_str += "{}: {}\n".format(cfg,
                                                       json.dumps(getattr(config, cfg),
                                                                  ensure_ascii=False, indent=4))
                    else:
                        reply_str += "{}: {}\n".format(cfg, getattr(config, cfg))
            reply = [reply_str]
        elif cfg_name in dir(config):
            if len(params) == 1:
                # 按照配置项类型进行格式化
                if isinstance(getattr(config, cfg_name), str):
                    reply_str = "[bot]配置项{}: \"{}\"\n".format(cfg_name, getattr(config, cfg_name))
                elif isinstance(getattr(config, cfg_name), dict):
                    reply_str = "[bot]配置项{}: {}\n".format(cfg_name,
                                                             json.dumps(getattr(config, cfg_name),
                                                                        ensure_ascii=False, indent=4))
                else:
                    reply_str = "[bot]配置项{}: {}\n".format(cfg_name, getattr(config, cfg_name))
                reply = [reply_str]
            else:
                cfg_value = " ".join(params[1:])
                # 类型转换，如果是json则转换为字典
                if cfg_value == 'true':
                    cfg_value = True
                elif cfg_value == 'false':
                    cfg_value = False
                elif cfg_value.isdigit():
                    cfg_value = int(cfg_value)
                elif cfg_value.startswith('{') and cfg_value.endswith('}'):
                    cfg_value = json.loads(cfg_value)
                else:
                    try:
                        cfg_value = float(cfg_value)
                    except ValueError:
                        pass

                # 检查类型是否匹配
                if isinstance(getattr(config, cfg_name), type(cfg_value)):
                    setattr(config, cfg_name, cfg_value)
                    pkg.utils.context.set_config(config)
                    reply = ["[bot]配置项{}修改成功".format(cfg_name)]
                else:
                    reply = ["[bot]err:配置项{}类型不匹配".format(cfg_name)]

        else:
            reply = ["[bot]err:未找到配置项 {}".format(cfg_name)]

    return reply


@command(
    "cfg",
    "配置文件相关操作",
    "!cfg all\n!cfg <配置项名称>\n!cfg <配置项名称> <配置项新值>",
    [],
    True
)
def cmd_cfg(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """配置文件相关操作"""
    reply = config_operation(cmd, params)
    return reply
