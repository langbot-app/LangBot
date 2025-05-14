from __future__ import annotations

import typing

from ..core import app, entities as core_entities
from . import entities, operator, errors
from ..utils import importutil

# 引入所有算子以便注册
from . import operators

importutil.import_modules_in_pkg(operators)


class CommandManager:
    """命令管理器"""

    ap: app.Application

    cmd_list: list[operator.CommandOperator]
    """
    运行时命令列表，扁平存储，各个对象包含对应的子节点引用
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
        for cls in operator.preregistered_operators:
            if cls.path in self.ap.instance_config.data['command']['privilege']:
                cls.lowest_privilege = self.ap.instance_config.data['command']['privilege'][cls.path]

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
        context: entities.ExecuteContext,
        operator_list: list[operator.CommandOperator],
        operator: operator.CommandOperator = None,
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        """执行命令"""

        found = False
        if len(context.crt_params) > 0:  # 查找下一个参数是否对应此节点的某个子节点名
            for oper in operator_list:
                if (context.crt_params[0] == oper.name or context.crt_params[0] in oper.alias) and (
                    oper.parent_class is None or oper.parent_class == operator.__class__
                ):
                    found = True

                    context.crt_command = context.crt_params[0]
                    context.crt_params = context.crt_params[1:]

                    async for ret in self._execute(context, oper.children, oper):
                        yield ret
                    break

        if not found:  # 如果下一个参数未在此节点的子节点中找到，则执行此节点或者报错
            if operator is None:
                yield entities.CommandReturn(error=errors.CommandNotFoundError(context.crt_params[0]))
            else:
                if operator.lowest_privilege > context.privilege:
                    yield entities.CommandReturn(error=errors.CommandPrivilegeError(operator.name))
                else:
                    async for ret in operator.execute(context):
                        yield ret

    async def execute(
        self,
        command_text: str,
        query: core_entities.Query,
        session: core_entities.Session,
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        """执行命令"""

        privilege = 1

        if f'{query.launcher_type.value}_{query.launcher_id}' in self.ap.instance_config.data['admins']:
            privilege = 2

        ctx = entities.ExecuteContext(
            query=query,
            session=session,
            command_text=command_text,
            command='',
            crt_command='',
            params=command_text.split(' '),
            crt_params=command_text.split(' '),
            privilege=privilege,
        )

        async for ret in self._execute(ctx, self.cmd_list):
            yield ret
