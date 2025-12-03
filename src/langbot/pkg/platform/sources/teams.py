from __future__ import annotations

import typing
import asyncio
import traceback
import base64
import datetime
import aiohttp
import pydantic

from botbuilder.core import BotFrameworkAdapter, BotFrameworkAdapterSettings, TurnContext
from botbuilder.schema import Activity, ActivityTypes, ChannelAccount, ConversationAccount
from botframework.connector.auth import MicrosoftAppCredentials
from quart import Quart, request, Response

import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.platform.entities as platform_entities
import langbot_plugin.api.definition.abstract.platform.event_logger as abstract_platform_logger


class TeamsMessageConverter(abstract_platform_adapter.AbstractMessageConverter):
    """Convert messages between LangBot format and Teams Activity format"""

    @staticmethod
    async def yiri2target(message_chain: platform_message.MessageChain) -> dict:
        """Convert LangBot message chain to Teams message format"""
        text_content = []
        attachments = []

        for component in message_chain:
            if isinstance(component, platform_message.Plain):
                text_content.append(component.text)
            elif isinstance(component, platform_message.Image):
                # Teams supports image attachments
                image_data = None
                image_type = 'image/png'

                if component.base64:
                    # Extract base64 data
                    if component.base64.startswith('data:'):
                        parts = component.base64.split(',')
                        header = parts[0]
                        if 'image/' in header:
                            image_type = header.split(';')[0].replace('data:', '')
                        image_data = parts[1] if len(parts) > 1 else component.base64
                    else:
                        image_data = component.base64
                elif component.url:
                    # For URLs, Teams can display them inline
                    text_content.append(f'\n{component.url}')
                    continue
                elif component.path:
                    try:
                        with open(component.path, 'rb') as f:
                            image_bytes = f.read()
                            image_data = base64.b64encode(image_bytes).decode('utf-8')
                    except Exception:
                        continue

                if image_data:
                    # Create inline image attachment
                    attachments.append({
                        'contentType': image_type,
                        'contentUrl': f'data:{image_type};base64,{image_data}',
                        'name': 'image'
                    })

        result = {
            'text': ''.join(text_content),
        }

        if attachments:
            result['attachments'] = attachments

        return result

    @staticmethod
    async def target2yiri(activity: Activity) -> platform_message.MessageChain:
        """Convert Teams Activity to LangBot message chain"""
        components = []

        # Add message source
        components.append(
            platform_message.Source(
                id=activity.id,
                time=activity.timestamp if activity.timestamp else datetime.datetime.now()
            )
        )

        # Handle mentions (convert to At components)
        if activity.entities:
            for entity in activity.entities:
                if entity.type == 'mention':
                    mentioned = entity.mentioned
                    if mentioned:
                        components.append(platform_message.At(target=str(mentioned.id)))

        # Add text content
        if activity.text:
            text = activity.text
            # Remove bot mentions from text
            if activity.entities:
                for entity in activity.entities:
                    if entity.type == 'mention' and entity.text:
                        text = text.replace(entity.text, '').strip()

            if text:
                components.append(platform_message.Plain(text=text))

        # Handle attachments (images, files, etc.)
        if activity.attachments:
            for attachment in activity.attachments:
                if attachment.content_type and 'image' in attachment.content_type:
                    # Download and convert image to base64
                    if attachment.content_url:
                        try:
                            async with aiohttp.ClientSession() as session:
                                async with session.get(attachment.content_url) as response:
                                    image_data = await response.read()
                                    image_base64 = base64.b64encode(image_data).decode('utf-8')
                                    content_type = attachment.content_type or 'image/png'
                                    components.append(
                                        platform_message.Image(
                                            base64=f'data:{content_type};base64,{image_base64}'
                                        )
                                    )
                        except Exception:
                            pass

        return platform_message.MessageChain(components)


class TeamsEventConverter(abstract_platform_adapter.AbstractEventConverter):
    """Convert events between Teams Activity and LangBot platform events"""

    @staticmethod
    async def yiri2target(event: platform_events.Event) -> Activity:
        """Convert LangBot event to Teams Activity"""
        return event.source_platform_object

    @staticmethod
    async def target2yiri(activity: Activity, bot_id: str) -> platform_events.Event:
        """Convert Teams Activity to LangBot event"""
        message_chain = await TeamsMessageConverter.target2yiri(activity)

        # Determine if it's a personal or channel/group chat
        conversation_type = activity.conversation.conversation_type if activity.conversation else None

        if conversation_type == 'personal':
            # Personal chat (1-on-1)
            return platform_events.FriendMessage(
                sender=platform_entities.Friend(
                    id=activity.from_property.id,
                    nickname=activity.from_property.name or activity.from_property.id,
                    remark=activity.from_property.id,
                ),
                message_chain=message_chain,
                time=activity.timestamp.timestamp() if activity.timestamp else datetime.datetime.now().timestamp(),
                source_platform_object=activity,
            )
        else:
            # Channel or group chat
            return platform_events.GroupMessage(
                sender=platform_entities.GroupMember(
                    id=activity.from_property.id,
                    member_name=activity.from_property.name or activity.from_property.id,
                    permission=platform_entities.Permission.Member,
                    group=platform_entities.Group(
                        id=activity.conversation.id,
                        name=activity.conversation.name or activity.conversation.id,
                        permission=platform_entities.Permission.Member,
                    ),
                    special_title='',
                    join_timestamp=0,
                    last_speak_timestamp=0,
                    mute_time_remaining=0,
                ),
                message_chain=message_chain,
                time=activity.timestamp.timestamp() if activity.timestamp else datetime.datetime.now().timestamp(),
                source_platform_object=activity,
            )


class TeamsAdapter(abstract_platform_adapter.AbstractMessagePlatformAdapter):
    """Microsoft Teams platform adapter for LangBot"""

    adapter: BotFrameworkAdapter = pydantic.Field(exclude=True, default=None)
    app: Quart = pydantic.Field(exclude=True, default=None)
    bot_uuid: typing.Optional[str] = None

    message_converter: TeamsMessageConverter = TeamsMessageConverter()
    event_converter: TeamsEventConverter = TeamsEventConverter()

    config: dict

    listeners: typing.Dict[
        typing.Type[platform_events.Event],
        typing.Callable[[platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None],
    ] = {}

    def __init__(self, config: dict, logger: abstract_platform_logger.AbstractEventLogger, **kwargs):
        """Initialize Teams adapter with app credentials"""
        # Validate required config
        if 'app_id' not in config or 'app_password' not in config:
            raise ValueError('Teams adapter requires app_id and app_password in configuration')

        # Create Bot Framework adapter settings
        settings = BotFrameworkAdapterSettings(
            app_id=config['app_id'],
            app_password=config['app_password']
        )

        # Create Bot Framework adapter
        adapter_instance = BotFrameworkAdapter(settings)

        super().__init__(
            config=config,
            logger=logger,
            bot_account_id=config['app_id'],
            listeners={},
            **kwargs
        )

        # Set the adapter after initialization
        self.adapter = adapter_instance

    async def _handle_activity(self, activity: Activity):
        """Internal method to handle incoming activities"""
        try:
            # Only process message activities from users (not bots)
            if activity.type == ActivityTypes.message:
                if activity.from_property and not (hasattr(activity.from_property, 'role') and activity.from_property.role == 'bot'):
                    # Convert to LangBot event
                    lb_event = await self.event_converter.target2yiri(activity, self.bot_account_id)

                    # Call appropriate listener
                    event_type = type(lb_event)
                    if event_type in self.listeners:
                        await self.listeners[event_type](lb_event, self)
        except Exception as e:
            await self.logger.error(f'Error handling Teams activity: {str(e)}\n{traceback.format_exc()}')

    async def send_message(self, target_type: str, target_id: str, message: platform_message.MessageChain):
        """Send a message to a specific target"""
        try:
            message_data = await self.message_converter.yiri2target(message)

            # Create activity
            activity = Activity(
                type=ActivityTypes.message,
                text=message_data.get('text', ''),
                attachments=message_data.get('attachments', []),
                conversation=ConversationAccount(id=target_id),
            )

            # Send via Bot Framework adapter
            # Note: This requires a conversation reference which we would need to store
            # For now, this is a placeholder - full implementation would require conversation tracking
            await self.logger.warning('Direct send_message not fully implemented - use reply_message instead')
        except Exception as e:
            await self.logger.error(f'Error sending Teams message: {str(e)}')

    async def reply_message(
        self,
        message_source: platform_events.MessageEvent,
        message: platform_message.MessageChain,
        quote_origin: bool = False,
    ):
        """Reply to a message"""
        try:
            assert isinstance(message_source.source_platform_object, Activity)
            source_activity: Activity = message_source.source_platform_object

            message_data = await self.message_converter.yiri2target(message)

            # Build conversation reference from source activity
            conversation_reference = TurnContext.get_conversation_reference(source_activity)

            # Create reply activity
            async def send_reply(turn_context: TurnContext):
                reply_text = message_data.get('text', '')
                reply_attachments = message_data.get('attachments', [])

                if quote_origin:
                    # Include reply_to_id to quote the original message
                    await turn_context.send_activity(
                        Activity(
                            type=ActivityTypes.message,
                            text=reply_text,
                            attachments=reply_attachments,
                            reply_to_id=source_activity.id
                        )
                    )
                else:
                    await turn_context.send_activity(
                        Activity(
                            type=ActivityTypes.message,
                            text=reply_text,
                            attachments=reply_attachments
                        )
                    )

            # Continue conversation using the conversation reference
            await self.adapter.continue_conversation(
                conversation_reference,
                send_reply,
                self.bot_account_id
            )

        except Exception as e:
            await self.logger.error(f'Error replying to Teams message: {str(e)}\n{traceback.format_exc()}')

    def register_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        """Register event listener"""
        self.listeners[event_type] = callback

    def unregister_listener(
        self,
        event_type: typing.Type[platform_events.Event],
        _callback: typing.Callable[
            [platform_events.Event, abstract_platform_adapter.AbstractMessagePlatformAdapter], None
        ],
    ):
        """Unregister event listener"""
        if event_type in self.listeners:
            del self.listeners[event_type]

    def set_bot_uuid(self, bot_uuid: str):
        """Set bot UUID for webhook URL generation"""
        self.bot_uuid = bot_uuid

    async def handle_unified_webhook(self, _bot_uuid: str, _path: str, request_obj):
        """Handle unified webhook requests from Teams

        Args:
            _bot_uuid: Bot UUID (unused)
            _path: Sub-path (unused)
            request_obj: Quart Request object

        Returns:
            Response data
        """
        try:
            # Get request body
            body = await request_obj.get_json()

            # Get authorization header
            auth_header = request_obj.headers.get('Authorization', '')

            # Process activity
            async def bot_logic(turn_context: TurnContext):
                # Handle the activity
                await self._handle_activity(turn_context.activity)

            # Process the request through Bot Framework adapter
            await self.adapter.process_activity(body, auth_header, bot_logic)

            return Response(status=200)

        except Exception as e:
            await self.logger.error(f'Error processing Teams webhook: {str(e)}\n{traceback.format_exc()}')
            return Response(status=500)

    async def run_async(self):
        """Run the adapter - Teams uses webhook mode, so just keep alive and log webhook URL"""
        # Print webhook callback address
        if self.bot_uuid and hasattr(self.logger, 'ap'):
            try:
                api_port = self.logger.ap.instance_config.data['api']['port']
                webhook_url = f"http://127.0.0.1:{api_port}/bots/{self.bot_uuid}"
                webhook_url_public = f"http://<Your-Public-IP>:{api_port}/bots/{self.bot_uuid}"

                await self.logger.info(f"Teams Bot Webhook URL:")
                await self.logger.info(f"  Local: {webhook_url}")
                await self.logger.info(f"  Public: {webhook_url_public}")
                await self.logger.info(f"Configure this URL as the messaging endpoint in Azure Bot Service")
            except Exception as e:
                await self.logger.warning(f"Could not generate webhook URL: {e}")

        # Keep the adapter running
        async def keep_alive():
            while True:
                await asyncio.sleep(1)

        await keep_alive()

    async def kill(self) -> bool:
        """Shutdown the adapter"""
        await self.logger.info('Teams adapter stopped')
        return True
