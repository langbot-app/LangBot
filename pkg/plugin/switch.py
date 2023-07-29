# 控制插件的开关
import json
import logging
import os

import pkg.plugin.host as host


def wrapper_dict_from_plugin_list() -> dict:
    """将插件列表转换为开关json"""
    switch = {}

    for plugin_name in host.__plugins__:
        plugin = host.__plugins__[plugin_name]

        switch[plugin_name] = {
            "path": plugin["path"],
            "enabled": plugin["enabled"],
        }

    return switch


def apply_switch(switch: dict):
    """将开关数据应用到插件列表中"""
    # print("将开关数据应用到插件列表中")
    # print(switch)
    for plugin_name in switch:
        host.__plugins__[plugin_name]["enabled"] = switch[plugin_name]["enabled"]

        # 查找此插件的所有内容函数
        for func in host.__callable_functions__:
            if func['name'].startswith(plugin_name + '-'):
                func['enabled'] = switch[plugin_name]["enabled"]


def dump_switch():
    """保存开关数据"""
    logging.debug("保存开关数据")
    # 将开关数据写入plugins/switch.json

    switch = wrapper_dict_from_plugin_list()

    with open("plugins/switch.json", "w", encoding="utf-8") as f:
        json.dump(switch, f, indent=4, ensure_ascii=False)


def load_switch():
    """加载开关数据"""
    logging.debug("加载开关数据")
    # 读取plugins/switch.json

    switch = {}

    # 检查文件是否存在
    if not os.path.exists("plugins/switch.json"):
        # 不存在则创建
        with open("plugins/switch.json", "w", encoding="utf-8") as f:
            json.dump(switch, f, indent=4, ensure_ascii=False)

    with open("plugins/switch.json", "r", encoding="utf-8") as f:
        switch = json.load(f)

    if switch is None:
        switch = {}

    switch_modified = False

    switch_copy = switch.copy()
    # 检查switch中多余的和path不相符的
    for plugin_name in switch_copy:
        if plugin_name not in host.__plugins__:
            del switch[plugin_name]
            switch_modified = True
        elif switch[plugin_name]["path"] != host.__plugins__[plugin_name]["path"]:
            # 删除此不相符的
            del switch[plugin_name]
            switch_modified = True

    # 检查plugin中多余的
    for plugin_name in host.__plugins__:
        if plugin_name not in switch:
            switch[plugin_name] = {
                "path": host.__plugins__[plugin_name]["path"],
                "enabled": host.__plugins__[plugin_name]["enabled"],
            }
            switch_modified = True

    # 应用开关数据
    apply_switch(switch)

    # 如果switch有修改，保存
    if switch_modified:
        dump_switch()
