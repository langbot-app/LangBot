from __future__ import annotations

import typing

from .. import operator
from langbot_plugin.api.entities.builtin.command import context as command_context


@operator.operator_class(name='help', help='显示帮助', usage='!help\n!help <命令名称>')
class HelpOperator(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        help = 'LangBot - 大语言模型原生即时通信机器人平台\n链接：https://langbot.app'

        help += '\n发送命令 !cmd 可查看命令列表'

        yield command_context.CommandReturn(text=help)
