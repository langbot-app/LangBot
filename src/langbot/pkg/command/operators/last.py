# from __future__ import annotations

# import typing


# from .. import operator
# from langbot_plugin.api.entities.builtin.command import context as command_context, errors as command_errors


# @operator.operator_class(name='last', help='切换到前一个对话', usage='!last')
# class LastOperator(operator.CommandOperator):
#     async def execute(
#         self, context: command_context.ExecuteContext
#     ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
#         if context.session.conversations:
#             # 找到当前会话的上一个会话
#             for index in range(len(context.session.conversations) - 1, -1, -1):
#                 if context.session.conversations[index] == context.session.using_conversation:
#                     if index == 0:
#                         yield command_context.CommandReturn(
#                             error=command_errors.CommandOperationError('已经是第一个对话了')
#                         )
#                         return
#                     else:
#                         context.session.using_conversation = context.session.conversations[index - 1]
#                         time_str = context.session.using_conversation.create_time.strftime('%Y-%m-%d %H:%M:%S')

#                         yield command_context.CommandReturn(
#                             text=f'已切换到上一个对话: {index} {time_str}: {context.session.using_conversation.messages[0].readable_str()}'
#                         )
#                         return
#         else:
#             yield command_context.CommandReturn(error=command_errors.CommandOperationError('当前没有对话'))
