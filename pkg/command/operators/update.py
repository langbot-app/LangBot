from __future__ import annotations

import typing

from .. import operator, entities


@operator.operator_class(name='update', help='更新程序', usage='!update', privilege=2)
class UpdateCommand(operator.CommandOperator):
    async def execute(self, context: entities.ExecuteContext) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        yield entities.CommandReturn(text='不再支持通过命令更新，请查看 LangBot 文档。')
