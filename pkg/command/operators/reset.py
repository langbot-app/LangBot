from __future__ import annotations

import typing

from .. import operator, entities


@operator.operator_class(name='reset', help='重置当前会话', usage='!reset')
class ResetOperator(operator.CommandOperator):
    async def execute(self, context: entities.ExecuteContext) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        """执行"""
        context.session.using_conversation = None

        yield entities.CommandReturn(text='已重置当前会话')
