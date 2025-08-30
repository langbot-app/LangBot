from __future__ import annotations
from typing import AsyncGenerator

from .. import operator
from langbot_plugin.api.entities.builtin.command import context as command_context


@operator.operator_class(name='func', help='查看所有已注册的内容函数', usage='!func')
class FuncOperator(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> AsyncGenerator[command_context.CommandReturn, None]:
        reply_str = '当前已启用的内容函数: \n\n'

        index = 1

        all_functions = await self.ap.tool_mgr.get_all_tools()

        for func in all_functions:
            reply_str += '{}. {}:\n{}\n\n'.format(
                index,
                func.name,
                func.description,
            )
            index += 1

        yield command_context.CommandReturn(text=reply_str)
