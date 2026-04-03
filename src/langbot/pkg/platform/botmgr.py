from __future__ import annotations

import asyncio
import re
import traceback
import sqlalchemy

from ..core import app, entities as core_entities, taskmgr

from ..discover import engine

from ..entity.persistence import bot as persistence_bot
from ..entity.persistence import pipeline as persistence_pipeline

from ..entity.errors import platform as platform_errors

from .logger import EventLogger

import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.platform.events as platform_events
import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.definition.abstract.platform.adapter as abstract_platform_adapter


class RuntimeBot:
    """运行时机器人"""

    ap: app.Application

    bot_entity: persistence_bot.Bot

    enable: bool

    adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter

    task_wrapper: taskmgr.TaskWrapper

    task_context: taskmgr.TaskContext

    logger: EventLogger

    def __init__(
        self,
        ap: app.Application,
        bot_entity: persistence_bot.Bot,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        logger: EventLogger,
    ):
        self.ap = ap
        self.bot_entity = bot_entity
        self.enable = bot_entity.enable
        self.adapter = adapter
        self.task_context = taskmgr.TaskContext()
        self.logger = logger

    @staticmethod
    def _match_operator(actual: str, operator: str, expected: str) -> bool:
        """Evaluate a single operator condition."""
        if operator == 'eq':
            return actual == expected
        elif operator == 'neq':
            return actual != expected
        elif operator == 'contains':
            return expected in actual
        elif operator == 'not_contains':
            return expected not in actual
        elif operator == 'starts_with':
            return actual.startswith(expected)
        elif operator == 'regex':
            try:
                return bool(re.search(expected, actual))
            except re.error:
                return False
        return False

    PIPELINE_DISCARD = '__discard__'

    def resolve_pipeline_uuid(
        self,
        launcher_type: str,
        launcher_id: str,
        message_text: str,
        message_element_types: list[str] | None = None,
    ) -> tuple[str | None, bool]:
        """Resolve pipeline UUID based on routing rules.

        Rules are evaluated in order; first match wins.
        Falls back to use_pipeline_uuid if no rule matches.

        Rule types:
          - launcher_type: session type ("person" / "group")
          - launcher_id: session / group id
          - message_content: message text content
          - message_has_element: message contains element of given type
            (Image, Voice, File, Forward, Face, At, AtAll, Quote)
            Operators: eq (has), neq (doesn't have)

        Operators: eq, neq, contains, not_contains, starts_with, regex

        When pipeline_uuid is ``__discard__``, the message should be
        silently dropped by the caller.

        Returns:
            tuple: (pipeline_uuid, routed_by_rule) - routed_by_rule is True
            when a routing rule matched, False when falling back to default.
        """
        rules = self.bot_entity.pipeline_routing_rules or []
        element_type_set = set(message_element_types or [])

        for rule in rules:
            rule_type = rule.get('type')
            operator = rule.get('operator', 'eq')
            rule_value = rule.get('value', '')
            target_uuid = rule.get('pipeline_uuid')
            if not rule_type or not target_uuid:
                continue

            if rule_type == 'launcher_type':
                if self._match_operator(launcher_type, operator, rule_value):
                    return target_uuid, True
            elif rule_type == 'launcher_id':
                if self._match_operator(str(launcher_id), operator, str(rule_value)):
                    return target_uuid, True
            elif rule_type == 'message_content':
                if self._match_operator(message_text, operator, rule_value):
                    return target_uuid, True
            elif rule_type == 'message_has_element':
                has_element = rule_value in element_type_set
                if operator == 'eq' and has_element:
                    return target_uuid, True
                elif operator == 'neq' and not has_element:
                    return target_uuid, True

        return self.bot_entity.use_pipeline_uuid, False

    async def initialize(self):
        async def on_friend_message(
            event: platform_events.FriendMessage,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            image_components = [
                component for component in event.message_chain if isinstance(component, platform_message.Image)
            ]

            await self.logger.info(
                f'{event.message_chain}',
                images=image_components,
                message_session_id=f'person_{event.sender.id}',
            )

            # Push to webhooks and check if pipeline should be skipped
            skip_pipeline = False
            if hasattr(self.ap, 'webhook_pusher') and self.ap.webhook_pusher:
                skip_pipeline = await self.ap.webhook_pusher.push_person_message(
                    event, self.bot_entity.uuid, adapter.__class__.__name__
                )

            # Only add to query pool if no webhook requested to skip pipeline
            if not skip_pipeline:
                launcher_id = event.sender.id

                if hasattr(adapter, 'get_launcher_id'):
                    custom_launcher_id = adapter.get_launcher_id(event)
                    if custom_launcher_id:
                        launcher_id = custom_launcher_id

                message_text = str(event.message_chain)
                element_types = [comp.type for comp in event.message_chain]
                pipeline_uuid, routed_by_rule = self.resolve_pipeline_uuid(
                    'person', launcher_id, message_text, element_types
                )

                if pipeline_uuid == self.PIPELINE_DISCARD:
                    await self.logger.info('Person message discarded by routing rule')
                    return

                await self.ap.msg_aggregator.add_message(
                    bot_uuid=self.bot_entity.uuid,
                    launcher_type=provider_session.LauncherTypes.PERSON,
                    launcher_id=launcher_id,
                    sender_id=event.sender.id,
                    message_event=event,
                    message_chain=event.message_chain,
                    adapter=adapter,
                    pipeline_uuid=pipeline_uuid,
                    routed_by_rule=routed_by_rule,
                )
            else:
                await self.logger.info('Pipeline skipped for person message due to webhook response')

        async def on_group_message(
            event: platform_events.GroupMessage,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            image_components = [
                component for component in event.message_chain if isinstance(component, platform_message.Image)
            ]

            await self.logger.info(
                f'{event.message_chain}',
                images=image_components,
                message_session_id=f'group_{event.group.id}',
            )

            # Push to webhooks and check if pipeline should be skipped
            skip_pipeline = False
            if hasattr(self.ap, 'webhook_pusher') and self.ap.webhook_pusher:
                skip_pipeline = await self.ap.webhook_pusher.push_group_message(
                    event, self.bot_entity.uuid, adapter.__class__.__name__
                )

            # Only add to query pool if no webhook requested to skip pipeline
            if not skip_pipeline:
                launcher_id = event.group.id

                if hasattr(adapter, 'get_launcher_id'):
                    custom_launcher_id = adapter.get_launcher_id(event)
                    if custom_launcher_id:
                        launcher_id = custom_launcher_id

                message_text = str(event.message_chain)
                element_types = [comp.type for comp in event.message_chain]
                pipeline_uuid, routed_by_rule = self.resolve_pipeline_uuid(
                    'group', launcher_id, message_text, element_types
                )

                if pipeline_uuid == self.PIPELINE_DISCARD:
                    await self.logger.info('Group message discarded by routing rule')
                    return

                await self.ap.msg_aggregator.add_message(
                    bot_uuid=self.bot_entity.uuid,
                    launcher_type=provider_session.LauncherTypes.GROUP,
                    launcher_id=launcher_id,
                    sender_id=event.sender.id,
                    message_event=event,
                    message_chain=event.message_chain,
                    adapter=adapter,
                    pipeline_uuid=pipeline_uuid,
                    routed_by_rule=routed_by_rule,
                )
            else:
                await self.logger.info('Pipeline skipped for group message due to webhook response')

        self.adapter.register_listener(platform_events.FriendMessage, on_friend_message)
        self.adapter.register_listener(platform_events.GroupMessage, on_group_message)

        # Register feedback listener (only effective on adapters that support it)
        async def on_feedback(
            event: platform_events.FeedbackEvent,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            try:
                # Resolve pipeline name
                pipeline_name = ''
                if self.bot_entity.use_pipeline_uuid:
                    try:
                        pipeline_result = await self.ap.persistence_mgr.execute_async(
                            sqlalchemy.select(persistence_pipeline.LegacyPipeline.name).where(
                                persistence_pipeline.LegacyPipeline.uuid == self.bot_entity.use_pipeline_uuid
                            )
                        )
                        pipeline_row = pipeline_result.first()
                        if pipeline_row:
                            pipeline_name = pipeline_row[0]
                    except Exception:
                        pass

                await self.ap.monitoring_service.record_feedback(
                    feedback_id=event.feedback_id,
                    feedback_type=event.feedback_type,
                    feedback_content=event.feedback_content,
                    inaccurate_reasons=event.inaccurate_reasons,
                    bot_id=self.bot_entity.uuid,
                    bot_name=self.bot_entity.name,
                    pipeline_id=self.bot_entity.use_pipeline_uuid or '',
                    pipeline_name=pipeline_name,
                    session_id=event.session_id,
                    message_id=event.message_id,
                    stream_id=event.stream_id,
                    user_id=event.user_id,
                    platform=adapter.__class__.__name__,
                )
                await self.logger.info(
                    f'Recorded feedback: feedback_id={event.feedback_id}, type={event.feedback_type}'
                )
            except Exception:
                await self.logger.error(f'Failed to record feedback: {traceback.format_exc()}')

        self.adapter.register_listener(platform_events.FeedbackEvent, on_feedback)

    async def run(self):
        async def exception_wrapper():
            try:
                self.task_context.set_current_action('Running...')
                await self.adapter.run_async()
                self.task_context.set_current_action('Exited.')
            except Exception as e:
                if isinstance(e, asyncio.CancelledError):
                    self.task_context.set_current_action('Exited.')
                    return

                traceback_str = traceback.format_exc()
                self.task_context.set_current_action('Exited with error.')
                await self.logger.error(f'平台适配器运行出错:\n{e}\n{traceback_str}')

        self.task_wrapper = self.ap.task_mgr.create_task(
            exception_wrapper(),
            kind='platform-adapter',
            name=f'platform-adapter-{self.adapter.__class__.__name__}',
            context=self.task_context,
            scopes=[
                core_entities.LifecycleControlScope.APPLICATION,
                core_entities.LifecycleControlScope.PLATFORM,
            ],
        )

    async def shutdown(self):
        await self.adapter.kill()

        self.ap.task_mgr.cancel_task(self.task_wrapper.id)


# 控制QQ消息输入输出的类
class PlatformManager:
    # ====== 4.0 ======
    ap: app.Application = None

    bots: list[RuntimeBot]

    websocket_proxy_bot: RuntimeBot

    adapter_components: list[engine.Component]

    adapter_dict: dict[str, type[abstract_platform_adapter.AbstractMessagePlatformAdapter]]

    def __init__(self, ap: app.Application = None):
        self.ap = ap
        self.bots = []
        self.adapter_components = []
        self.adapter_dict = {}

    async def initialize(self):
        # delete all bot log images
        await self.ap.storage_mgr.storage_provider.delete_dir_recursive('bot_log_images')

        disabled_adapters = self.ap.instance_config.data.get('system', {}).get('disabled_adapters', []) or []

        self.adapter_components = self.ap.discover.get_components_by_kind('MessagePlatformAdapter')
        adapter_dict: dict[str, type[abstract_platform_adapter.AbstractMessagePlatformAdapter]] = {}
        for component in self.adapter_components:
            if component.metadata.name in disabled_adapters:
                continue
            adapter_dict[component.metadata.name] = component.get_python_component_class()
        self.adapter_dict = adapter_dict

        # Filter out disabled adapters from components list (for API responses)
        if disabled_adapters:
            self.adapter_components = [c for c in self.adapter_components if c.metadata.name not in disabled_adapters]

        # initialize websocket adapter
        websocket_adapter_class = self.adapter_dict['websocket']
        websocket_logger = EventLogger(name='websocket-adapter', ap=self.ap)
        websocket_adapter_inst = websocket_adapter_class(
            {},
            websocket_logger,
            ap=self.ap,
        )

        self.websocket_proxy_bot = RuntimeBot(
            ap=self.ap,
            bot_entity=persistence_bot.Bot(
                uuid='websocket-proxy-bot',
                name='WebSocket',
                description='',
                adapter='websocket',
                adapter_config={},
                enable=True,
            ),
            adapter=websocket_adapter_inst,
            logger=websocket_logger,
        )
        await self.websocket_proxy_bot.initialize()

        await self.load_bots_from_db()

    def get_running_adapters(self) -> list[abstract_platform_adapter.AbstractMessagePlatformAdapter]:
        return [bot.adapter for bot in self.bots if bot.enable]

    async def load_bots_from_db(self):
        self.ap.logger.info('Loading bots from db...')

        self.bots = []

        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_bot.Bot))

        bots = result.all()

        for bot in bots:
            # load all bots here, enable or disable will be handled in runtime
            try:
                await self.load_bot(bot)
            except platform_errors.AdapterNotFoundError as e:
                self.ap.logger.warning(f'Adapter {e.adapter_name} not found, skipping bot {bot.uuid}')
            except Exception as e:
                self.ap.logger.error(f'Failed to load bot {bot.uuid}: {e}\n{traceback.format_exc()}')

    async def load_bot(
        self,
        bot_entity: persistence_bot.Bot | sqlalchemy.Row[persistence_bot.Bot] | dict,
    ) -> RuntimeBot:
        """加载机器人"""
        if isinstance(bot_entity, sqlalchemy.Row):
            bot_entity = persistence_bot.Bot(**bot_entity._mapping)
        elif isinstance(bot_entity, dict):
            bot_entity = persistence_bot.Bot(**bot_entity)

        logger = EventLogger(name=f'platform-adapter-{bot_entity.name}', ap=self.ap)

        if bot_entity.adapter not in self.adapter_dict:
            raise platform_errors.AdapterNotFoundError(bot_entity.adapter)

        adapter_inst = self.adapter_dict[bot_entity.adapter](
            bot_entity.adapter_config,
            logger,
        )

        # 如果 adapter 支持 set_bot_uuid 方法，设置 bot_uuid（用于统一 webhook）
        if hasattr(adapter_inst, 'set_bot_uuid'):
            adapter_inst.set_bot_uuid(bot_entity.uuid)

        runtime_bot = RuntimeBot(ap=self.ap, bot_entity=bot_entity, adapter=adapter_inst, logger=logger)

        await runtime_bot.initialize()

        self.bots.append(runtime_bot)

        return runtime_bot

    async def get_bot_by_uuid(self, bot_uuid: str) -> RuntimeBot | None:
        if self.websocket_proxy_bot and self.websocket_proxy_bot.bot_entity.uuid == bot_uuid:
            return self.websocket_proxy_bot
        for bot in self.bots:
            if bot.bot_entity.uuid == bot_uuid:
                return bot
        return None

    async def remove_bot(self, bot_uuid: str):
        for bot in self.bots:
            if bot.bot_entity.uuid == bot_uuid:
                if bot.enable:
                    await bot.shutdown()
                self.bots.remove(bot)
                return

    def get_available_adapters_info(self) -> list[dict]:
        return [
            component.to_plain_dict() for component in self.adapter_components if component.metadata.name != 'websocket'
        ]

    def get_available_adapter_info_by_name(self, name: str) -> dict | None:
        for component in self.adapter_components:
            if component.metadata.name == name:
                return component.to_plain_dict()
        return None

    def get_available_adapter_manifest_by_name(self, name: str) -> engine.Component | None:
        for component in self.adapter_components:
            if component.metadata.name == name:
                return component
        return None

    async def run(self):
        # This method will only be called when the application launching
        await self.websocket_proxy_bot.run()

        for bot in self.bots:
            if bot.enable:
                await bot.run()

    async def shutdown(self):
        for bot in self.bots:
            if bot.enable:
                await bot.shutdown()
        self.ap.task_mgr.cancel_by_scope(core_entities.LifecycleControlScope.PLATFORM)
