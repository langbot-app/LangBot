from __future__ import annotations


import telegram
import telegram.ext
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ApplicationBuilder, ContextTypes, MessageHandler, CallbackQueryHandler, filters
import telegramify_markdown
import typing
import traceback
import json
import base64
import pydantic

from langbot.pkg.utils import httpclient
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class TelegramMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain, bot: telegram.Bot) -> list[dict]:
        components = []

        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                components.append({'type': 'text', 'text': component.text})
            elif isinstance(component, platform_message.Image):
                photo_bytes = None

                if component.base64:
                    photo_bytes = base64.b64decode(component.base64)
                elif component.url:
                    session = httpclient.get_session()
                    async with session.get(component.url) as response:
                        photo_bytes = await response.read()
                elif component.path:
                    with open(component.path, 'rb') as f:
                        photo_bytes = f.read()

                components.append({'type': 'photo', 'photo': photo_bytes})
            elif isinstance(component, platform_message.File):
                file_bytes = None

                if component.base64:
                    # Strip data URI prefix if present (e.g. "data:application/pdf;base64,...")
                    b64_data = component.base64
                    if ';base64,' in b64_data:
                        b64_data = b64_data.split(';base64,', 1)[1]
                    file_bytes = base64.b64decode(b64_data)
                elif component.url:
                    session = httpclient.get_session()
                    async with session.get(component.url) as response:
                        file_bytes = await response.read()
                elif component.path:
                    with open(component.path, 'rb') as f:
                        file_bytes = f.read()

                file_name = getattr(component, 'name', None) or 'file'
                components.append({'type': 'document', 'document': file_bytes, 'filename': file_name})
            elif isinstance(component, platform_message.Forward):
                for node in component.node_list:
                    components.extend(await TelegramMessageConverter.yiri2target(node.message_chain, bot))

        return components

    @staticmethod
    async def target2yiri(message: telegram.Message, bot: telegram.Bot, bot_account_id: str):
        message_components = []

        def parse_message_text(text: str) -> list[platform_message.MessageComponent]:
            msg_components = []

            if f'@{bot_account_id}' in text:
                msg_components.append(platform_message.At(target=bot_account_id))
                text = text.replace(f'@{bot_account_id}', '')
            msg_components.append(platform_message.Plain(text=text))

            return msg_components

        if message.text:
            message_text = message.text
            message_components.extend(parse_message_text(message_text))

        if message.photo:
            if message.caption:
                message_components.extend(parse_message_text(message.caption))

            file = await message.photo[-1].get_file()

            file_bytes = None
            file_format = ''

            async with httpclient.get_session(trust_env=True).get(file.file_path) as response:
                file_bytes = await response.read()
                file_format = 'image/jpeg'

            message_components.append(
                platform_message.Image(
                    base64=f'data:{file_format};base64,{base64.b64encode(file_bytes).decode("utf-8")}'
                )
            )

        if message.voice:
            if message.caption:
                message_components.extend(parse_message_text(message.caption))

            file = await message.voice.get_file()

            file_bytes = None
            file_format = message.voice.mime_type or 'audio/ogg'

            async with httpclient.get_session(trust_env=True).get(file.file_path) as response:
                file_bytes = await response.read()

            message_components.append(
                platform_message.Voice(
                    base64=f'data:{file_format};base64,{base64.b64encode(file_bytes).decode("utf-8")}',
                    length=message.voice.duration,
                )
            )

        if message.document:
            if message.caption:
                message_components.extend(parse_message_text(message.caption))

            file = await message.document.get_file()
            file_name = message.document.file_name or 'document'
            file_size = message.document.file_size or 0
            file_format = message.document.mime_type or 'application/octet-stream'

            file_bytes = None
            async with httpclient.get_session(trust_env=True).get(file.file_path) as response:
                file_bytes = await response.read()

            message_components.append(
                platform_message.File(
                    name=file_name,
                    size=file_size,
                    base64=f'data:{file_format};base64,{base64.b64encode(file_bytes).decode("utf-8")}',
                )
            )

        return platform_message.MessageChain(message_components)


class TelegramEventConverter(abstract_platform_adapter.AbstractEventConverter):
    @staticmethod
    async def yiri2target(event: platform_events.MessageEvent, bot: telegram.Bot):
        return event.source_platform_object

    @staticmethod
    async def target2yiri(event: Update, bot: telegram.Bot, bot_account_id: str):
        lb_message = await TelegramMessageConverter.target2yiri(event.message, bot, bot_account_id)

        if event.effective_chat.type == 'private':
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=event.effective_chat.id,
                    nickname=event.effective_chat.first_name,
                    remark=str(event.effective_chat.id),
                ),
                message_chain=lb_message,
                time=event.message.date.timestamp(),
                source_platform_object=event,
            )
        elif event.effective_chat.type in ('group', 'supergroup'):
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=event.effective_chat.id,
                    member_name=event.effective_chat.title,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=event.effective_chat.id,
                        name=event.effective_chat.title,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                ),
                message_chain=lb_message,
                time=event.message.date.timestamp(),
                source_platform_object=event,
            )


class TelegramAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    bot: telegram.Bot = pydantic.Field(exclude=True)
    application: telegram.ext.Application = pydantic.Field(exclude=True)
    ap: typing.Any = pydantic.Field(exclude=True, default=None)

    message_converter: TelegramMessageConverter = TelegramMessageConverter()
    event_converter: TelegramEventConverter = TelegramEventConverter()

    config: dict

    msg_stream_id: dict  # 流式消息id字典，key为流式消息id，value为首次消息源id，用于在流式消息时判断编辑那条消息

    seq: int  # 消息中识别消息顺序，直接以seq作为标识

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger):
        async def telegram_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
            if update.message.from_user.is_bot:
                return

            try:
                lb_event = await self.event_converter.target2yiri(update, self.bot, self.bot_account_id)
                await self.listeners[type(lb_event)](lb_event, self)
                await self.is_stream_output_supported()
            except Exception:
                await self.logger.error(f'Error in telegram callback: {traceback.format_exc()}')

        application = ApplicationBuilder().token(config['token']).build()
        bot = application.bot
        application.add_handler(
            MessageHandler(
                filters.TEXT | (filters.COMMAND) | filters.PHOTO | filters.VOICE | filters.Document.ALL,
                telegram_callback,
            )
        )

        async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
            query = update.callback_query
            await query.answer()
            try:
                data = json.loads(query.data)
                if data.get('form_action') or data.get('f'):
                    import langbot_plugin.api.entities.builtin.provider.session as provider_session

                    # workflow_run_id is not in the callback payload (too large
                    # for Telegram's 64-byte limit). Only w_suffix is sent;
                    # the runner resolves the full run id from _PENDING_FORMS.
                    w_suffix = data.get('w', '')
                    action_id = data.get('action_id') or data.get('a', '')
                    session_key = data.get('session_key') or data.get('s', '')

                    if session_key.startswith('group_') or session_key.startswith('g:'):
                        launcher_type = provider_session.LauncherTypes.GROUP
                        launcher_id = (
                            session_key.split(':', 1)[1]
                            if session_key.startswith('g:')
                            else session_key[len('group_') :]
                        )
                    else:
                        launcher_type = provider_session.LauncherTypes.PERSON
                        launcher_id = (
                            session_key.split(':', 1)[1]
                            if session_key.startswith('p:')
                            else session_key[len('person_') :]
                        )

                    user_id = str(query.from_user.id)

                    # Find bot_uuid and pipeline_uuid
                    bot_uuid = ''
                    pipeline_uuid = None
                    for b in self.ap.platform_mgr.bots:
                        if b.adapter is self:
                            bot_uuid = b.bot_entity.uuid
                            pipeline_uuid = b.bot_entity.use_pipeline_uuid
                            break

                    form_action_data = {
                        # workflow_run_id is intentionally omitted; the runner
                        # resolves it from w_suffix via _PENDING_FORMS.
                        'w_suffix': w_suffix,
                        'action_id': action_id,
                        'user': f'{launcher_type.value}_{launcher_id}',
                        'inputs': {},
                    }

                    message_chain = platform_message.MessageChain(
                        [platform_message.Plain(text=f'[Form Action: {action_id}]')]
                    )

                    if launcher_type == provider_session.LauncherTypes.GROUP:
                        synthetic_event = platform_events.GroupMessage(
                            sender=platform_entities.GroupMember(
                                id=user_id,
                                member_name='',
                                permission=platform_entities.Permission.Member,
                                group=platform_entities.Group(
                                    id=launcher_id,
                                    name='',
                                    permission=platform_entities.Permission.Member,
                                ),
                            ),
                            message_chain=message_chain,
                            source_platform_object=update,
                        )
                    else:
                        synthetic_event = platform_events.FriendMessage(
                            sender=platform_entities.Friend(
                                id=user_id,
                                nickname='',
                                remark='',
                            ),
                            message_chain=message_chain,
                            source_platform_object=update,
                        )

                    await self.ap.query_pool.add_query(
                        bot_uuid=bot_uuid,
                        launcher_type=launcher_type,
                        launcher_id=launcher_id,
                        sender_id=user_id,
                        message_event=synthetic_event,
                        message_chain=message_chain,
                        adapter=self,
                        pipeline_uuid=pipeline_uuid,
                        variables={
                            '_dify_form_action': form_action_data,
                            '_routed_by_rule': True,
                        },
                    )
            except Exception:
                await self.logger.error(f'Error in telegram callback query: {traceback.format_exc()}')

        application.add_handler(CallbackQueryHandler(callback_query_handler))
        super().__init__(
            config=config,
            logger=logger,
            msg_stream_id={},
            seq=1,
            bot=bot,
            application=application,
            bot_account_id='',
            listeners={},
        )

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        components = await TelegramMessageConverter.yiri2target(message, self.bot)

        chat_id_str, _, thread_id_str = str(target_id).partition('#')
        chat_id: int | str = int(chat_id_str) if chat_id_str.lstrip('-').isdigit() else chat_id_str
        message_thread_id = int(thread_id_str) if thread_id_str and thread_id_str.isdigit() else None

        for component in components:
            component_type = component.get('type')
            args = {'chat_id': chat_id}
            if message_thread_id is not None:
                args['message_thread_id'] = message_thread_id

            if component_type == 'text':
                text = component.get('text', '')
                if self.config['markdown_card'] is True:
                    text = telegramify_markdown.markdownify(content=text)
                    args['parse_mode'] = 'MarkdownV2'
                args['text'] = text
                await self.bot.send_message(**args)
            elif component_type == 'photo':
                photo = component.get('photo')
                if photo is None:
                    continue
                args['photo'] = telegram.InputFile(photo)
                await self.bot.send_photo(**args)
            elif component_type == 'document':
                doc = component.get('document')
                if doc is None:
                    continue
                filename = component.get('filename', 'file')
                args['document'] = telegram.InputFile(doc, filename=filename)
                await self.bot.send_document(**args)

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        assert isinstance(message_source.source_platform_object, Update)
        components = await TelegramMessageConverter.yiri2target(message, self.bot)

        for component in components:
            if component['type'] == 'text':
                if self.config['markdown_card'] is True:
                    content = telegramify_markdown.markdownify(
                        content=component['text'],
                    )
                else:
                    content = component['text']
                args = {
                    'chat_id': message_source.source_platform_object.effective_chat.id,
                    'text': content,
                }
                if self.config['markdown_card'] is True:
                    args['parse_mode'] = 'MarkdownV2'

        if message_source.source_platform_object.message.message_thread_id:
            args['message_thread_id'] = message_source.source_platform_object.message.message_thread_id

        if quote_origin:
            args['reply_to_message_id'] = message_source.source_platform_object.message.id

        await self.bot.send_message(**args)

    def _process_markdown(self, text: str) -> str:
        if self.config.get('markdown_card', False):
            return telegramify_markdown.markdownify(content=text)
        return text

    def _build_message_args(self, chat_id: int, text: str, message_thread_id: int = None, **extra_args) -> dict:
        args = {'chat_id': chat_id, 'text': self._process_markdown(text), **extra_args}
        if message_thread_id:
            args['message_thread_id'] = message_thread_id
        if self.config.get('markdown_card', False):
            args['parse_mode'] = 'MarkdownV2'
        return args

    async def create_message_card(self, message_id, event):
        assert isinstance(event.source_platform_object, Update)
        update = event.source_platform_object
        chat_id = update.effective_chat.id
        chat_type = update.effective_chat.type
        effective_message = update.effective_message
        message_thread_id = getattr(effective_message, 'message_thread_id', None) if effective_message else None

        if chat_type == 'private':
            import time as _time

            draft_id = int(_time.time() * 1000)
            self.msg_stream_id[message_id] = ('private', draft_id)
            args = self._build_message_args(chat_id, 'Thinking...', message_thread_id, draft_id=draft_id)
            try:
                await self.bot.send_message_draft(**args)
            except (telegram.error.RetryAfter, telegram.error.BadRequest):
                pass
        else:
            args = self._build_message_args(chat_id, 'Thinking...', message_thread_id)
            send_msg = await self.bot.send_message(**args)
            self.msg_stream_id[message_id] = ('group', send_msg.message_id)

        return True

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
        assert isinstance(message_source.source_platform_object, Update)
        update = message_source.source_platform_object
        chat_id = update.effective_chat.id
        effective_message = update.effective_message
        message_thread_id = getattr(effective_message, 'message_thread_id', None) if effective_message else None

        if message_id not in self.msg_stream_id:
            return

        chat_mode, stream_id = self.msg_stream_id[message_id]
        components = await TelegramMessageConverter.yiri2target(message, self.bot)

        if not components or components[0]['type'] != 'text':
            if is_final and bot_message.tool_calls is None:
                self.msg_stream_id.pop(message_id)
            return

        content = components[0]['text']
        form_data = getattr(bot_message, '_form_data', None)

        if form_data and is_final:
            self.msg_stream_id.pop(message_id, None)
            await self._send_form_action_buttons(message_source, form_data)
            return

        if chat_mode == 'private':
            # Streaming via draft (ephemeral preview in the chat input area)
            if (msg_seq - 1) % 8 == 0 or is_final:
                args = self._build_message_args(chat_id, content, message_thread_id, draft_id=stream_id)
                try:
                    await self.bot.send_message_draft(**args)
                except telegram.error.BadRequest as exc:
                    if 'Message_too_long' in str(exc):
                        args['text'] = content[:4000] + '\n\n… (truncated)'
                        try:
                            await self.bot.send_message_draft(**args)
                        except telegram.error.RetryAfter:
                            pass
                    else:
                        pass  # Ignore other draft errors (cosmetic)
            if is_final and bot_message.tool_calls is None:
                # Finalise: send the real message, discard the draft
                args = self._build_message_args(chat_id, content, message_thread_id)
                try:
                    await self.bot.send_message(**args)
                except telegram.error.BadRequest as exc:
                    if 'Message_too_long' in str(exc):
                        args['text'] = content[:4000] + '\n\n… (truncated)'
                        await self.bot.send_message(**args)
                    else:
                        raise
                self.msg_stream_id.pop(message_id)
        else:
            # Streaming via edit_message_text (persistent message)
            if (msg_seq - 1) % 8 == 0 or is_final:
                args = {
                    'message_id': stream_id,
                    'chat_id': chat_id,
                    'text': self._process_markdown(content),
                }
                if self.config.get('markdown_card', False):
                    args['parse_mode'] = 'MarkdownV2'
                try:
                    await self.bot.edit_message_text(**args)
                except telegram.error.BadRequest as exc:
                    if 'Message_too_long' in str(exc):
                        args['text'] = self._process_markdown(content[:4000] + '\n\n… (truncated)')
                        await self.bot.edit_message_text(**args)
                    else:
                        raise

            if is_final and bot_message.tool_calls is None:
                self.msg_stream_id.pop(message_id)

    async def _send_form_action_buttons(
        self,
        message_source: platform_events.MessageEvent,
        form_data: dict,
    ):
        """Send inline keyboard buttons for Dify human_input_required form actions."""
        actions = form_data.get('actions', [])
        node_title = form_data.get('node_title', '')
        form_content = form_data.get('form_content', '')
        workflow_run_id = form_data.get('workflow_run_id', '')
        # Telegram callback_data is capped at 64 bytes, so we identify the
        # paused workflow by the last 8 chars of workflow_run_id (unique
        # within a session with overwhelming probability).
        w_suffix = workflow_run_id[-8:] if workflow_run_id else ''

        if isinstance(message_source, platform_events.GroupMessage):
            session_key = f'g:{message_source.group.id}'
        else:
            session_key = f'p:{message_source.sender.id}'

        keyboard = []
        oversized = False
        for action in actions:
            action_id = action.get('id', '')
            action_title = action.get('title', action_id)
            callback_payload = {'f': 1, 'a': action_id, 's': session_key}
            if w_suffix:
                callback_payload['w'] = w_suffix
            callback_data = json.dumps(callback_payload, separators=(',', ':'))
            if len(callback_data.encode('utf-8')) > 64:
                oversized = True
                break
            keyboard.append([InlineKeyboardButton(action_title, callback_data=callback_data)])

        update = message_source.source_platform_object
        chat_id = update.effective_chat.id
        effective_message = update.effective_message
        message_thread_id = getattr(effective_message, 'message_thread_id', None) if effective_message else None

        text_lines = [f'[{node_title}] Please select an action:']
        if form_content:
            text_lines.insert(0, form_content)

        if oversized:
            # callback_data exceeds Telegram's 64-byte limit — fall back to
            # a plain-text numbered list so the user can reply by number.
            for idx, action in enumerate(actions, start=1):
                title = action.get('title') or action.get('id') or ''
                text_lines.append(f'  {idx}. {title}')
            args = {
                'chat_id': chat_id,
                'text': '\n\n'.join(text_lines),
            }
        else:
            reply_markup = InlineKeyboardMarkup(keyboard)
            args = {
                'chat_id': chat_id,
                'text': '\n\n'.join(text_lines),
                'reply_markup': reply_markup,
            }

        if message_thread_id:
            args['message_thread_id'] = message_thread_id

        await self.bot.send_message(**args)

    def get_launcher_id(self, event: platform_events.MessageEvent) -> str | None:
        if not isinstance(event.source_platform_object, Update):
            return None

        message = event.source_platform_object.message
        if not message:
            return None

        # specifically handle telegram forum topic and private thread(not supported by official client yet but supported by bot api)
        if message.message_thread_id:
            # check if it is a group
            if isinstance(event, platform_events.GroupMessage):
                return f'{event.group.id}#{message.message_thread_id}'
            elif isinstance(event, platform_events.FriendMessage):
                return f'{event.sender.id}#{message.message_thread_id}'

        return None

    async def is_stream_output_supported(self) -> bool:
        is_stream = False
        if self.config.get('enable-stream-reply', None):
            is_stream = True
        return is_stream

    async def is_muted(self, group_id: int) -> bool:
        return False

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
        self.listeners.pop(event_type)

    async def run_async(self):
        await self.application.initialize()
        self.bot_account_id = (await self.bot.get_me()).username
        await self.application.updater.start_polling(allowed_updates=Update.ALL_TYPES)
        await self.application.start()
        await self.logger.info('Telegram adapter running')

    async def kill(self) -> bool:
        if self.application.running:
            await self.application.stop()
            if self.application.updater:
                await self.application.updater.stop()
            await self.logger.info('Telegram adapter stopped')
        return True
