from __future__ import annotations

import typing

from .. import operator, entities


@operator.operator_class(name='help', help='显示帮助', usage='!help\n!help <命令名称>')
class HelpOperator(operator.CommandOperator):
    async def execute(self, context: entities.ExecuteContext) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        help = 'LangBot - 大语言模型原生即时通信机器人平台\n链接：https://langbot.app'

        help += '\n发送命令 !cmd 可查看命令列表'

        yield entities.CommandReturn(text=help)
