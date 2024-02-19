from __future__ import annotations

import typing

from .. import operator, entities, cmdmgr, errors


@operator.operator_class(
    name='help',
    help='显示帮助',
    usage='!help\n!help <命令名称>'
)
class HelpOperator(operator.CommandOperator):
    
    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        help = self.ap.system_cfg.data['help-message']

        help += '\n发送命令 !cmd 可查看命令列表'

        yield entities.CommandReturn(text=help)
