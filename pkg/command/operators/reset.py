from __future__ import annotations

import typing

from .. import operator
from langbot_plugin.api.entities.builtin.command import context as command_context


@operator.operator_class(name='reset', help='重置当前会话', usage='!reset')
class ResetOperator(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        """执行"""
        context.session.using_conversation = None

        yield command_context.CommandReturn(text='已重置当前会话')
