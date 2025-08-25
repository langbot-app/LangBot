from __future__ import annotations
import typing
import traceback

from .. import operator
from langbot_plugin.api.entities.builtin.command import context as command_context, errors as command_errors


@operator.operator_class(
    name='plugin',
    help='插件操作',
    usage='!plugin\n!plugin get <插件仓库地址>\n!plugin update\n!plugin del <插件名>\n!plugin on <插件名>\n!plugin off <插件名>',
)
class PluginOperator(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        plugin_list = self.ap.plugin_mgr.plugins()
        reply_str = '所有插件({}):\n'.format(len(plugin_list))
        idx = 0
        for plugin in plugin_list:
            reply_str += '\n#{} {} {}\n{}\nv{}\n作者: {}\n'.format(
                (idx + 1),
                plugin.plugin_name,
                '[已禁用]' if not plugin.enabled else '',
                plugin.plugin_description,
                plugin.plugin_version,
                plugin.plugin_author,
            )

            idx += 1

        yield command_context.CommandReturn(text=reply_str)


@operator.operator_class(name='get', help='安装插件', privilege=2, parent_class=PluginOperator)
class PluginGetOperator(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        if len(context.crt_params) == 0:
            yield command_context.CommandReturn(error=command_errors.ParamNotEnoughError('请提供插件仓库地址'))
        else:
            repo = context.crt_params[0]

            yield command_context.CommandReturn(text='正在安装插件...')

            try:
                await self.ap.plugin_mgr.install_plugin(repo)
                yield command_context.CommandReturn(text='插件安装成功，请重启程序以加载插件')
            except Exception as e:
                traceback.print_exc()
                yield command_context.CommandReturn(error=command_errors.CommandError('插件安装失败: ' + str(e)))


@operator.operator_class(name='update', help='更新插件', privilege=2, parent_class=PluginOperator)
class PluginUpdateOperator(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        if len(context.crt_params) == 0:
            yield command_context.CommandReturn(error=command_errors.ParamNotEnoughError('请提供插件名称'))
        else:
            plugin_name = context.crt_params[0]

            try:
                plugin_container = self.ap.plugin_mgr.get_plugin_by_name(plugin_name)

                if plugin_container is not None:
                    yield command_context.CommandReturn(text='正在更新插件...')
                    await self.ap.plugin_mgr.update_plugin(plugin_name)
                    yield command_context.CommandReturn(text='插件更新成功，请重启程序以加载插件')
                else:
                    yield command_context.CommandReturn(error=command_errors.CommandError('插件更新失败: 未找到插件'))
            except Exception as e:
                traceback.print_exc()
                yield command_context.CommandReturn(error=command_errors.CommandError('插件更新失败: ' + str(e)))


@operator.operator_class(name='all', help='更新所有插件', privilege=2, parent_class=PluginUpdateOperator)
class PluginUpdateAllOperator(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        try:
            plugins = [p.plugin_name for p in self.ap.plugin_mgr.plugins()]

            if plugins:
                yield command_context.CommandReturn(text='正在更新插件...')
                updated = []
                try:
                    for plugin_name in plugins:
                        await self.ap.plugin_mgr.update_plugin(plugin_name)
                        updated.append(plugin_name)
                except Exception as e:
                    traceback.print_exc()
                    yield command_context.CommandReturn(error=command_errors.CommandError('插件更新失败: ' + str(e)))
                yield command_context.CommandReturn(text='已更新插件: {}'.format(', '.join(updated)))
            else:
                yield command_context.CommandReturn(text='没有可更新的插件')
        except Exception as e:
            traceback.print_exc()
            yield command_context.CommandReturn(error=command_errors.CommandError('插件更新失败: ' + str(e)))


@operator.operator_class(name='del', help='删除插件', privilege=2, parent_class=PluginOperator)
class PluginDelOperator(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        if len(context.crt_params) == 0:
            yield command_context.CommandReturn(error=command_errors.ParamNotEnoughError('请提供插件名称'))
        else:
            plugin_name = context.crt_params[0]

            try:
                plugin_container = self.ap.plugin_mgr.get_plugin_by_name(plugin_name)

                if plugin_container is not None:
                    yield command_context.CommandReturn(text='正在删除插件...')
                    await self.ap.plugin_mgr.uninstall_plugin(plugin_name)
                    yield command_context.CommandReturn(text='插件删除成功，请重启程序以加载插件')
                else:
                    yield command_context.CommandReturn(error=command_errors.CommandError('插件删除失败: 未找到插件'))
            except Exception as e:
                traceback.print_exc()
                yield command_context.CommandReturn(error=command_errors.CommandError('插件删除失败: ' + str(e)))


@operator.operator_class(name='on', help='启用插件', privilege=2, parent_class=PluginOperator)
class PluginEnableOperator(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        if len(context.crt_params) == 0:
            yield command_context.CommandReturn(error=command_errors.ParamNotEnoughError('请提供插件名称'))
        else:
            plugin_name = context.crt_params[0]

            try:
                if await self.ap.plugin_mgr.update_plugin_switch(plugin_name, True):
                    yield command_context.CommandReturn(text='已启用插件: {}'.format(plugin_name))
                else:
                    yield command_context.CommandReturn(
                        error=command_errors.CommandError('插件状态修改失败: 未找到插件 {}'.format(plugin_name))
                    )
            except Exception as e:
                traceback.print_exc()
                yield command_context.CommandReturn(error=command_errors.CommandError('插件状态修改失败: ' + str(e)))


@operator.operator_class(name='off', help='禁用插件', privilege=2, parent_class=PluginOperator)
class PluginDisableOperator(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        if len(context.crt_params) == 0:
            yield command_context.CommandReturn(error=command_errors.ParamNotEnoughError('请提供插件名称'))
        else:
            plugin_name = context.crt_params[0]

            try:
                if await self.ap.plugin_mgr.update_plugin_switch(plugin_name, False):
                    yield command_context.CommandReturn(text='已禁用插件: {}'.format(plugin_name))
                else:
                    yield command_context.CommandReturn(
                        error=command_errors.CommandError('插件状态修改失败: 未找到插件 {}'.format(plugin_name))
                    )
            except Exception as e:
                traceback.print_exc()
                yield command_context.CommandReturn(error=command_errors.CommandError('插件状态修改失败: ' + str(e)))
