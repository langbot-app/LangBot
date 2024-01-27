from __future__ import annotations
from typing import AsyncGenerator

from .. import operator, entities, cmdmgr
from ...plugin import host as plugin_host


@operator.operator_class(name="func", alias=[], help="查看所有以注册的内容函数")
class FuncOperator(operator.CommandOperator):
    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> AsyncGenerator[entities.CommandReturn, None]:
        reply_str = "当前已加载的内容函数: \n\n"

        index = 1
        for func in plugin_host.__callable_functions__:
            reply_str += "{}. {}{}:\n{}\n\n".format(index, ("(已禁用) " if not func['enabled'] else ""), func['name'], func['description'])
            index += 1

        yield entities.CommandReturn(
            text=reply_str
        )