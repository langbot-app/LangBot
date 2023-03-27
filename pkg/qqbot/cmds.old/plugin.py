from pkg.qqbot.cmds.model import command
import pkg.utils.context
import pkg.plugin.switch as plugin_switch

import os
import threading
import logging


def plugin_operation(cmd, params, is_admin):
    reply = []

    import pkg.plugin.host as plugin_host
    import pkg.utils.updater as updater

    plugin_list = plugin_host.__plugins__

    if len(params) == 0:
        reply_str = "[bot]所有插件({}):\n".format(len(plugin_host.__plugins__))
        idx = 0
        for key in plugin_host.iter_plugins_name():
            plugin = plugin_list[key]
            reply_str += "\n#{} {} {}\n{}\nv{}\n作者: {}\n"\
                .format((idx+1), plugin['name'],
                        "[已禁用]" if not plugin['enabled'] else "",
                        plugin['description'],
                        plugin['version'], plugin['author'])

            if updater.is_repo("/".join(plugin['path'].split('/')[:-1])):
                remote_url = updater.get_remote_url("/".join(plugin['path'].split('/')[:-1]))
                if remote_url != "https://github.com/RockChinQ/QChatGPT" and remote_url != "https://gitee.com/RockChin/QChatGPT":
                    reply_str += "源码: "+remote_url+"\n"

            idx += 1

        reply = [reply_str]
    elif params[0] == 'update':
        # 更新所有插件
        if is_admin:
            def closure():
                import pkg.utils.context
                updated = []
                for key in plugin_list:
                    plugin = plugin_list[key]
                    if updater.is_repo("/".join(plugin['path'].split('/')[:-1])):
                        success = updater.pull_latest("/".join(plugin['path'].split('/')[:-1]))
                        if success:
                            updated.append(plugin['name'])

                # 检查是否有requirements.txt
                pkg.utils.context.get_qqbot_manager().notify_admin("正在安装依赖...")
                for key in plugin_list:
                    plugin = plugin_list[key]
                    if os.path.exists("/".join(plugin['path'].split('/')[:-1])+"/requirements.txt"):
                        logging.info("{}检测到requirements.txt，安装依赖".format(plugin['name']))
                        import pkg.utils.pkgmgr
                        pkg.utils.pkgmgr.install_requirements("/".join(plugin['path'].split('/')[:-1])+"/requirements.txt")

                        import main
                        main.reset_logging()

                pkg.utils.context.get_qqbot_manager().notify_admin("已更新插件: {}".format(", ".join(updated)))

            threading.Thread(target=closure).start()
            reply = ["[bot]正在更新所有插件，请勿重复发起..."]
        else:
            reply = ["[bot]err:权限不足"]
    elif params[0] == 'del' or params[0] == 'delete':
        if is_admin:
            if len(params) < 2:
                reply = ["[bot]err:未指定插件名"]
            else:
                plugin_name = params[1]
                if plugin_name in plugin_list:
                    unin_path = plugin_host.uninstall_plugin(plugin_name)
                    reply = ["[bot]已删除插件: {} ({}), 请发送 !reload 重载插件".format(plugin_name, unin_path)]
                else:
                    reply = ["[bot]err:未找到插件: {}, 请使用!plugin指令查看插件列表".format(plugin_name)]
        else:
            reply = ["[bot]err:权限不足，请使用管理员账号私聊发起"]
    elif params[0] == 'on' or params[0] == 'off' :
        new_status = params[0] == 'on'
        if is_admin:
            if len(params) < 2:
                reply = ["[bot]err:未指定插件名"]
            else:
                plugin_name = params[1]
                if plugin_name in plugin_list:
                    plugin_list[plugin_name]['enabled'] = new_status
                    plugin_switch.dump_switch()
                    reply = ["[bot]已{}插件: {}".format("启用" if new_status else "禁用", plugin_name)]
                else:
                    reply = ["[bot]err:未找到插件: {}, 请使用!plugin指令查看插件列表".format(plugin_name)]
        else:
            reply = ["[bot]err:权限不足，请使用管理员账号私聊发起"]
    elif params[0].startswith("http"):
        if is_admin:

            def closure():
                try:
                    plugin_host.install_plugin(params[0])
                    pkg.utils.context.get_qqbot_manager().notify_admin("插件安装成功，请发送 !reload 指令重载插件")
                except Exception as e:
                    logging.error("插件安装失败:{}".format(e))
                    pkg.utils.context.get_qqbot_manager().notify_admin("插件安装失败:{}".format(e))

            threading.Thread(target=closure, args=()).start()
            reply = ["[bot]正在安装插件..."]
        else:
            reply = ["[bot]err:权限不足，请使用管理员账号私聊发起"]
    else:
        reply = ["[bot]err:未知参数: {}".format(params)]

    return reply


@command(
    "plugin",
    "插件相关操作",
    "!plugin\n!plugin <插件仓库地址>\!plugin update\n!plugin del <插件名>\n!plugin on <插件名>\n!plugin off <插件名>",
    [],
    False
)
def cmd_plugin(cmd: str, params: list, session_name: str,
                text_message: str, launcher_type: str, launcher_id: int,
                 sender_id: int, is_admin: bool) -> list:
    """插件相关操作"""
    reply = plugin_operation(cmd, params, is_admin)
    return reply