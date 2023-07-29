import json
import os

import pkg.plugin.host as host
import logging


def wrapper_dict_from_runtime_context() -> dict:
    """从变量中包装settings.json的数据字典"""
    settings = {
        "order": [],
        "functions": {
            "enabled": host.__enable_content_functions__
        }
    }

    for plugin_name in host.__plugins_order__:
        settings["order"].append(plugin_name)

    return settings


def apply_settings(settings: dict):
    """将settings.json数据应用到变量中"""
    if "order" in settings:
        host.__plugins_order__ = settings["order"]

    if "functions" in settings:
        if "enabled" in settings["functions"]:
            host.__enable_content_functions__ = settings["functions"]["enabled"]
            # logging.debug("set content function enabled: {}".format(host.__enable_content_functions__))


def dump_settings():
    """保存settings.json数据"""
    logging.debug("保存plugins/settings.json数据")

    settings = wrapper_dict_from_runtime_context()

    with open("plugins/settings.json", "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=4, ensure_ascii=False)


def load_settings():
    """加载settings.json数据"""
    logging.debug("加载plugins/settings.json数据")

    # 读取plugins/settings.json
    settings = {
    }

    # 检查文件是否存在
    if not os.path.exists("plugins/settings.json"):
        # 不存在则创建
        with open("plugins/settings.json", "w", encoding="utf-8") as f:
            json.dump(wrapper_dict_from_runtime_context(), f, indent=4, ensure_ascii=False)

    with open("plugins/settings.json", "r", encoding="utf-8") as f:
        settings = json.load(f)

    if settings is None:
        settings = {
        }

    # 检查每个设置项
    if "order" not in settings:
        settings["order"] = []

    settings_modified = False

    settings_copy = settings.copy()

    # 检查settings中多余的插件项

    # order
    for plugin_name in settings_copy["order"]:
        if plugin_name not in host.__plugins_order__:
            settings["order"].remove(plugin_name)
            settings_modified = True

    # 检查settings中缺少的插件项

    # order
    for plugin_name in host.__plugins_order__:
        if plugin_name not in settings_copy["order"]:
            settings["order"].append(plugin_name)
            settings_modified = True

    if "functions" not in settings:
        settings["functions"] = {
            "enabled": host.__enable_content_functions__
        }
        settings_modified = True
    elif "enabled" not in settings["functions"]:
        settings["functions"]["enabled"] = host.__enable_content_functions__
        settings_modified = True

    logging.info("已全局{}内容函数。".format("启用" if settings["functions"]["enabled"] else "禁用"))

    apply_settings(settings)

    if settings_modified:
        dump_settings()
