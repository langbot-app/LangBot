# from __future__ import annotations

# import typing

# from .. import operator
# from langbot_plugin.api.entities.builtin.command import context as command_context, errors as command_errors


# @operator.operator_class(name='resend', help='重发当前会话的最后一条消息', usage='!resend')
# class ResendOperator(operator.CommandOperator):
#     async def execute(
#         self, context: command_context.ExecuteContext
#     ) -> typing.AsyncGenerator[command_context.CommandReturn, None]:
#         # 回滚到最后一条用户message前
#         if context.session.using_conversation is None:
#             yield command_context.CommandReturn(error=command_errors.CommandError('当前没有对话'))
#         else:
#             conv_msg = context.session.using_conversation.messages

#             # 倒序一直删到最后一条用户message
#             while len(conv_msg) > 0 and conv_msg[-1].role != 'user':
#                 conv_msg.pop()

#             if len(conv_msg) > 0:
#                 # 删除最后一条用户message
#                 conv_msg.pop()

#             # 不重发了，提示用户已删除就行了
#             yield command_context.CommandReturn(text='已删除最后一次请求记录')
