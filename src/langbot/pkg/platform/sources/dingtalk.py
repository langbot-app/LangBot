import asyncio
import json
import traceback
import typing
import uuid

from langbot.libs.dingtalk_api.dingtalkevent import DingTalkEvent
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.entities.builtin.provider.session as provider_session
from langbot.libs.dingtalk_api.api import DingTalkClient
import datetime
from langbot.pkg.platform.logger import EventLogger
from langbot.pkg.provider.runners.difysvapi import _format_human_input_text


class DingTalkMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    def _format_image_as_markdown(msg: platform_message.Image) -> str:
        """Convert an Image message to Markdown format for DingTalk."""
        if msg.url:
            return f'\n![image]({msg.url})\n'
        elif msg.base64:
            # For base64 images, try to include them as data URIs
            # DingTalk may have limited support for base64 in markdown
            if msg.base64.startswith('data:'):
                return f'\n![image]({msg.base64})\n'
            else:
                return f'\n![image](data:image/png;base64,{msg.base64})\n'
        return ''

    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, markdown_enabled: bool = True):
        content = ''
        at = False
        for msg in message_chain:
            if type(msg) is platform_message.At:
                at = True
            elif type(msg) is platform_message.Plain:
                content += msg.text
            elif type(msg) is platform_message.Image:
                # DingTalk supports markdown images when markdown_card is enabled
                # When markdown is disabled, images cannot be rendered in plain text mode
                if markdown_enabled:
                    content += DingTalkMessageConverter._format_image_as_markdown(msg)
                # Note: When markdown_enabled is False, images are not included
                # as DingTalk plain text messages don't support image embedding
            elif type(msg) is platform_message.Forward:
                for node in msg.node_list:
                    forwarded_content, _ = await DingTalkMessageConverter.yiri2target(
                        node.message_chain, markdown_enabled
                    )
                    content += forwarded_content
        return content, at

    @staticmethod
    async def target2yiri(event: DingTalkEvent, bot_name: str):
        yiri_msg_list = []
        yiri_msg_list.append(
            platform_message.Source(id=event.incoming_message.message_id, time=datetime.datetime.now())
        )

        for atUser in event.incoming_message.at_users:
            if atUser.dingtalk_id == event.incoming_message.chatbot_user_id:
                yiri_msg_list.append(platform_message.At(target=bot_name))

        if event.rich_content:
            elements = event.rich_content.get('Elements')
            for element in elements:
                if element.get('Type') == 'text':
                    text = element.get('Content', '').replace('@' + bot_name, '')
                    if text.strip():
                        yiri_msg_list.append(platform_message.Plain(text=text))
                elif element.get('Type') == 'image' and element.get('Picture'):
                    yiri_msg_list.append(platform_message.Image(base64=element['Picture']))
        else:
            # 回退到原有简单逻辑
            # 对于音频消息，content 来自 recognition 转写文字，在下方音频处理块中统一处理
            if event.content and event.type != 'audio':
                text_content = event.content.replace('@' + bot_name, '')
                yiri_msg_list.append(platform_message.Plain(text=text_content))
            if event.picture:
                yiri_msg_list.append(platform_message.Image(base64=event.picture))

            # 处理其他类型消息（文件、音频等）
        if event.file:
            yiri_msg_list.append(platform_message.File(url=event.file, name=event.name))
        if event.audio:
            # 优先使用钉钉自带的语音转写文字（recognition字段）
            if event.content and event.type == 'audio':
                yiri_msg_list.append(platform_message.Plain(text=event.content))
            else:
                yiri_msg_list.append(platform_message.Voice(base64=event.audio))

        # Handle quoted/replied message - extract content as top-level components
        # so that plugins like FileReader can process them the same way as direct messages
        if event.quoted_message:
            quote_info = event.quoted_message
            msg_type = quote_info.get('msg_type', '')

            # Process quoted file - add as top-level File component (same as private chat)
            if msg_type == 'file' and quote_info.get('file_url'):
                file_name = quote_info.get('file_name', 'file')
                yiri_msg_list.append(platform_message.File(url=quote_info['file_url'], name=file_name))

            # Process quoted image - add as top-level Image component
            elif msg_type == 'picture' and quote_info.get('picture'):
                yiri_msg_list.append(platform_message.Image(base64=quote_info['picture']))

            # Process quoted audio - add as top-level Voice component
            elif msg_type == 'audio' and quote_info.get('audio'):
                yiri_msg_list.append(platform_message.Voice(base64=quote_info['audio']))

            # Process quoted text - add as Plain text with context prefix
            elif msg_type == 'text' and quote_info.get('content'):
                yiri_msg_list.append(platform_message.Plain(text=f'[引用消息] {quote_info["content"]}'))

            # Process quoted rich text - add as Plain text with context prefix
            elif msg_type == 'richText' and quote_info.get('content'):
                yiri_msg_list.append(platform_message.Plain(text=f'[引用消息] {quote_info["content"]}'))

        chain = platform_message.MessageChain(yiri_msg_list)

        return chain


class DingTalkEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent):
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: DingTalkEvent, bot_name: str):
        message_chain = await DingTalkMessageConverter.target2yiri(event, bot_name)

        if event.conversation == 'FriendMessage':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.incoming_message.sender_staff_id,
                    nickname=event.incoming_message.sender_nick,
                    remark='',
                ),
                message_chain=message_chain,
                time=event.incoming_message.create_at,
                source_platform_object=event,
            )
        elif event.conversation == 'GroupMessage':
            sender = platform_entities.GroupMember(
                id=event.incoming_message.sender_staff_id,
                member_name=event.incoming_message.sender_nick,
                permission='MEMBER',
                group=platform_entities.Group(
                    id=event.incoming_message.conversation_id,
                    name=event.incoming_message.conversation_title,
                    permission=platform_entities.Permission.Member,
                ),
                special_title='',
            )
            time = event.incoming_message.create_at
            return platform_events.GroupMessage(
                sender=sender,
                message_chain=message_chain,
                time=time,
                source_platform_object=event,
            )


class DingTalkAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: DingTalkClient
    bot_account_id: str
    message_converter: DingTalkMessageConverter = DingTalkMessageConverter()
    event_converter: DingTalkEventConverter = DingTalkEventConverter()
    config: dict
    card_instance_id_dict: (
        dict  # 回复卡片消息字典，key为消息id，value为回复卡片实例id，用于在流式消息时判断是否发送到指定卡片
    )
    # outTrackId → form snapshot {session_key, launcher_type, launcher_id, form_token,
    #   workflow_run_id, actions, node_title, form_content, expires_at, open_space_id,
    #   user_id_hint, current_text}. Lookup keys for the data-source pull endpoint and
    #   the STREAM card-action callback.
    card_state: dict
    # session_key → out_track_id of the currently-active card for the
    # conversation turn. Lets resumed-workflow chunks (which arrive on a
    # synthetic event with a fresh resp_message_id) keep updating the same
    # card the user clicked instead of getting a new one.
    active_turn_card: dict
    # session_key → accumulated streaming text for the active turn. Read
    # by _paint_form_on_card so the post-pause form keeps the streamed
    # context above the new prompt.
    active_turn_text: dict
    ap: typing.Any = None
    bot_uuid: str = ''

    def __init__(self, config: dict, logger: EventLogger):
        required_keys = [
            'client_id',
            'client_secret',
            'robot_name',
            'robot_code',
        ]
        missing_keys = [key for key in required_keys if key not in config]
        if missing_keys:
            raise Exception('钉钉缺少相关配置项，请查看文档或联系管理员')
        bot = DingTalkClient(
            client_id=config['client_id'],
            client_secret=config['client_secret'],
            robot_name=config['robot_name'],
            robot_code=config['robot_code'],
            markdown_card=config['markdown_card'],
            logger=logger,
        )
        bot_account_id = config['robot_name']
        super().__init__(
            config=config,
            logger=logger,
            card_instance_id_dict={},
            card_state={},
            active_turn_card={},
            active_turn_text={},
            bot_account_id=bot_account_id,
            bot=bot,
            listeners={},
        )
        # Wire the card-action callback after super().__init__ so we can reference
        # self.* — the client's handler stores this as a soft reference and reads
        # it at fire time.
        self.bot.card_action_callback = self._on_card_action

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        event = await DingTalkEventConverter.yiri2target(
            message_source,
        )
        incoming_message = event.incoming_message

        markdown_enabled = self.config.get('markdown_card', False)
        content, at = await DingTalkMessageConverter.yiri2target(message, markdown_enabled)
        await self.bot.send_message(content, incoming_message, at)

    async def reply_message_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
        is_final: bool = False,
    ):
        message_id = bot_message.resp_message_id
        msg_seq = bot_message.msg_sequence

        form_template_id = (self.config.get('human_input_card_template_id') or '').strip()
        form_data = getattr(bot_message, '_form_data', None)
        if is_final and self.ap is not None:
            self.ap.logger.info(
                f'DingTalk reply_message_chunk final: form_data_present={form_data is not None}, '
                f'form_template_configured={bool(form_template_id)}'
            )

        if form_data and is_final:
            await self._handle_form_chunk(message_source, bot_message, message, form_data)
            return

        if (msg_seq - 1) % 8 == 0 or is_final:
            markdown_enabled = self.config.get('markdown_card', False)
            content, at = await DingTalkMessageConverter.yiri2target(message, markdown_enabled)
            if not content and bot_message.content:
                content = bot_message.content  # 兼容直接传入content的情况

            chat_card_entry = self.card_instance_id_dict.get(message_id)
            if chat_card_entry is None:
                # No streaming chat card was created for this query — common
                # path for synthetic events (e.g. resumed workflow after a
                # button click). Lazy-create one so the resumed output streams
                # into a card just like a normal conversation, instead of
                # being deferred and sent in one shot on is_final.
                if not content:
                    return  # nothing to stream yet
                chat_card_entry = await self._lazy_create_resume_chat_card(message_source, message_id)
                if chat_card_entry is None:
                    # Lazy-create failed (no template configured); fall back
                    # to a one-shot proactive message on the final chunk.
                    if is_final:
                        await self._send_proactive_to_event(message_source, content)
                    return

            card_instance, card_instance_id = chat_card_entry
            if content:
                if form_template_id:
                    # The card content has already been written via
                    # update_card_data (in _paint_form_on_card and the
                    # initial card creation). The streaming endpoint
                    # (PUT /v1.0/card/streaming) does not propagate
                    # updates on cards whose content was last set via
                    # update_card_data — they take different code paths
                    # on the DingTalk client. Stick with update_card_data
                    # for the whole turn for consistency.
                    try:
                        await self.bot.update_card_data(
                            out_track_id=card_instance_id,
                            card_param_map={
                                'content': content,
                                'btns': '[]',
                                'flowStatus': '3' if is_final else '1',
                            },
                        )
                    except Exception:
                        if self.ap is not None:
                            self.ap.logger.exception('DingTalk: update card content failed')
                else:
                    await self.bot.send_card_message(card_instance, card_instance_id, content, is_final)
            if is_final:
                if form_template_id and not content:
                    # Empty final chunk still needs to leave the card with
                    # flowStatus=3 so the spinner stops.
                    try:
                        await self.bot.update_card_data(
                            out_track_id=card_instance_id,
                            card_param_map={'flowStatus': '3'},
                        )
                    except Exception:
                        pass
                if bot_message.tool_calls is None:
                    self.card_instance_id_dict.pop(message_id, None)

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        markdown_enabled = self.config.get('markdown_card', False)
        content, _ = await DingTalkMessageConverter.yiri2target(message, markdown_enabled)
        if target_type == 'person':
            await self.bot.send_proactive_message_to_one(target_id, content)
        if target_type == 'group':
            await self.bot.send_proactive_message_to_group(target_id, content)

    async def is_stream_output_supported(self) -> bool:
        is_stream = False
        if self.config.get('enable-stream-reply', None):
            is_stream = True
        return is_stream

    async def create_message_card(self, message_id, event):
        form_template_id = (self.config.get('human_input_card_template_id') or '').strip()
        legacy_template_id = self.config.get('card_template_id', '')

        # Synthetic events (button clicks): look up the card already in
        # active_turn_card so reply_message_chunk can stream to it.
        if event is None or event.source_platform_object is None:
            if form_template_id:
                session_key = self._session_key_from_event(event) if event is not None else ''
                carry = self.active_turn_card.get(session_key, '') if session_key else ''
                if carry:
                    self.card_instance_id_dict[message_id] = (None, carry)
                    return True
            return False

        if form_template_id:
            # Create one card with the form template, empty buttons,
            # pending state. Streaming writes content to it; form pause
            # paints buttons onto it. One card per turn, no duplication.
            incoming_message = event.source_platform_object.incoming_message
            out_track_id = uuid.uuid4().hex
            is_group = str(incoming_message.conversation_type) == '2'
            if is_group:
                open_space_id = f'dtv1.card//IM_GROUP.{incoming_message.conversation_id}'
            else:
                open_space_id = f'dtv1.card//IM_ROBOT.{incoming_message.sender_staff_id}'
            try:
                await self.bot.create_and_deliver_card(
                    card_template_id=form_template_id,
                    out_track_id=out_track_id,
                    open_space_id=open_space_id,
                    is_group=is_group,
                    card_param_map={'content': '', 'btns': '[]', 'flowStatus': '1'},
                    callback_type='STREAM',
                )
            except Exception:
                if self.ap is not None:
                    self.ap.logger.exception('DingTalk: create form-template card failed')
                return False
            self.card_instance_id_dict[message_id] = (None, out_track_id)
            session_key = self._session_key_from_event(event)
            if session_key:
                self.active_turn_card[session_key] = out_track_id
                self.active_turn_text[session_key] = ''
            return True

        # Legacy chat-card path (no form template).
        incoming_message = event.source_platform_object.incoming_message
        card_auto_layout = self.config.get('card_auto_layout', False)
        card_instance, card_instance_id = await self.bot.create_and_card(
            legacy_template_id, incoming_message, card_auto_layout=card_auto_layout
        )
        self.card_instance_id_dict[message_id] = (card_instance, card_instance_id)
        return True

    def _session_key_from_event(self, event) -> str:
        """Return launcher_type_launcher_id for an event, '' if unrecoverable."""
        if event is None:
            return ''
        spo = event.source_platform_object
        if spo is None:
            try:
                if isinstance(event, platform_events.GroupMessage):
                    return f'group_{event.group.id}'
                return f'person_{event.sender.id}'
            except Exception:
                return ''
        try:
            inc = spo.incoming_message
            if str(inc.conversation_type) == '2':
                return f'group_{inc.conversation_id}'
            return f'person_{inc.sender_staff_id}'
        except Exception:
            return ''

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        async def on_message(event: DingTalkEvent):
            try:
                return await callback(
                    await self.event_converter.target2yiri(event, self.config['robot_name']),
                    self,
                )
            except Exception:
                await self.logger.error(f'Error in dingtalk callback: {traceback.format_exc()}')

        if event_type == platform_events.FriendMessage:
            self.bot.on_message('FriendMessage')(on_message)
        elif event_type == platform_events.GroupMessage:
            self.bot.on_message('GroupMessage')(on_message)

    async def run_async(self):
        await self.bot.start()

    async def kill(self) -> bool:
        await self.bot.stop()
        return True

    async def is_muted(self) -> bool:
        return False

    async def unregister_listener(
        self,
        event_type: type,
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        return super().unregister_listener(event_type, callback)

    # ------------------------------------------------------------------
    # Dify human-input form support
    # ------------------------------------------------------------------

    def set_bot_uuid(self, bot_uuid: str):
        """Receive the bot uuid from the platform manager.

        Used to compose the public-facing unified-webhook URL for the card
        dynamic-data-source pull endpoint.
        """
        self.bot_uuid = bot_uuid

    def _derive_open_space(self, message_source: platform_events.MessageEvent) -> tuple[str, bool]:
        """Return (openSpaceId, is_group) for the given inbound event."""
        if isinstance(message_source, platform_events.GroupMessage):
            return f'dtv1.card//IM_GROUP.{message_source.group.id}', True
        return f'dtv1.card//IM_ROBOT.{message_source.sender.id}', False

    def _derive_session_descriptor(
        self, message_source: platform_events.MessageEvent
    ) -> tuple[provider_session.LauncherTypes, str, str]:
        """Return (launcher_type, launcher_id, sender_user_id) for routing."""
        if isinstance(message_source, platform_events.GroupMessage):
            return (
                provider_session.LauncherTypes.GROUP,
                str(message_source.group.id),
                str(message_source.sender.id),
            )
        return (
            provider_session.LauncherTypes.PERSON,
            str(message_source.sender.id),
            str(message_source.sender.id),
        )

    async def _handle_form_chunk(
        self,
        message_source: platform_events.MessageEvent,
        bot_message,
        message: platform_message.MessageChain,
        form_data: dict,
    ) -> None:
        """Surface human-input prompt + buttons on the active card.

        In single-card mode (form_template_id configured): update the
        EXISTING card with form buttons so it transitions from streaming
        output to prompt+buttons on the same card. In legacy mode:
        finalize the chat card and deliver a separate form card.
        """
        if self.ap is not None:
            self.ap.logger.info(
                f'DingTalk _handle_form_chunk: actions={len(form_data.get("actions") or [])}, '
                f'node_title={form_data.get("node_title", "")!r}'
            )
        message_id = bot_message.resp_message_id
        template_id = (self.config.get('human_input_card_template_id') or '').strip()

        if template_id:
            # Single-card mode: paint prompt + buttons onto the existing card.
            session_key = self._session_key_from_event(message_source)
            entry = self.card_instance_id_dict.get(message_id)
            out_track_id = entry[1] if entry else None
            if not out_track_id and session_key:
                out_track_id = self.active_turn_card.get(session_key, '')
            if out_track_id:
                await self._paint_form_on_card(message_source, out_track_id, form_data, session_key)
                self.card_instance_id_dict.pop(message_id, None)
                return

            # No existing card (e.g. Dify paused immediately with no LLM
            # output before the pause). Create a form card directly.
            await self._send_form_card(message_source, form_data, template_id)
            self.card_instance_id_dict.pop(message_id, None)
            return

        # Legacy mode: finalize the streaming card with text fallback.
        chat_card_entry = self.card_instance_id_dict.pop(message_id, None)
        if chat_card_entry is not None:
            _, chat_out_track_id = chat_card_entry
            markdown_enabled = self.config.get('markdown_card', False)
            text_content, _ = await DingTalkMessageConverter.yiri2target(message, markdown_enabled)
            if not text_content and bot_message.content:
                text_content = bot_message.content
            try:
                await self.bot.send_card_message(None, chat_out_track_id, text_content or '​', True)
            except Exception:
                await self.logger.error(f'DingTalk: finalize chat card before form failed: {traceback.format_exc()}')

        await self.send_message_text_form(message_source, form_data)

    async def _paint_form_on_card(
        self,
        message_source: platform_events.MessageEvent,
        out_track_id: str,
        form_data: dict,
        session_key: str,
    ) -> None:
        """Update an existing card's content + buttons for human-input."""
        actions = list(form_data.get('actions') or [])
        node_title = form_data.get('node_title', '') or 'Human Input Required'
        form_content = form_data.get('form_content', '') or ''

        # Record form state for the click-handler.
        launcher_type, launcher_id, sender_user_id = self._derive_session_descriptor(message_source)
        self.card_state[out_track_id] = {
            'session_key': session_key,
            'launcher_type': launcher_type.value,
            'launcher_id': launcher_id,
            'sender_user_id': sender_user_id,
            'form_token': form_data.get('form_token', ''),
            'workflow_run_id': form_data.get('workflow_run_id', ''),
            'actions': actions,
            'node_title': node_title,
            'form_content': form_content,
        }

        btns = self._build_btns(actions, out_track_id)
        parts: list[str] = []
        prior = self.active_turn_text.get(session_key, '') if session_key else ''
        if prior.strip():
            parts.append(prior.rstrip())
            parts.append('---')
        if node_title:
            parts.append(f'**{node_title}**')
        if form_content:
            parts.append(form_content)
        display_content = '\n\n'.join(parts) or '请选择一个操作以继续。'

        try:
            await self.bot.update_card_data(
                out_track_id=out_track_id,
                card_param_map={
                    'content': display_content,
                    'btns': json.dumps(btns, ensure_ascii=False),
                    'flowStatus': '3',
                },
            )
        except Exception:
            if self.ap is not None:
                self.ap.logger.exception('DingTalk: paint form on card failed')
            await self.send_message_text_form(message_source, form_data)
            return

        if session_key:
            self.active_turn_text[session_key] = display_content

    @staticmethod
    def _build_btns(actions: list, out_track_id: str) -> list:
        btns = []
        for idx, action in enumerate(actions):
            action_id = str(action.get('id') or '')
            title = str(action.get('title') or action_id or f'选项 {idx + 1}')
            style = (action.get('button_style') or '').lower()
            if style == 'primary' or (style == '' and idx == 0):
                color = 'blue'
            elif style == 'danger':
                color = 'red'
            else:
                color = 'gray'
            btns.append(
                {
                    'text': title,
                    'color': color,
                    'status': 'normal',
                    'event': {
                        'type': 'sendCardRequest',
                        'params': {
                            'actionId': action_id,
                            'params': {'action_id': action_id, 'out_track_id': out_track_id},
                        },
                    },
                }
            )
        return btns

    async def _send_form_card(
        self,
        message_source: platform_events.MessageEvent,
        form_data: dict,
        template_id: str,
    ) -> None:
        """Deliver a new card pre-loaded with the human-input prompt + buttons."""
        out_track_id = uuid.uuid4().hex
        open_space_id, is_group = self._derive_open_space(message_source)
        launcher_type, launcher_id, sender_user_id = self._derive_session_descriptor(message_source)
        session_key = f'{launcher_type.value}_{launcher_id}'

        actions = list(form_data.get('actions') or [])
        node_title = form_data.get('node_title', '') or 'Human Input Required'
        form_content = form_data.get('form_content', '') or ''

        self.card_state[out_track_id] = {
            'session_key': session_key,
            'launcher_type': launcher_type.value,
            'launcher_id': launcher_id,
            'sender_user_id': sender_user_id,
            'form_token': form_data.get('form_token', ''),
            'workflow_run_id': form_data.get('workflow_run_id', ''),
            'actions': actions,
            'node_title': node_title,
            'form_content': form_content,
            'open_space_id': open_space_id,
            'is_group': is_group,
        }

        parts = []
        if node_title:
            parts.append(f'**{node_title}**')
        if form_content:
            parts.append(form_content)
        display_content = '\n\n'.join(parts) or '请选择一个操作以继续。'

        btns = []
        for idx, action in enumerate(actions):
            action_id = str(action.get('id') or '')
            title = str(action.get('title') or action_id or f'选项 {idx + 1}')
            style = (action.get('button_style') or '').lower()
            if style == 'primary' or (style == '' and idx == 0):
                color = 'blue'
            elif style == 'danger':
                color = 'red'
            else:
                color = 'gray'
            btns.append(
                {
                    'text': title,
                    'color': color,
                    'status': 'normal',
                    'event': {
                        'type': 'sendCardRequest',
                        'params': {
                            'actionId': action_id,
                            'params': {'action_id': action_id, 'out_track_id': out_track_id},
                        },
                    },
                }
            )

        try:
            if self.ap is not None:
                self.ap.logger.info(
                    f'DingTalk _send_form_card: out_track_id={out_track_id} template_id={template_id} '
                    f'open_space_id={open_space_id} is_group={is_group} btns={len(btns)}'
                )
            await self.bot.create_and_deliver_card(
                card_template_id=template_id,
                out_track_id=out_track_id,
                open_space_id=open_space_id,
                is_group=is_group,
                card_param_map={
                    'content': display_content,
                    'btns': json.dumps(btns, ensure_ascii=False),
                    'flowStatus': '3',
                },
                callback_type='STREAM',
            )
        except Exception:
            await self.logger.error(f'DingTalk: deliver form card failed: {traceback.format_exc()}')
            await self.send_message_text_form(message_source, form_data)
            self.card_state.pop(out_track_id, None)

    async def _lazy_create_resume_chat_card(
        self,
        message_source: platform_events.MessageEvent,
        message_id: str,
    ) -> typing.Optional[tuple]:
        """Create a new card for resumed-workflow streaming output.

        Used after a button click triggers a synthetic event — the form
        card stays put with the "已选择" notice, and a fresh card is
        spawned here for the LLM reply to stream into.
        """
        form_template_id = (self.config.get('human_input_card_template_id') or '').strip()
        legacy_template_id = (self.config.get('card_template_id') or '').strip()
        template_id = form_template_id or legacy_template_id
        if not template_id:
            return None
        out_track_id = uuid.uuid4().hex
        open_space_id, is_group = self._derive_open_space(message_source)
        if form_template_id:
            card_param_map = {'content': '', 'btns': '[]', 'flowStatus': '1'}
            card_data_config = None
        else:
            card_param_map = {'content': '', 'query': '...'}
            card_data_config = {'autoLayout': self.config.get('card_auto_layout', False)}
        try:
            success = await self.bot.create_and_deliver_card(
                card_template_id=template_id,
                out_track_id=out_track_id,
                open_space_id=open_space_id,
                is_group=is_group,
                card_param_map=card_param_map,
                card_data_config=card_data_config,
                callback_type='STREAM',
            )
        except Exception:
            if self.ap is not None:
                self.ap.logger.exception('DingTalk: lazy create resume chat card failed')
            return None
        if not success:
            return None
        entry = (None, out_track_id)
        self.card_instance_id_dict[message_id] = entry
        # Register as the active card so any further chunks on this turn
        # (and a subsequent re-pause) land on the same new card.
        session_key = self._session_key_from_event(message_source)
        if session_key:
            self.active_turn_card[session_key] = out_track_id
            self.active_turn_text[session_key] = ''
        return entry

    async def send_message_text_form(
        self,
        message_source: platform_events.MessageEvent,
        form_data: dict,
    ) -> None:
        """Fallback: send the human-input prompt as plain text."""
        display_text = _format_human_input_text(
            form_data.get('node_title', ''),
            form_data.get('form_content', ''),
            form_data.get('actions', []) or [],
        )
        await self._send_proactive_to_event(message_source, display_text)

    async def _send_proactive_to_event(
        self,
        message_source: platform_events.MessageEvent,
        content: str,
    ) -> None:
        """Send `content` as a proactive message to the conversation behind
        `message_source`. Used when no inbound chatbot message exists to
        anchor a card on (e.g. resumed flows triggered by card actions).
        """
        if not content:
            return
        if self.ap is not None:
            target = (
                str(message_source.group.id)
                if isinstance(message_source, platform_events.GroupMessage)
                else str(message_source.sender.id)
            )
            self.ap.logger.info(
                f'DingTalk _send_proactive_to_event: target={target} '
                f'is_group={isinstance(message_source, platform_events.GroupMessage)} content_len={len(content)}'
            )
        try:
            if isinstance(message_source, platform_events.GroupMessage):
                await self.bot.send_proactive_message_to_group(str(message_source.group.id), content)
            else:
                await self.bot.send_proactive_message_to_one(str(message_source.sender.id), content)
        except Exception:
            if self.ap is not None:
                self.ap.logger.exception('DingTalk: send proactive message failed')
            await self.logger.error(f'DingTalk: send proactive message failed: {traceback.format_exc()}')

    async def _on_card_action(self, payload: dict) -> None:
        """Translate a card button click into a synthetic query.

        Reads the clicked button's ``actionId`` (the real Dify action id —
        the ButtonGroup template sends it back via `event.params.actionId`),
        recovers the action title from ``card_state``, and enqueues a
        synthetic `_dify_form_action` query the same way Lark / Telegram do.
        """
        if self.ap is not None:
            self.ap.logger.info(
                f'DingTalk _on_card_action received: out_track_id={payload.get("out_track_id")} '
                f'payload_action_id={payload.get("action_id")!r} params={payload.get("params")!r}'
            )
        out_track_id = payload.get('out_track_id') or ''
        params = payload.get('params') or {}
        # ButtonGroup `sendCardRequest` events surface the click id at the
        # callback top level as `actionId`; fall back to `params.action_id`
        # (alternate template wiring) and `params.actionId`.
        raw_action_id = (
            (payload.get('action_id') or '').strip()
            or (params.get('action_id') or '').strip()
            or (params.get('actionId') or '').strip()
            or (params.get('id') or '').strip()
        )
        state = self.card_state.get(out_track_id)
        if state is None:
            await self.logger.warning(f'DingTalk: card action received for unknown out_track_id={out_track_id}')
            return
        if not raw_action_id:
            await self.logger.warning(f'DingTalk: card action with no action_id, payload={payload}')
            return

        actions = state.get('actions', []) or []
        action_id = raw_action_id
        action_title = raw_action_id
        for action in actions:
            if str(action.get('id', '')) == raw_action_id:
                action_title = action.get('title') or raw_action_id
                break

        launcher_type = (
            provider_session.LauncherTypes.GROUP
            if state.get('launcher_type') == provider_session.LauncherTypes.GROUP.value
            else provider_session.LauncherTypes.PERSON
        )
        launcher_id = state.get('launcher_id', '')
        sender_user_id = state.get('sender_user_id') or payload.get('user_id') or launcher_id

        form_action_data = {
            'form_token': state.get('form_token', ''),
            'workflow_run_id': state.get('workflow_run_id', ''),
            'action_id': action_id,
            'action_title': action_title,
            'node_title': state.get('node_title', ''),
            'user': f'{launcher_type.value}_{launcher_id}',
            'inputs': {},
        }

        message_chain = platform_message.MessageChain([platform_message.Plain(text=f'[Form Action: {action_title}]')])

        if launcher_type == provider_session.LauncherTypes.GROUP:
            synthetic_event = platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=sender_user_id,
                    member_name='',
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=launcher_id,
                        name='',
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                ),
                message_chain=message_chain,
                time=int(datetime.datetime.now().timestamp()),
                source_platform_object=None,
            )
        else:
            synthetic_event = platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=sender_user_id,
                    nickname='',
                    remark='',
                ),
                message_chain=message_chain,
                time=int(datetime.datetime.now().timestamp()),
                source_platform_object=None,
            )

        bot_uuid = ''
        pipeline_uuid = None
        if self.ap is not None:
            for bot in self.ap.platform_mgr.bots:
                if bot.adapter is self:
                    bot_uuid = bot.bot_entity.uuid
                    pipeline_uuid = bot.bot_entity.use_pipeline_uuid
                    break

            try:
                self.ap.logger.info(
                    f'DingTalk _on_card_action enqueuing form action: action_id={action_id!r} '
                    f'action_title={action_title!r} launcher_type={launcher_type.value} '
                    f'launcher_id={launcher_id} bot_uuid={bot_uuid} pipeline_uuid={pipeline_uuid}'
                )
                await self.ap.query_pool.add_query(
                    bot_uuid=bot_uuid,
                    launcher_type=launcher_type,
                    launcher_id=launcher_id,
                    sender_id=sender_user_id,
                    message_event=synthetic_event,
                    message_chain=message_chain,
                    adapter=self,
                    pipeline_uuid=pipeline_uuid,
                    variables={
                        '_dify_form_action': form_action_data,
                        '_routed_by_rule': True,
                    },
                )
                self.ap.logger.info('DingTalk _on_card_action: query enqueued OK')
            except Exception:
                self.ap.logger.exception('DingTalk: enqueue form action query failed')
                return

        # Visual feedback on the form card itself: keep the prompt visible,
        # add a "已选择" line, remove the buttons. The resumed-workflow
        # output lives on a separate new card (lazy-created in
        # reply_message_chunk on the synthetic event), so the form card
        # stays put as a record of the user's selection.
        asyncio.create_task(
            self._mark_card_resolved(
                out_track_id,
                action_title,
                node_title=state.get('node_title', ''),
                form_content=state.get('form_content', ''),
            )
        )

        # Crucial: do NOT leave the form card's out_track_id in
        # active_turn_card — otherwise create_message_card for the
        # synthetic event would reuse it for the resume output, painting
        # the LLM reply on top of the "已选择" notice. Clear it so the
        # resume goes through the lazy-create path and spawns a fresh card.
        session_key = state.get('session_key', '')
        if session_key and self.active_turn_card.get(session_key) == out_track_id:
            self.active_turn_card.pop(session_key, None)
            self.active_turn_text.pop(session_key, None)

        # Once consumed, drop the state — the runner clears _PENDING_FORMS too.
        self.card_state.pop(out_track_id, None)

    async def _mark_card_resolved(
        self,
        out_track_id: str,
        action_title: str,
        *,
        node_title: str = '',
        form_content: str = '',
    ) -> None:
        """Update the form card to acknowledge the user's selection.

        Keeps the original prompt visible, adds a "已选择: X" notice, and
        clears the buttons. The card stays as a permanent record of the
        choice; the resumed workflow's output goes to a separate new card.
        """
        parts: list[str] = []
        if node_title:
            parts.append(f'**{node_title}**')
        if form_content:
            parts.append(form_content)
        parts.append(f'---\n✅ 已选择：**{action_title}**')
        content = '\n\n'.join(parts)
        if self.ap is not None:
            self.ap.logger.info(f'DingTalk _mark_card_resolved: out_track_id={out_track_id} action={action_title!r}')
        try:
            await self.bot.update_card_data(
                out_track_id=out_track_id,
                card_param_map={
                    'content': content,
                    'btns': '[]',
                    'flowStatus': '3',
                },
            )
        except Exception:
            if self.ap is not None:
                self.ap.logger.exception('DingTalk: mark card resolved failed')
