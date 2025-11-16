import base64
import json
import time
from typing import Callable
import dingtalk_stream  # type: ignore
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
        logger: None,
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
        self.logger = logger

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
            except Exception:
                await self.logger.error('failed to get access token in dingtalk')

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
                await self.logger.error(f'failed to get download url: {response.json()}')

        if download_url:
            return await self.download_url_to_base64(download_url)

    async def download_url_to_base64(self, download_url):
        async with httpx.AsyncClient() as client:
            response = await client.get(download_url)

            if response.status_code == 200:
                file_bytes = response.content
                mime_type = response.headers.get('Content-Type', 'application/octet-stream')
                base64_str = base64.b64encode(file_bytes).decode('utf-8')
                return f'data:{mime_type};base64,{base64_str}'
            else:
                await self.logger.error(f'failed to get files: {response.json()}')

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
                    await self.logger.error(f'failed to get audio: {response.json()}')
            else:
                raise Exception(f'Error: {response.status_code}, {response.text}')

    async def get_file_url(self, download_code: str):
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
                    return download_url
                else:
                    await self.logger.error(f'failed to get file: {response.json()}')
            else:
                raise Exception(f'Error: {response.status_code}, {response.text}')

    async def update_incoming_message(self, message):
        """异步更新 DingTalkClient 中的 incoming_message"""
        message_data = await self.get_message(message)
        if message_data:
            event = DingTalkEvent.from_payload(message_data)
            if event:
                await self._handle_message(event)

    async def send_message(self, content: str, incoming_message, at: bool):
        if self.markdown_card:
            if at:
                self.EchoTextHandler.reply_markdown(
                    title='@' + incoming_message.sender_nick + ' ' + content,
                    text='@' + incoming_message.sender_nick + ' ' + content,
                    incoming_message=incoming_message,
                )
            else:
                self.EchoTextHandler.reply_markdown(
                    title=content,
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

                # 使用统一的结构化数据格式，保持顺序
                rich_content = {
                    'Type': 'richText',
                    'Elements': [],  # 按顺序存储所有元素
                    'SimpleContent': '',  # 兼容字段：纯文本内容
                    'SimplePicture': '',  # 兼容字段：第一张图片
                }

                # 先收集所有文本和图片占位符
                text_elements = []

                # 解析富文本内容，保持原始顺序
                for item in data['richText']:
                    # 处理文本内容
                    if 'text' in item and item['text'] != '\n':
                        element = {'Type': 'text', 'Content': item['text']}
                        rich_content['Elements'].append(element)
                        text_elements.append(item['text'])

                    # 检查是否是图片元素 - 根据钉钉API的实际结构调整
                    # 钉钉富文本中的图片通常有特定标识，可能需要根据实际返回调整
                    elif item.get('type') == 'picture':
                        # 创建图片占位符
                        element = {
                            'Type': 'image_placeholder',
                        }
                        rich_content['Elements'].append(element)

                # 获取并下载所有图片
                image_list = incoming_message.get_image_list()
                if image_list:
                    new_elements = []
                    image_index = 0

                    for element in rich_content['Elements']:
                        if element['Type'] == 'image_placeholder':
                            if image_index < len(image_list) and image_list[image_index]:
                                image_url = await self.download_image(image_list[image_index])
                                new_elements.append({'Type': 'image', 'Picture': image_url})
                                image_index += 1
                            else:
                                # 如果没有对应的图片，保留占位符或跳过
                                continue
                        else:
                            new_elements.append(element)

                    rich_content['Elements'] = new_elements

                # 设置兼容字段
                all_texts = [elem['Content'] for elem in rich_content['Elements'] if elem.get('Type') == 'text']
                rich_content['SimpleContent'] = '\n'.join(all_texts) if all_texts else ''

                all_images = [elem['Picture'] for elem in rich_content['Elements'] if elem.get('Type') == 'image']
                if all_images:
                    rich_content['SimplePicture'] = all_images[0]
                    rich_content['AllImages'] = all_images  # 所有图片的列表

                # 设置原始的 content 和 picture 字段以保持兼容
                message_data['Content'] = rich_content['SimpleContent']
                message_data['Rich_Content'] = rich_content
                if all_images:
                    message_data['Picture'] = all_images[0]

            elif incoming_message.message_type == 'text':
                message_data['Content'] = incoming_message.get_text_list()[0]

                message_data['Type'] = 'text'
            elif incoming_message.message_type == 'picture':
                message_data['Picture'] = await self.download_image(incoming_message.get_image_list()[0])

                message_data['Type'] = 'image'
            elif incoming_message.message_type == 'audio':
                message_data['Audio'] = await self.get_audio_url(incoming_message.to_dict()['content']['downloadCode'])

                message_data['Type'] = 'audio'
            elif incoming_message.message_type == 'file':
                down_list = incoming_message.get_down_list()
                if len(down_list) >= 2:
                    message_data['File'] = await self.get_file_url(down_list[0])
                    message_data['Name'] = down_list[1]
                else:
                    if self.logger:
                        await self.logger.error(f'get_down_list() returned fewer than 2 elements: {down_list}')
                    message_data['File'] = None
                    message_data['Name'] = None
                message_data['Type'] = 'file'

            copy_message_data = message_data.copy()
            del copy_message_data['IncomingMessage']
            # print("message_data:", json.dumps(copy_message_data, indent=4, ensure_ascii=False))
        except Exception:
            if self.logger:
                await self.logger.error(f'Error in get_message: {traceback.format_exc()}')
            else:
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
                response = await client.post(url, headers=headers, json=data)
                if response.status_code == 200:
                    return
        except Exception:
            await self.logger.error(f'failed to send proactive massage to person: {traceback.format_exc()}')
            raise Exception(f'failed to send proactive massage to person: {traceback.format_exc()}')

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
                response = await client.post(url, headers=headers, json=data)
                if response.status_code == 200:
                    return
        except Exception:
            await self.logger.error(f'failed to send proactive massage to group: {traceback.format_exc()}')
            raise Exception(f'failed to send proactive massage to group: {traceback.format_exc()}')

    async def create_and_card(
        self, temp_card_id: str, incoming_message: dingtalk_stream.ChatbotMessage, quote_origin: bool = False
    ):
        content_key = 'content'
        card_data = {content_key: ''}

        card_instance = dingtalk_stream.AICardReplier(self.client, incoming_message)
        # print(card_instance)
        # 先投放卡片: https://open.dingtalk.com/document/orgapp/create-and-deliver-cards
        card_instance_id = await card_instance.async_create_and_deliver_card(
            temp_card_id,
            card_data,
        )
        return card_instance, card_instance_id

    async def send_card_message(self, card_instance, card_instance_id: str, content: str, is_final: bool):
        content_key = 'content'
        try:
            await card_instance.async_streaming(
                card_instance_id,
                content_key=content_key,
                content_value=content,
                append=False,
                finished=is_final,
                failed=False,
            )
        except Exception as e:
            self.logger.exception(e)
            await card_instance.async_streaming(
                card_instance_id,
                content_key=content_key,
                content_value='',
                append=False,
                finished=is_final,
                failed=True,
            )

    async def start(self):
        """启动 WebSocket 连接，监听消息"""
        await self.client.start()
