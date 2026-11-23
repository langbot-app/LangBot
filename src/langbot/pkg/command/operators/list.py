# from __future__ import annotations

# import typing

# from .. import operator
# from langbot_plugin.api.entities.builtin.command import context as command_context, errors as command_errors


# @operator.operator_class(name='list', help='列出此会话中的所有历史对话', usage='!list\n!list <页码>')
# class ListOperator(operator.CommandOperator):
#     async def execute(
#         self, context: command_context.ExecuteContext
#     ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
#         page = 0

#         if len(context.crt_params) > 0:
#             try:
#                 page = int(context.crt_params[0] - 1)
#             except Exception:
#                 yield command_context.CommandReturn(error=command_errors.CommandOperationError('页码应为整数'))
#                 return

#         record_per_page = 10

#         content = ''

#         index = 0

#         using_conv_index = 0

#         for conv in context.session.conversations[::-1]:
#             time_str = conv.create_time.strftime('%Y-%m-%d %H:%M:%S')

#             if conv == context.session.using_conversation:
#                 using_conv_index = index

#             if index >= page * record_per_page and index < (page + 1) * record_per_page:
#                 content += (
#                     f'{index} {time_str}: {conv.messages[0].readable_str() if len(conv.messages) > 0 else "无内容"}\n'
#                 )
#             index += 1

#         if content == '':
#             content = '无'
#         else:
#             if context.session.using_conversation is None:
#                 content += '\n当前处于新会话'
#             else:
#                 content += f'\n当前会话: {using_conv_index} {context.session.using_conversation.create_time.strftime("%Y-%m-%d %H:%M:%S")}: {context.session.using_conversation.messages[0].readable_str() if len(context.session.using_conversation.messages) > 0 else "无内容"}'

#         yield command_context.CommandReturn(text=f'第 {page + 1} 页 (时间倒序):\n{content}')
