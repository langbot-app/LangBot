from __future__ import annotations

import typing

from ..core import app
from . import operator
from ..utils import importutil
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.pipeline.query as pipeline_query
from langbot_plugin.api.entities.builtin.command import context as command_context, errors as command_errors

# 引入所有算子以便注册
from . import operators

importutil.import_modules_in_pkg(operators)


class CommandManager:
    ap: app.Application

    cmd_list: list[operator.CommandOperator]
    """
    Runtime command list, flat storage, each object contains a reference to the corresponding child node
    """

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        # 设置各个类的路径
        def set_path(cls: operator.CommandOperator, ancestors: list[str]):
            cls.path = '.'.join(ancestors + [cls.name])
            for op in operator.preregistered_operators:
                if op.parent_class == cls:
                    set_path(op, ancestors + [cls.name])

        for cls in operator.preregistered_operators:
            if cls.parent_class is None:
                set_path(cls, [])

        # 应用命令权限配置
        # for cls in operator.preregistered_operators:
        #     if cls.path in self.ap.instance_config.data['command']['privilege']:
        #         cls.lowest_privilege = self.ap.instance_config.data['command']['privilege'][cls.path]

        # 实例化所有类
        self.cmd_list = [cls(self.ap) for cls in operator.preregistered_operators]

        # 设置所有类的子节点
        for cmd in self.cmd_list:
            cmd.children = [child for child in self.cmd_list if child.parent_class == cmd.__class__]

        # 初始化所有类
        for cmd in self.cmd_list:
            await cmd.initialize()

    async def _execute(
        self,
        context: command_context.ExecuteContext,
        operator_list: list[operator.CommandOperator],
        operator: operator.CommandOperator = None,
        bound_plugins: list[str] | None = None,
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        """执行命令"""

        command_list = await self.ap.plugin_connector.list_commands(bound_plugins)

        for command in command_list:
            if command.metadata.name == context.command:
                async for ret in self.ap.plugin_connector.execute_command(context, bound_plugins):
                    yield ret
                break
        else:
            yield command_context.CommandReturn(error=command_errors.CommandNotFoundError(context.command))

    async def execute(
        self,
        command_text: str,
        full_command_text: str,
        query: pipeline_query.Query,
        session: provider_session.Session,
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        """执行命令"""

        privilege = 1

        if f'{query.launcher_type.value}_{query.launcher_id}' in self.ap.instance_config.data['admins']:
            privilege = 2

        ctx = command_context.ExecuteContext(
            query_id=query.query_id,
            session=session,
            command_text=command_text,
            full_command_text=full_command_text,
            command='',
            crt_command='',
            params=command_text.split(' '),
            crt_params=command_text.split(' '),
            privilege=privilege,
        )

        ctx.command = ctx.params[0]

        ctx.shift()

        # Get bound plugins from query
        bound_plugins = query.variables.get('_pipeline_bound_plugins', None)

        async for ret in self._execute(ctx, self.cmd_list, bound_plugins=bound_plugins):
            yield ret
