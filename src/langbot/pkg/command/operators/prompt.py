# from __future__ import annotations

# import typing

# from .. import operator
# from langbot_plugin.api.entities.builtin.command import context as command_context, errors as command_errors


# @operator.operator_class(name='prompt', help='查看当前对话的前文', usage='!prompt')
# class PromptOperator(operator.CommandOperator):
#     async def execute(
#         self, context: command_context.ExecuteContext
#     ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
#         """执行"""
#         if context.session.using_conversation is None:
#             yield command_context.CommandReturn(error=command_errors.CommandOperationError('当前没有对话'))
#         else:
#             reply_str = '当前对话所有内容:\n\n'

#             for msg in context.session.using_conversation.messages:
#                 reply_str += f'{msg.role}: {msg.content}\n'

#             yield command_context.CommandReturn(text=reply_str)
