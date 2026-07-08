# from __future__ import annotations

# import typing

# from .. import operator
# from langbot_plugin.api.entities.builtin.command import context as command_context, errors as command_errors


# @operator.operator_class(name='del', help='删除当前会话的历史记录', usage='!del <序号>\n!del all')
# class DelOperator(operator.CommandOperator):
#     async def execute(
#         self, context: command_context.ExecuteContext
#     ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
#         if context.session.conversations:
#             delete_index = 0
#             if len(context.crt_params) > 0:
#                 try:
#                     delete_index = int(context.crt_params[0])
#                 except Exception:
#                     yield command_context.CommandReturn(error=command_errors.CommandOperationError('索引必须是整数'))
#                     return

#             if delete_index < 0 or delete_index >= len(context.session.conversations):
#                 yield command_context.CommandReturn(error=command_errors.CommandOperationError('索引超出范围'))
#                 return

#             # 倒序
#             to_delete_index = len(context.session.conversations) - 1 - delete_index

#             if context.session.conversations[to_delete_index] == context.session.using_conversation:
#                 context.session.using_conversation = None

#             del context.session.conversations[to_delete_index]

#             yield command_context.CommandReturn(text=f'已删除对话: {delete_index}')
#         else:
#             yield command_context.CommandReturn(error=command_errors.CommandOperationError('当前没有对话'))


# @operator.operator_class(name='all', help='删除此会话的所有历史记录', parent_class=DelOperator)
# class DelAllOperator(operator.CommandOperator):
#     async def execute(
#         self, context: command_context.ExecuteContext
#     ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
#         context.session.conversations = []
#         context.session.using_conversation = None

#         yield command_context.CommandReturn(text='已删除所有对话')
