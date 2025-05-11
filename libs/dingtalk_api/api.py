import base64
import json
import time
from typing import Callable
import dingtalk_stream
from .EchoHandler import EchoTextHandler
from .dingtalkevent import DingTalkEvent
import httpx
import traceback


class DingTalkClient:
    def __init__(
        self,
        client_id: str,
        client_secret: str,
        robot_name: str,
        robot_code: str,
        markdown_card: bool,
    ):
        """初始化 WebSocket 连接并自动启动"""
        self.credential = dingtalk_stream.Credential(client_id, client_secret)
        self.client = dingtalk_stream.DingTalkStreamClient(self.credential)
        self.key = client_id
        self.secret = client_secret
        # 在 DingTalkClient 中传入自己作为参数，避免循环导入
        self.EchoTextHandler = EchoTextHandler(self)
        self.client.register_callback_handler(dingtalk_stream.chatbot.ChatbotMessage.TOPIC, self.EchoTextHandler)
        self._message_handlers = {
            'example': [],
        }
        self.access_token = ''
        self.robot_name = robot_name
        self.robot_code = robot_code
        self.access_token_expiry_time = ''
        self.markdown_card = markdown_card

    async def get_access_token(self):
        url = 'https://api.dingtalk.com/v1.0/oauth2/accessToken'
        headers = {'Content-Type': 'application/json'}
        data = {'appKey': self.key, 'appSecret': self.secret}
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(url, json=data, headers=headers)
                if response.status_code == 200:
                    response_data = response.json()
                    self.access_token = response_data.get('accessToken')
                    expires_in = int(response_data.get('expireIn', 7200))
                    self.access_token_expiry_time = time.time() + expires_in - 60
            except Exception as e:
                raise Exception(e)

    async def is_token_expired(self):
        """检查token是否过期"""
        if self.access_token_expiry_time is None:
            return True
        return time.time() > self.access_token_expiry_time

    async def check_access_token(self):
        if not self.access_token or await self.is_token_expired():
            return False
        return bool(self.access_token and self.access_token.strip())

    async def download_image(self, download_code: str):
        if not await self.check_access_token():
            await self.get_access_token()
        url = 'https://api.dingtalk.com/v1.0/robot/messageFiles/download'
        params = {'downloadCode': download_code, 'robotCode': self.robot_code}
        headers = {'x-acs-dingtalk-access-token': self.access_token}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                result = response.json()
                download_url = result.get('downloadUrl')
            else:
                raise Exception(f'Error: {response.status_code}, {response.text}')

        if download_url:
            return await self.download_url_to_base64(download_url)

    async def download_url_to_base64(self, download_url):
        async with httpx.AsyncClient() as client:
            response = await client.get(download_url)

            if response.status_code == 200:
                file_bytes = response.content
                base64_str = base64.b64encode(file_bytes).decode('utf-8')  # 返回字符串格式
                return base64_str
            else:
                raise Exception('获取文件失败')

    async def get_audio_url(self, download_code: str):
        if not await self.check_access_token():
            await self.get_access_token()
        url = 'https://api.dingtalk.com/v1.0/robot/messageFiles/download'
        params = {'downloadCode': download_code, 'robotCode': self.robot_code}
        headers = {'x-acs-dingtalk-access-token': self.access_token}
        async with httpx.AsyncClient() as client:
            response = await client.post(url, headers=headers, json=params)
            if response.status_code == 200:
                result = response.json()
                download_url = result.get('downloadUrl')
                if download_url:
                    return await self.download_url_to_base64(download_url)
                else:
                    raise Exception('获取音频失败')
            else:
                raise Exception(f'Error: {response.status_code}, {response.text}')

    async def update_incoming_message(self, message):
        """异步更新 DingTalkClient 中的 incoming_message"""
        message_data = await self.get_message(message)
        if message_data:
            event = DingTalkEvent.from_payload(message_data)
            if event:
                await self._handle_message(event)

    async def send_message(self, content: str, incoming_message):
        if self.markdown_card:
            self.EchoTextHandler.reply_markdown(
                title=self.robot_name + '的回答',
                text=content,
                incoming_message=incoming_message,
            )
        else:
            self.EchoTextHandler.reply_text(content, incoming_message)

    async def get_incoming_message(self):
        """获取收到的消息"""
        return await self.EchoTextHandler.get_incoming_message()

    def on_message(self, msg_type: str):
        def decorator(func: Callable[[DingTalkEvent], None]):
            if msg_type not in self._message_handlers:
                self._message_handlers[msg_type] = []
            self._message_handlers[msg_type].append(func)
            return func

        return decorator

    async def _handle_message(self, event: DingTalkEvent):
        """
        处理消息事件。
        """
        msg_type = event.conversation
        if msg_type in self._message_handlers:
            for handler in self._message_handlers[msg_type]:
                await handler(event)

    async def get_message(self, incoming_message: dingtalk_stream.chatbot.ChatbotMessage):
        try:
            # print(json.dumps(incoming_message.to_dict(), indent=4, ensure_ascii=False))
            message_data = {
                'IncomingMessage': incoming_message,
            }
            if str(incoming_message.conversation_type) == '1':
                message_data['conversation_type'] = 'FriendMessage'
            elif str(incoming_message.conversation_type) == '2':
                message_data['conversation_type'] = 'GroupMessage'

            if incoming_message.message_type == 'richText':
                data = incoming_message.rich_text_content.to_dict()
                for item in data['richText']:
                    if 'text' in item:
                        message_data['Content'] = item['text']
                    if incoming_message.get_image_list()[0]:
                        message_data['Picture'] = await self.download_image(incoming_message.get_image_list()[0])
                message_data['Type'] = 'text'

            elif incoming_message.message_type == 'text':
                message_data['Content'] = incoming_message.get_text_list()[0]

                message_data['Type'] = 'text'
            elif incoming_message.message_type == 'picture':
                message_data['Picture'] = await self.download_image(incoming_message.get_image_list()[0])

                message_data['Type'] = 'image'
            elif incoming_message.message_type == 'audio':
                message_data['Audio'] = await self.get_audio_url(incoming_message.to_dict()['content']['downloadCode'])

                message_data['Type'] = 'audio'

            copy_message_data = message_data.copy()
            del copy_message_data['IncomingMessage']
            # print("message_data:", json.dumps(copy_message_data, indent=4, ensure_ascii=False))
        except Exception:
            traceback.print_exc()

        return message_data

    async def send_proactive_message_to_one(self, target_id: str, content: str):
        if not await self.check_access_token():
            await self.get_access_token()

        url = 'https://api.dingtalk.com/v1.0/robot/oToMessages/batchSend'

        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }

        data = {
            'robotCode': self.robot_code,
            'userIds': [target_id],
            'msgKey': 'sampleText',
            'msgParam': json.dumps({'content': content}),
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, headers=headers, json=data)
        except Exception:
            traceback.print_exc()

    async def send_proactive_message_to_group(self, target_id: str, content: str):
        if not await self.check_access_token():
            await self.get_access_token()

        url = 'https://api.dingtalk.com/v1.0/robot/groupMessages/send'

        headers = {
            'x-acs-dingtalk-access-token': self.access_token,
            'Content-Type': 'application/json',
        }

        data = {
            'robotCode': self.robot_code,
            'openConversationId': target_id,
            'msgKey': 'sampleText',
            'msgParam': json.dumps({'content': content}),
        }
        try:
            async with httpx.AsyncClient() as client:
                await client.post(url, headers=headers, json=data)
        except Exception:
            traceback.print_exc()

    async def start(self):
        """启动 WebSocket 连接，监听消息"""
        await self.client.start()
