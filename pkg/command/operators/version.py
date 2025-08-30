from __future__ import annotations

import typing

from .. import operator
from langbot_plugin.api.entities.builtin.command import context as command_context


@operator.operator_class(name='version', help='显示版本信息', usage='!version')
class VersionCommand(operator.CommandOperator):
    async def execute(
        self, context: command_context.ExecuteContext
    ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
        reply_str = f'当前版本: \n{self.ap.ver_mgr.get_current_version()}'

        try:
            if await self.ap.ver_mgr.is_new_version_available():
                reply_str += '\n\n有新版本可用。'
        except Exception:
            pass

        yield command_context.CommandReturn(text=reply_str.strip())
