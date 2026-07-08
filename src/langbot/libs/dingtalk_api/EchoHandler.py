import asyncio
import dingtalk_stream  # type: ignore
from dingtalk_stream import AckMessage


class EchoTextHandler(dingtalk_stream.ChatbotHandler):
    def __init__(self, client):
        super().__init__()  # Call parent class initializer to set up logger
        self.msg_id = ''
        self.incoming_message = None
        self.client = client  # 用于更新 DingTalkClient 中的 incoming_message

    """处理钉钉消息"""

    async def process(self, callback: dingtalk_stream.CallbackMessage):
        incoming_message = dingtalk_stream.ChatbotMessage.from_dict(callback.data)
        if incoming_message.message_id != self.msg_id:
            self.msg_id = incoming_message.message_id

        await self.client.update_incoming_message(incoming_message)

        return AckMessage.STATUS_OK, 'OK'

    async def get_incoming_message(self):
        """异步等待消息的到来"""
        while self.incoming_message is None:
            await asyncio.sleep(0.1)  # 异步等待，避免阻塞

        return self.incoming_message
