from __future__ import annotations

import typing

from .. import operator, entities, errors


@operator.operator_class(name='prompt', help='查看当前对话的前文', usage='!prompt')
class PromptOperator(operator.CommandOperator):
    async def execute(self, context: entities.ExecuteContext) -> typing.AsyncGenerator[entities.CommandReturn, None]:
        """执行"""
        if context.session.using_conversation is None:
            yield entities.CommandReturn(error=errors.CommandOperationError('当前没有对话'))
        else:
            reply_str = '当前对话所有内容:\n\n'

            for msg in context.session.using_conversation.messages:
                reply_str += f'{msg.role}: {msg.content}\n'

            yield entities.CommandReturn(text=reply_str)
