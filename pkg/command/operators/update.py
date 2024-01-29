from __future__ import annotations

import typing
import traceback

from .. import operator, entities, cmdmgr, errors


@operator.operator_class(
    name="update",
    help="更新程序",
    usage='!update',
    privilege=2
)
class UpdateCommand(operator.CommandOperator):

    async def execute(
        self,
        context: entities.ExecuteContext
    ) -> typing.AsyncGenerator[entities.CommandReturn, None]:
       
        try:
            yield entities.CommandReturn(text="正在进行更新...")
            if await self.ap.ver_mgr.update_all():
                yield entities.CommandReturn(text="更新完成，请重启程序以应用更新")
            else:
                yield entities.CommandReturn(text="当前已是最新版本")
        except Exception as e:
            traceback.print_exc()
            yield entities.CommandReturn(error=errors.CommandError("更新失败: "+str(e)))