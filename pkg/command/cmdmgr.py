from __future__ import annotations

import typing

from ..core import app, entities as core_entities
from ..openai import entities as llm_entities
from ..openai.session import entities as session_entities
from . import entities, operator, errors

from .operators import func, plugin, default, reset, list as list_cmd, last, next, delc, resend, prompt, cfg, cmd, help, version, update


class CommandManager:
    """命令管理器
    """

    ap: app.Application

    cmd_list: list[operator.CommandOperator]

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
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
        operator: operator.CommandOperator = None
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        """执行命令
        """

        found = False
        if len(context.crt_params) > 0:
            for oper in operator_list:
                if (context.crt_params[0] == oper.name \
                    or context.crt_params[0] in oper.alias) \
                    and (oper.parent_class is None or oper.parent_class == operator.__class__):
                    found = True

                    context.crt_command = context.crt_params[0]
                    context.crt_params = context.crt_params[1:]

                    async for ret in self._execute(
                        context,
                        oper.children,
                        oper
                    ):
                        yield ret
                    break

        if not found:
            if operator is None:
                yield entities.CommandReturn(
                    error=errors.CommandNotFoundError(context.crt_params[0])
                )
            else:
                if operator.lowest_privilege > context.privilege:
                    yield entities.CommandReturn(
                        error=errors.CommandPrivilegeError(operator.name)
                    )
                else:
                    async for ret in operator.execute(context):
                        yield ret


    async def execute(
        self,
        command_text: str,
        query: core_entities.Query,
        session: session_entities.Session
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        """执行命令
        """

        privilege = 1
        if query.sender_id == self.ap.cfg_mgr.data['admin_qq'] \
            or query.sender_id in self.ap.cfg_mgr['admin_qq']:
            privilege = 2

        ctx = entities.ExecuteContext(
            query=query,
            session=session,
            command_text=command_text,
            command='',
            crt_command='',
            params=command_text.split(' '),
            crt_params=command_text.split(' '),
            privilege=privilege
        )

        async for ret in self._execute(
            ctx,
            self.cmd_list
        ):
            yield ret
