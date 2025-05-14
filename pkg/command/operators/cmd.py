from __future__ import annotations

import typing

from .. import operator, entities, errors


@operator.operator_class(name='cmd', help='显示命令列表', usage='!cmd\n!cmd <命令名称>')
class CmdOperator(operator.CommandOperator):
    """命令列表"""

    async def execute(self, context: entities.ExecuteContext) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        """执行"""
        if len(context.crt_params) == 0:
            reply_str = '当前所有命令: \n\n'

            for cmd in self.ap.cmd_mgr.cmd_list:
                if cmd.parent_class is None:
                    reply_str += f'{cmd.name}: {cmd.help}\n'

            reply_str += '\n使用 !cmd <命令名称> 查看命令的详细帮助'

            yield entities.CommandReturn(text=reply_str.strip())

        else:
            cmd_name = context.crt_params[0]

            cmd = None

            for _cmd in self.ap.cmd_mgr.cmd_list:
                if (cmd_name == _cmd.name or cmd_name in _cmd.alias) and (_cmd.parent_class is None):
                    cmd = _cmd
                    break

            if cmd is None:
                yield entities.CommandReturn(error=errors.CommandNotFoundError(cmd_name))
            else:
                reply_str = f'{cmd.name}: {cmd.help}\n\n'
                reply_str += f'使用方法: \n{cmd.usage}'

                yield entities.CommandReturn(text=reply_str.strip())
