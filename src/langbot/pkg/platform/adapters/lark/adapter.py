from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import time
import traceback
import typing
import uuid

from Crypto.Cipher import AES
import lark_oapi
from lark_oapi.api.auth.v3 import (
    CreateAppAccessTokenRequest,
    CreateAppAccessTokenRequestBody,
    CreateAppAccessTokenResponse,
    CreateTenantAccessTokenRequest,
    CreateTenantAccessTokenRequestBody,
    CreateTenantAccessTokenResponse,
    ResendAppTicketRequest,
    ResendAppTicketRequestBody,
    ResendAppTicketResponse,
)
from lark_oapi.api.cardkit.v1 import (
    ContentCardElementRequest,
    ContentCardElementRequestBody,
    ContentCardElementResponse,
    CreateCardRequest,
    CreateCardRequestBody,
    CreateCardResponse,
)
from lark_oapi.api.im.v1 import (
    CreateMessageRequest,
    CreateMessageRequestBody,
    CreateMessageResponse,
    EventMessage,
    EventSender,
    P2ImMessageReceiveV1,
    P2ImMessageReceiveV1Data,
    ReplyMessageRequest,
    ReplyMessageRequestBody,
    ReplyMessageResponse,
)
import lark_oapi.ws.exception
import pydantic
import quart

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger
from langbot.pkg.platform.adapters.lark.api_impl import LarkAPIMixin
from langbot.pkg.platform.adapters.lark.event_converter import LarkEventConverter
from langbot.pkg.platform.adapters.lark.message_converter import LarkMessageConverter
from langbot.pkg.platform.adapters.lark.platform_api import PLATFORM_API_MAP
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform.errors import NotSupportedError


class AESCipher:
    def __init__(self, key: str):
        self.key = hashlib.sha256(self.str_to_bytes(key)).digest()

    @staticmethod
    def str_to_bytes(data):
        if isinstance(data, str):
            return data.encode('utf8')
        return data

    @staticmethod
    def _unpad(value: bytes) -> bytes:
        return value[: -value[len(value) - 1]]

    def decrypt_string(self, encrypted: str) -> str:
        encrypted_bytes = base64.b64decode(encrypted)
        iv = encrypted_bytes[: AES.block_size]
        cipher = AES.new(self.key, AES.MODE_CBC, iv)
        return self._unpad(cipher.decrypt(encrypted_bytes[AES.block_size :])).decode('utf8')


class LarkAdapter(LarkAPIMixin, abstract_platform_adapter.AbstractPlatformAdapter):
    bot: lark_oapi.ws.Client = pydantic.Field(exclude=True)
    api_client: lark_oapi.Client = pydantic.Field(exclude=True)
    quart_app: quart.Quart = pydantic.Field(exclude=True)
    cipher: AESCipher = pydantic.Field(exclude=True)

    config: dict
    lark_tenant_key: str = pydantic.Field(exclude=True, default='')
    app_ticket: str | None = None
    app_access_token: str | None = None
    app_access_token_expire_at: int | None = None
    tenant_access_tokens: dict[str, dict[str, typing.Any]] = pydantic.Field(default_factory=dict)
    bot_uuid: str | None = None
    event_loop: asyncio.AbstractEventLoop | None = pydantic.Field(exclude=True, default=None)

    message_converter: LarkMessageConverter = LarkMessageConverter()
    event_converter: LarkEventConverter = LarkEventConverter()
    listeners: dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = pydantic.Field(default_factory=dict)
    card_id_dict: dict[str, str] = pydantic.Field(default_factory=dict)
    pending_monitoring_msg: dict[str, str] = pydantic.Field(default_factory=dict)
    reply_to_monitoring_msg: dict[str, tuple[str, float]] = pydantic.Field(default_factory=dict)
    _message_cache: dict[str, platform_events.MessageReceivedEvent] = pydantic.PrivateAttr(default_factory=dict)
    _user_cache: dict[str, platform_entities.User] = pydantic.PrivateAttr(default_factory=dict)
    _group_cache: dict[str, platform_entities.UserGroup] = pydantic.PrivateAttr(default_factory=dict)
    _monitoring_mapping_ttl: int = 600

    class Config:
        arbitrary_types_allowed = True

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        required_keys = ['app_id', 'app_secret', 'bot_name']
        missing_keys = [key for key in required_keys if not config.get(key)]
        if missing_keys:
            raise ValueError(f'Lark missing required config: {", ".join(missing_keys)}')

        api_client = self.build_api_client(config)
        event_handler = self._build_event_handler()
        bot = lark_oapi.ws.Client(config['app_id'], config['app_secret'], event_handler=event_handler)
        cipher = AESCipher(config.get('encrypt-key', ''))

        super().__init__(
            config=config,
            logger=logger,
            lark_tenant_key=config.get('lark_tenant_key', ''),
            bot_account_id=config['bot_name'],
            bot=bot,
            api_client=api_client,
            quart_app=quart.Quart(__name__),
            cipher=cipher,
            listeners={},
            card_id_dict={},
            pending_monitoring_msg={},
            reply_to_monitoring_msg={},
            event_loop=None,
            **kwargs,
        )
        self._message_cache = {}
        self._user_cache = {}
        self._group_cache = {}
        self.request_app_ticket()

    def _build_event_handler(self):
        async def on_message(event: lark_oapi.im.v1.P2ImMessageReceiveV1):
            await self._handle_message_event(event)

        def sync_on_message(event: lark_oapi.im.v1.P2ImMessageReceiveV1):
            self._submit_coro(on_message(event))

        def sync_on_card_action(event):
            return self._handle_card_action_sync(event)

        return (
            lark_oapi.EventDispatcherHandler.builder('', '')
            .register_p2_im_message_receive_v1(sync_on_message)
            .register_p2_card_action_trigger(sync_on_card_action)
            .build()
        )

    def get_supported_events(self) -> list[str]:
        return ['message.received', 'bot.invited_to_group', 'platform.specific']

    def get_supported_apis(self) -> list[str]:
        return [
            'send_message',
            'reply_message',
            'get_message',
            'get_group_info',
            'get_group_member_info',
            'get_user_info',
            'get_file_url',
            'call_platform_api',
        ]

    def build_api_client(self, config: dict) -> lark_oapi.Client:
        builder = lark_oapi.Client.builder().app_id(config['app_id']).app_secret(config['app_secret'])
        if config.get('app_type', 'self') == 'isv':
            builder = builder.app_type(lark_oapi.AppType.ISV)
        return builder.build()

    def request_app_ticket(self):
        if self.config.get('app_type', 'self') != 'isv':
            return
        request = (
            ResendAppTicketRequest.builder()
            .request_body(
                ResendAppTicketRequestBody.builder()
                .app_id(self.config['app_id'])
                .app_secret(self.config['app_secret'])
                .build()
            )
            .build()
        )
        response: ResendAppTicketResponse = self.api_client.auth.v3.app_ticket.resend(request)
        if not response.success():
            raise RuntimeError(f'Lark app_ticket resend failed: {response.code} {response.msg}')

    def request_app_access_token(self):
        if self.config.get('app_type', 'self') != 'isv':
            return
        request = (
            CreateAppAccessTokenRequest.builder()
            .request_body(
                CreateAppAccessTokenRequestBody.builder()
                .app_id(self.config['app_id'])
                .app_secret(self.config['app_secret'])
                .app_ticket(self.app_ticket)
                .build()
            )
            .build()
        )
        response: CreateAppAccessTokenResponse = self.api_client.auth.v3.app_access_token.create(request)
        if not response.success():
            raise RuntimeError(f'Lark app_access_token failed: {response.code} {response.msg}')
        content = json.loads(response.raw.content)
        self.app_access_token = content['app_access_token']
        self.app_access_token_expire_at = int(time.time()) + content['expire'] - 300

    def get_app_access_token(self):
        if self.config.get('app_type', 'self') != 'isv':
            return None
        if (
            self.app_access_token is None
            or self.app_access_token_expire_at is None
            or int(time.time()) >= self.app_access_token_expire_at
        ):
            self.request_app_access_token()
        return self.app_access_token

    def request_tenant_access_token(self, tenant_key: str):
        if self.config.get('app_type', 'self') != 'isv':
            return
        request = (
            CreateTenantAccessTokenRequest.builder()
            .request_body(
                CreateTenantAccessTokenRequestBody.builder()
                .app_access_token(self.get_app_access_token())
                .tenant_key(tenant_key)
                .build()
            )
            .build()
        )
        response: CreateTenantAccessTokenResponse = self.api_client.auth.v3.tenant_access_token.create(request)
        if not response.success():
            raise RuntimeError(f'Lark tenant_access_token failed: {response.code} {response.msg}')
        content = json.loads(response.raw.content)
        self.tenant_access_tokens[tenant_key] = {
            'token': content['tenant_access_token'],
            'expire_at': int(time.time()) + content['expire'] - 300,
        }

    def get_tenant_access_token(self, tenant_key: str | None):
        if self.config.get('app_type', 'self') != 'isv' or not tenant_key:
            return None
        cached = self.tenant_access_tokens.get(tenant_key)
        if cached is None or int(time.time()) >= cached['expire_at']:
            self.request_tenant_access_token(tenant_key)
        return self.tenant_access_tokens.get(tenant_key, {}).get('token')

    async def send_message(
        self,
        target_type: str,
        target_id: str,
        message: platform_message.MessageChain,
    ) -> platform_events.MessageResult:
        text_elements, media_items = await self.message_converter.yiri2target(message, self.api_client)
        receive_id_type = 'chat_id' if target_type == 'group' else 'open_id'
        message_ids: list[str] = []

        for msg_type, content in self._outbound_payloads(text_elements, media_items):
            request = (
                CreateMessageRequest.builder()
                .receive_id_type(receive_id_type)
                .request_body(
                    CreateMessageRequestBody.builder()
                    .receive_id(str(target_id))
                    .content(json.dumps(content, ensure_ascii=False))
                    .msg_type(msg_type)
                    .uuid(str(uuid.uuid4()))
                    .build()
                )
                .build()
            )
            response: CreateMessageResponse = await self.api_client.im.v1.message.acreate(request)
            if not response.success():
                raise RuntimeError(f'Lark send_message failed: {response.code} {response.msg}')
            message_ids.append(getattr(response.data, 'message_id', ''))

        return platform_events.MessageResult(
            message_id=message_ids[-1] if message_ids else '', raw={'message_ids': message_ids}
        )

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ) -> platform_events.MessageResult:
        text_elements, media_items = await self.message_converter.yiri2target(message, self.api_client)
        tenant_key = self._tenant_key_from_source(message_source)
        message_ids: list[str] = []

        for msg_type, content in self._outbound_payloads(text_elements, media_items):
            request = (
                ReplyMessageRequest.builder()
                .message_id(self._message_id_from_source(message_source))
                .request_body(
                    ReplyMessageRequestBody.builder()
                    .content(json.dumps(content, ensure_ascii=False))
                    .msg_type(msg_type)
                    .reply_in_thread(False)
                    .uuid(str(uuid.uuid4()))
                    .build()
                )
                .build()
            )
            response: ReplyMessageResponse = await self.api_client.im.v1.message.areply(
                request, self.request_option(tenant_key)
            )
            if not response.success():
                raise RuntimeError(f'Lark reply_message failed: {response.code} {response.msg}')
            message_ids.append(getattr(response.data, 'message_id', ''))

        return platform_events.MessageResult(
            message_id=message_ids[-1] if message_ids else '', raw={'message_ids': message_ids}
        )

    def _outbound_payloads(self, text_elements: list[list[dict]], media_items: list[dict]) -> list[tuple[str, dict]]:
        payloads: list[tuple[str, dict]] = []
        if text_elements:
            needs_post = any(ele.get('tag') == 'at' for paragraph in text_elements for ele in paragraph)
            if needs_post:
                payloads.append(('post', {'zh_Hans': {'title': '', 'content': text_elements}}))
            else:
                parts = []
                for paragraph in text_elements:
                    text = ''.join(ele.get('text', '') for ele in paragraph)
                    if text:
                        parts.append(text)
                payloads.append(('text', {'text': '\n\n'.join(parts)}))
        for media in media_items:
            payloads.append((media['msg_type'], media['content']))
        return payloads

    async def is_stream_output_supported(self) -> bool:
        return bool(self.config.get('enable-stream-reply', False))

    async def on_monitoring_message_created(self, query, monitoring_message_id: str):
        user_msg_id = getattr(query.message_event, 'message_id', None)
        if user_msg_id:
            self.pending_monitoring_msg[str(user_msg_id)] = monitoring_message_id

    async def create_message_card(self, message_id, event) -> bool:
        card_id = await self.create_card_id(message_id)
        content = {'type': 'card', 'data': {'card_id': card_id, 'template_variable': {'content': 'Thinking...'}}}
        request = (
            ReplyMessageRequest.builder()
            .message_id(self._message_id_from_source(event))
            .request_body(
                ReplyMessageRequestBody.builder().content(json.dumps(content)).msg_type('interactive').build()
            )
            .build()
        )
        response: ReplyMessageResponse = await self.api_client.im.v1.message.areply(
            request, self.request_option(self._tenant_key_from_source(event))
        )
        if not response.success():
            raise RuntimeError(f'Lark create_message_card failed: {response.code} {response.msg}')
        return True

    async def create_card_id(self, message_id) -> str:
        card_data = {
            'schema': '2.0',
            'config': {'update_multi': True, 'streaming_mode': True},
            'body': {
                'direction': 'vertical',
                'elements': [{'tag': 'markdown', 'content': '', 'element_id': 'streaming_txt'}],
            },
        }
        request = (
            CreateCardRequest.builder()
            .request_body(CreateCardRequestBody.builder().type('card_json').data(json.dumps(card_data)).build())
            .build()
        )
        response: CreateCardResponse = self.api_client.cardkit.v1.card.create(request)
        if not response.success():
            raise RuntimeError(f'Lark create_card failed: {response.code} {response.msg}')
        self.card_id_dict[str(message_id)] = response.data.card_id
        return response.data.card_id

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        if bot_message.msg_sequence % 8 != 0 and not is_final:
            return
        text_elements, _ = await self.message_converter.yiri2target(message, self.api_client)
        content = '\n\n'.join(
            ''.join(ele.get('text', '') for ele in paragraph if ele.get('tag') in {'text', 'md'})
            for paragraph in text_elements
        )
        request = (
            ContentCardElementRequest.builder()
            .card_id(self.card_id_dict[bot_message.resp_message_id])
            .element_id('streaming_txt')
            .request_body(
                ContentCardElementRequestBody.builder().content(content).sequence(bot_message.msg_sequence).build()
            )
            .build()
        )
        response: ContentCardElementResponse = self.api_client.cardkit.v1.card_element.content(
            request, self.request_option(self._tenant_key_from_source(message_source))
        )
        if not response.success():
            raise RuntimeError(f'Lark card_element update failed: {response.code} {response.msg}')
        if is_final and bot_message.tool_calls is None:
            self.card_id_dict.pop(bot_message.resp_message_id, None)

    async def call_platform_api(self, action: str, params: dict = {}) -> dict:
        handler = PLATFORM_API_MAP.get(action)
        if handler is None:
            raise NotSupportedError(f'call_platform_api:{action}')
        return await handler(self, params)

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        if self.listeners.get(event_type) is callback:
            self.listeners.pop(event_type, None)

    def set_bot_uuid(self, bot_uuid: str):
        self.bot_uuid = bot_uuid

    def get_launcher_id(self, event: platform_events.MessageEvent) -> str | None:
        source_event = getattr(event.source_platform_object, 'event', None)
        message = getattr(source_event, 'message', None) if source_event else None
        thread_id = getattr(message, 'thread_id', None)
        if thread_id and isinstance(event, platform_events.MessageReceivedEvent) and event.group:
            return f'{event.group.id}_{thread_id}'
        return None

    async def handle_unified_webhook(self, bot_uuid: str, path: str, request):
        try:
            data = await request.json
            if 'encrypt' in data:
                data = json.loads(self.cipher.decrypt_string(data['encrypt']))
            event_type = self.get_event_type(data)
            if event_type == 'url_verification':
                return {'challenge': data.get('challenge')}
            if event_type == 'app_ticket':
                self.app_ticket = self._webhook_event(data).get('app_ticket')
                return {'code': 200, 'message': 'ok'}
            if event_type == 'im.message.receive_v1':
                p2v1 = P2ImMessageReceiveV1()
                p2v1.header = self._webhook_header(data)
                event_data = P2ImMessageReceiveV1Data()
                raw_event = self._webhook_event(data)
                event_data.message = EventMessage(raw_event['message'])
                event_data.sender = EventSender(raw_event['sender'])
                p2v1.event = event_data
                p2v1.schema = data.get('schema', '2.0')
                await self._handle_message_event(p2v1)
                return {'code': 200, 'message': 'ok'}
            if event_type == 'im.chat.member.bot.added_v1':
                raw_event = self._webhook_event(data)
                header = self._webhook_header(data)
                chat_id = raw_event.get('chat_id', '')
                await self._send_bot_added_welcome(chat_id, getattr(header, 'tenant_key', None))
                await self._dispatch_eba_event(LarkEventConverter.bot_invited_to_group(data, chat_id))
                return {'code': 200, 'message': 'ok'}
            if event_type == 'card.action.trigger':
                feedback_event = self._feedback_event_from_webhook(data)
                if feedback_event and platform_events.FeedbackEvent in self.listeners:
                    await self.listeners[platform_events.FeedbackEvent](feedback_event, self)
                return {'toast': {'type': 'success', 'content': '感谢您的反馈'}}
            await self._dispatch_eba_event(LarkEventConverter.platform_specific(data, event_type, data))
            return {'code': 200, 'message': 'ok'}
        except Exception:
            await self.logger.error(f'Error in lark webhook: {traceback.format_exc()}')
            return {'code': 500, 'message': 'error'}

    def get_event_type(self, data: dict) -> str:
        schema = data.get('schema', '1.0')
        if schema == '2.0':
            return data.get('header', {}).get('event_type', '')
        if 'event' in data:
            return data['event'].get('type', '')
        return data.get('type', '')

    def _webhook_event(self, data: dict) -> dict:
        return data.get('event', {})

    def _webhook_header(self, data: dict):
        return type('LarkWebhookHeader', (), data.get('header', {}))()

    async def run_async(self):
        self.event_loop = asyncio.get_running_loop()
        if not self.config.get('enable-webhook', False):
            try:
                await self.bot._connect()
            except lark_oapi.ws.exception.ClientException:
                raise
            except Exception:
                await self.bot._disconnect()
                if self.bot._auto_reconnect:
                    await self.bot._reconnect()
                else:
                    raise
        else:
            while True:
                await asyncio.sleep(1)

    async def kill(self) -> bool:
        self.bot._auto_reconnect = False
        await self.bot._disconnect()
        return True

    async def is_muted(self, group_id: int | None = None) -> bool:
        return False

    async def _handle_message_event(self, event: lark_oapi.im.v1.P2ImMessageReceiveV1):
        try:
            if platform_events.FriendMessage in self.listeners or platform_events.GroupMessage in self.listeners:
                legacy_event = await self.event_converter.target2legacy(event, self.api_client)
                if legacy_event and type(legacy_event) in self.listeners:
                    await self.listeners[type(legacy_event)](legacy_event, self)
            eba_event = await self.event_converter.target2yiri(event, self.api_client)
            if eba_event:
                self._cache_event(eba_event)
                await self._dispatch_eba_event(eba_event)
        except Exception:
            await self.logger.error(f'Error in lark message event: {traceback.format_exc()}')

    async def _dispatch_eba_event(self, event: platform_events.Event):
        for event_type in (type(event), platform_events.EBAEvent, platform_events.Event):
            callback = self.listeners.get(event_type)
            if callback:
                await callback(event, self)
                return

    def _cache_event(self, event: platform_events.Event):
        if not isinstance(event, platform_events.MessageReceivedEvent):
            return
        self._message_cache[str(event.message_id)] = event
        self._user_cache[str(event.sender.id)] = event.sender
        if event.group:
            self._group_cache[str(event.group.id)] = event.group

    def _handle_card_action_sync(self, event):
        feedback_event = self._feedback_event_from_callback(event)
        if feedback_event and platform_events.FeedbackEvent in self.listeners:
            self._submit_coro(self.listeners[platform_events.FeedbackEvent](feedback_event, self))
        from lark_oapi.event.callback.model.p2_card_action_trigger import P2CardActionTriggerResponse

        return P2CardActionTriggerResponse({'toast': {'type': 'success', 'content': '感谢您的反馈'}})

    def _submit_coro(self, coro):
        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = self.event_loop
            if loop and loop.is_running():
                asyncio.run_coroutine_threadsafe(coro, loop)
                return
            coro.close()
            raise
        else:
            loop.create_task(coro)

    def _feedback_event_from_callback(self, event) -> platform_events.FeedbackEvent | None:
        value = getattr(getattr(event.event, 'action', None), 'value', {}) or {}
        return self._feedback_event(
            raw=event,
            feedback_id=getattr(event.header, 'event_id', str(uuid.uuid4())),
            feedback_value=value.get('feedback', ''),
            user_id=getattr(getattr(event.event, 'operator', None), 'open_id', None),
            chat_id=getattr(getattr(event.event, 'context', None), 'open_chat_id', None),
            message_id=getattr(getattr(event.event, 'context', None), 'open_message_id', None),
        )

    def _feedback_event_from_webhook(self, data: dict) -> platform_events.FeedbackEvent | None:
        event = data.get('event', {})
        value = event.get('action', {}).get('value', {}) or {}
        operator = event.get('operator', {})
        context = event.get('context', {})
        return self._feedback_event(
            raw=data,
            feedback_id=data.get('header', {}).get('event_id', str(uuid.uuid4())),
            feedback_value=value.get('feedback', ''),
            user_id=operator.get('open_id') or operator.get('user_id'),
            chat_id=context.get('open_chat_id'),
            message_id=context.get('open_message_id'),
        )

    def _feedback_event(
        self,
        raw,
        feedback_id: str,
        feedback_value: str,
        user_id: str | None,
        chat_id: str | None,
        message_id: str | None,
    ) -> platform_events.FeedbackEvent | None:
        if feedback_value == '有帮助':
            feedback_type = 1
        elif feedback_value == '无帮助':
            feedback_type = 2
        else:
            return None
        return platform_events.FeedbackEvent(
            feedback_id=feedback_id,
            feedback_type=feedback_type,
            feedback_content=feedback_value,
            user_id=user_id,
            session_id=f'group_{chat_id}' if chat_id else (f'person_{user_id}' if user_id else None),
            message_id=message_id,
            stream_id=self.reply_to_monitoring_msg.get(message_id, (None, 0))[0] if message_id else None,
            source_platform_object=raw,
        )

    async def _send_bot_added_welcome(self, chat_id: str, tenant_key: str | None):
        welcome = self.config.get('bot_added_welcome', '')
        if not welcome or not chat_id:
            return
        content = {'zh_Hans': {'title': '', 'content': [[{'tag': 'md', 'text': welcome}]]}}
        request = (
            CreateMessageRequest.builder()
            .receive_id_type('chat_id')
            .request_body(
                CreateMessageRequestBody.builder()
                .receive_id(chat_id)
                .content(json.dumps(content, ensure_ascii=False))
                .msg_type('post')
                .uuid(str(uuid.uuid4()))
                .build()
            )
            .build()
        )
        response: CreateMessageResponse = await self.api_client.im.v1.message.acreate(
            request, self.request_option(tenant_key)
        )
        if not response.success():
            await self.logger.warning(f'Lark bot_added_welcome failed: {response.code} {response.msg}')

    def _tenant_key_from_source(self, event: platform_events.Event) -> str | None:
        source = getattr(event, 'source_platform_object', None)
        header = getattr(source, 'header', None)
        return getattr(header, 'tenant_key', None)

    def _message_id_from_source(self, event: platform_events.Event) -> str:
        message_id = getattr(event, 'message_id', None)
        if message_id:
            return str(message_id)
        source = getattr(event, 'source_platform_object', None)
        source_event = getattr(source, 'event', None)
        message = getattr(source_event, 'message', None) if source_event else None
        message_id = getattr(message, 'message_id', None)
        if message_id:
            return str(message_id)
        raise RuntimeError('Lark message source does not contain message_id')
