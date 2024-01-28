from __future__ import annotations
import typing
import traceback

from .. import operator, entities, cmdmgr, errors
from ...plugin import host as plugin_host
from ...utils import updater
from ...core import app


@operator.operator_class(
    name="plugin",
    help="插件操作",
    usage="!plugin\n!plugin get <插件仓库地址>\n!plugin update\n!plugin del <插件名>\n!plugin on <插件名>\n!plugin off <插件名>"
)
class PluginOperator(operator.CommandOperator):

    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        
        plugin_list = plugin_host.__plugins__
        reply_str = "所有插件({}):\n".format(len(plugin_host.__plugins__))
        idx = 0
        for key in plugin_host.iter_plugins_name():
            plugin = plugin_list[key]
            reply_str += "\n#{} {} {}\n{}\nv{}\n作者: {}\n"\
                .format((idx+1), plugin['name'],
                        "[已禁用]" if not plugin['enabled'] else "",
                        plugin['description'],
                        plugin['version'], plugin['author'])

            # TODO 从元数据调远程地址
            # if updater.is_repo("/".join(plugin['path'].split('/')[:-1])):
            #     remote_url = updater.get_remote_url("/".join(plugin['path'].split('/')[:-1]))
            #     if remote_url != "https://github.com/RockChinQ/QChatGPT" and remote_url != "https://gitee.com/RockChin/QChatGPT":
            #         reply_str += "源码: "+remote_url+"\n"

            idx += 1

        yield entities.CommandReturn(text=reply_str)


@operator.operator_class(
    name="get",
    help="安装插件",
    privilege=2,
    parent_class=PluginOperator
)
class PluginGetOperator(operator.CommandOperator):

    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        
        if len(context.crt_params) == 0:
            yield entities.CommandReturn(error=errors.ParamNotEnoughError('请提供插件仓库地址'))
        else:
            repo = context.crt_params[0]

            yield entities.CommandReturn(text="正在安装插件...")

            try:
                plugin_host.install_plugin(repo)
                yield entities.CommandReturn(text="插件安装成功，请重启程序以加载插件")
            except Exception as e:
                traceback.print_exc()
                yield entities.CommandReturn(error=errors.CommandError("插件安装失败: "+str(e)))


@operator.operator_class(
    name="update",
    help="更新插件",
    privilege=2,
    parent_class=PluginOperator
)
class PluginUpdateOperator(operator.CommandOperator):

    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        
        if len(context.crt_params) == 0:
            yield entities.CommandReturn(error=errors.ParamNotEnoughError('请提供插件名称'))
        else:
            plugin_name = context.crt_params[0]

            try:
                plugin_path_name = plugin_host.get_plugin_path_name_by_plugin_name(plugin_name)

                if plugin_path_name is not None:
                    yield entities.CommandReturn(text="正在更新插件...")
                    plugin_host.update_plugin(plugin_name)
                    yield entities.CommandReturn(text="插件更新成功，请重启程序以加载插件")
                else:
                    yield entities.CommandReturn(error=errors.CommandError("插件更新失败: 未找到插件"))
            except Exception as e:
                traceback.print_exc()
                yield entities.CommandReturn(error=errors.CommandError("插件更新失败: "+str(e)))

@operator.operator_class(
    name="all",
    help="更新所有插件",
    privilege=2,
    parent_class=PluginUpdateOperator
)
class PluginUpdateAllOperator(operator.CommandOperator):

    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:

        try:
            plugins = []

            for key in plugin_host.__plugins__:
                plugins.append(key)

            if plugins:
                yield entities.CommandReturn(text="正在更新插件...")
                updated = []
                try:
                    for plugin_name in plugins:
                        plugin_host.update_plugin(plugin_name)
                        updated.append(plugin_name)
                except Exception as e:
                    traceback.print_exc()
                    yield entities.CommandReturn(error=errors.CommandError("插件更新失败: "+str(e)))
                yield entities.CommandReturn(text="已更新插件: {}".format(", ".join(updated)))
            else:
                yield entities.CommandReturn(text="没有可更新的插件")
        except Exception as e:
            traceback.print_exc()
            yield entities.CommandReturn(error=errors.CommandError("插件更新失败: "+str(e)))


@operator.operator_class(
    name="del",
    help="删除插件",
    privilege=2,
    parent_class=PluginOperator
)
class PluginDelOperator(operator.CommandOperator):

    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        
        if len(context.crt_params) == 0:
            yield entities.CommandReturn(error=errors.ParamNotEnoughError('请提供插件名称'))
        else:
            plugin_name = context.crt_params[0]

            try:
                plugin_path_name = plugin_host.get_plugin_path_name_by_plugin_name(plugin_name)

                if plugin_path_name is not None:
                    yield entities.CommandReturn(text="正在删除插件...")
                    plugin_host.uninstall_plugin(plugin_name)
                    yield entities.CommandReturn(text="插件删除成功，请重启程序以加载插件")
                else:
                    yield entities.CommandReturn(error=errors.CommandError("插件删除失败: 未找到插件"))
            except Exception as e:
                traceback.print_exc()
                yield entities.CommandReturn(error=errors.CommandError("插件删除失败: "+str(e)))


def update_plugin_status(plugin_name: str, new_status: bool, ap: app.Application):
    if plugin_name in plugin_host.__plugins__:
        plugin_host.__plugins__[plugin_name]['enabled'] = new_status

        for func in ap.tool_mgr.all_functions:
            if func.name.startswith(plugin_name+'-'):
                func.enable = new_status

        return True
    else:
        return False


@operator.operator_class(
    name="on",
    help="启用插件",
    privilege=2,
    parent_class=PluginOperator
)
class PluginEnableOperator(operator.CommandOperator):

    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        
        if len(context.crt_params) == 0:
            yield entities.CommandReturn(error=errors.ParamNotEnoughError('请提供插件名称'))
        else:
            plugin_name = context.crt_params[0]

            try:
                if update_plugin_status(plugin_name, True, self.ap):
                    yield entities.CommandReturn(text="已启用插件: {}".format(plugin_name))
                else:
                    yield entities.CommandReturn(error=errors.CommandError("插件状态修改失败: 未找到插件 {}".format(plugin_name)))
            except Exception as e:
                traceback.print_exc()
                yield entities.CommandReturn(error=errors.CommandError("插件状态修改失败: "+str(e)))


@operator.operator_class(
    name="off",
    help="禁用插件",
    privilege=2,
    parent_class=PluginOperator
)
class PluginDisableOperator(operator.CommandOperator):

    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        
        if len(context.crt_params) == 0:
            yield entities.CommandReturn(error=errors.ParamNotEnoughError('请提供插件名称'))
        else:
            plugin_name = context.crt_params[0]

            try:
                if update_plugin_status(plugin_name, False, self.ap):
                    yield entities.CommandReturn(text="已禁用插件: {}".format(plugin_name))
                else:
                    yield entities.CommandReturn(error=errors.CommandError("插件状态修改失败: 未找到插件 {}".format(plugin_name)))
            except Exception as e:
                traceback.print_exc()
                yield entities.CommandReturn(error=errors.CommandError("插件状态修改失败: "+str(e)))
