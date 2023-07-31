from ..aamgr import AbstractCommandNode, Context

import os

import pkg.plugin.host as plugin_host
import pkg.utils.updater as updater


@AbstractCommandNode.register(
    parent=None,
    name="plugin",
    description="插件管理",
    usage="!plugin\n!plugin get <插件仓库地址>\n!plugin update\n!plugin del <插件名>\n!plugin on <插件名>\n!plugin off <插件名>",
    aliases=[],
    privilege=1
)
class PluginCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        reply = []
        plugin_list = plugin_host.__plugins__
        if len(ctx.params) == 0:
            # 列出所有插件
            
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
            return True, reply
        elif ctx.params[0].startswith("http"):
            reply = ["[bot]err: 此命令已弃用，请使用 !plugin get <插件仓库地址> 进行安装"]
            return True, reply
        else:
            return False, []

    
@AbstractCommandNode.register(
    parent=PluginCommand,
    name="get",
    description="安装插件",
    usage="!plugin get <插件仓库地址>",
    aliases=[],
    privilege=2
)
class PluginGetCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import threading
        import logging
        import pkg.utils.context

        if len(ctx.crt_params) == 0:
            reply = ["[bot]err: 请提供插件仓库地址"]
            return True, reply
        
        reply = []
        def closure():
            try:
                plugin_host.install_plugin(ctx.crt_params[0])
                pkg.utils.context.get_qqbot_manager().notify_admin("插件安装成功，请发送 !reload 指令重载插件")
            except Exception as e:
                logging.error("插件安装失败:{}".format(e))
                pkg.utils.context.get_qqbot_manager().notify_admin("插件安装失败:{}".format(e))

        threading.Thread(target=closure, args=()).start()
        reply = ["[bot]正在安装插件..."]
        return True, reply


@AbstractCommandNode.register(
    parent=PluginCommand,
    name="update",
    description="更新所有插件",
    usage="!plugin update",
    aliases=[],
    privilege=2
)
class PluginUpdateCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import threading
        import logging
        plugin_list = plugin_host.__plugins__

        reply = []

        if len(ctx.crt_params) > 0:
            def closure():
                try:
                    import pkg.utils.context
                    
                    updated = []

                    if ctx.crt_params[0] == 'all':
                        for key in plugin_list:
                            plugin_host.update_plugin(key)
                            updated.append(key)
                    else:
                        if ctx.crt_params[0] in plugin_list:
                            plugin_host.update_plugin(ctx.crt_params[0])
                            updated.append(ctx.crt_params[0])
                        else:
                            raise Exception("未找到插件: {}".format(ctx.crt_params[0]))

                    pkg.utils.context.get_qqbot_manager().notify_admin("已更新插件: {}, 请发送 !reload 重载插件".format(", ".join(updated)))
                except Exception as e:
                    logging.error("插件更新失败:{}".format(e))
                    pkg.utils.context.get_qqbot_manager().notify_admin("插件更新失败:{} 请尝试手动更新插件".format(e))

            reply = ["[bot]正在更新插件，请勿重复发起..."]
            threading.Thread(target=closure).start()
        else:
            reply = ["[bot]请指定要更新的插件, 或使用 !plugin update all 更新所有插件"]
        return True, reply


@AbstractCommandNode.register(
    parent=PluginCommand,
    name="del",
    description="删除插件",
    usage="!plugin del <插件名>",
    aliases=[],
    privilege=2
)
class PluginDelCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        plugin_list = plugin_host.__plugins__
        reply = []

        if len(ctx.crt_params) < 1:
            reply = ["[bot]err: 未指定插件名"]
        else:
            plugin_name = ctx.crt_params[0]
            if plugin_name in plugin_list:
                unin_path = plugin_host.uninstall_plugin(plugin_name)
                reply = ["[bot]已删除插件: {} ({}), 请发送 !reload 重载插件".format(plugin_name, unin_path)]
            else:
                reply = ["[bot]err:未找到插件: {}, 请使用!plugin指令查看插件列表".format(plugin_name)]
        
        return True, reply


@AbstractCommandNode.register(
    parent=PluginCommand,
    name="on",
    description="启用指定插件",
    usage="!plugin on <插件名>",
    aliases=[],
    privilege=2
)
@AbstractCommandNode.register(
    parent=PluginCommand,
    name="off",
    description="禁用指定插件",
    usage="!plugin off <插件名>",
    aliases=[],
    privilege=2
)
class PluginOnOffCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import pkg.plugin.switch as plugin_switch

        plugin_list = plugin_host.__plugins__
        reply = []
        
        print(ctx.params)
        new_status = ctx.params[0] == 'on'

        if len(ctx.crt_params) < 1:
            reply = ["[bot]err: 未指定插件名"]
        else:
            plugin_name = ctx.crt_params[0]
            if plugin_name in plugin_list:
                plugin_list[plugin_name]['enabled'] = new_status

                for func in plugin_host.__callable_functions__:
                    if func['name'].startswith(plugin_name+"-"):
                        func['enabled'] = new_status

                plugin_switch.dump_switch()
                reply = ["[bot]已{}插件: {}".format("启用" if new_status else "禁用", plugin_name)]
            else:
                reply = ["[bot]err:未找到插件: {}, 请使用!plugin指令查看插件列表".format(plugin_name)]
        
        return True, reply

