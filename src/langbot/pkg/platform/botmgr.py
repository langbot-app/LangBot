from __future__ import annotations

import asyncio
import dataclasses
import functools
import json
import re
import traceback
import uuid
import sqlalchemy

from ..core import app, entities as core_entities, taskmgr

from ..discover import engine

from ..entity.persistence import bot as persistence_bot
from ..entity.persistence import pipeline as persistence_pipeline
from ..entity.persistence import workspace as persistence_workspace

from ..entity.errors import platform as platform_errors
from ..api.http.context import ExecutionContext, PrincipalContext, PrincipalType, RequestContext
from ..api.http.authz import WorkspaceRequiredError

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

    execution_context: ExecutionContext

    workspace_uuid: str

    placement_generation: int

    def __init__(
        self,
        ap: app.Application,
        bot_entity: persistence_bot.Bot,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        logger: EventLogger,
        execution_context: ExecutionContext,
    ):
        if not isinstance(execution_context, ExecutionContext):
            raise WorkspaceRequiredError('RuntimeBot requires an ExecutionContext')
        if not execution_context.instance_uuid.strip() or not execution_context.workspace_uuid.strip():
            raise WorkspaceRequiredError('RuntimeBot requires an instance and Workspace')
        if execution_context.placement_generation <= 0:
            raise WorkspaceRequiredError('RuntimeBot requires a positive placement generation')
        entity_workspace_uuid = getattr(bot_entity, 'workspace_uuid', None)
        if entity_workspace_uuid != execution_context.workspace_uuid:
            raise WorkspaceRequiredError('RuntimeBot entity Workspace does not match its ExecutionContext')
        if execution_context.bot_uuid not in (None, bot_entity.uuid):
            raise WorkspaceRequiredError('RuntimeBot bot UUID does not match its ExecutionContext')

        self.ap = ap
        self.bot_entity = bot_entity
        self.execution_context = dataclasses.replace(execution_context, bot_uuid=bot_entity.uuid)
        self.workspace_uuid = self.execution_context.workspace_uuid
        self.placement_generation = self.execution_context.placement_generation
        self.enable = bot_entity.enable
        self.adapter = adapter
        self.task_context = taskmgr.TaskContext()
        self.logger = logger

    async def assert_execution_active(self) -> None:
        """Fail closed when this long-lived adapter belongs to a stale placement."""

        await self.ap.workspace_service.get_execution_binding(
            self.workspace_uuid,
            expected_generation=self.placement_generation,
        )

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
    PIPELINE_DISCARD_DISPLAY_NAME = 'Discarded'

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

    def resolve_event_pipeline_uuid(
        self,
        adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        launcher_type: str,
        launcher_id: str,
        message_text: str,
        message_element_types: list[str] | None = None,
    ) -> tuple[str | None, bool]:
        """Resolve a pipeline, honoring a trusted per-task adapter override."""

        get_override = getattr(adapter, 'get_pipeline_uuid_override', None)
        if callable(get_override):
            override = get_override()
            if override:
                return str(override), False
        return self.resolve_pipeline_uuid(
            launcher_type,
            launcher_id,
            message_text,
            message_element_types,
        )

    async def _record_discarded_message(
        self,
        launcher_type: provider_session.LauncherTypes,
        launcher_id: str | int,
        sender_id: str | int,
        message_event: platform_events.MessageEvent,
        message_chain: platform_message.MessageChain,
    ) -> None:
        """Record a discarded message in the monitoring system."""
        try:
            if hasattr(message_chain, 'model_dump'):
                message_content = json.dumps(message_chain.model_dump(), ensure_ascii=False)
            else:
                message_content = str(message_chain)

            sender_name = None
            if hasattr(message_event, 'sender'):
                if hasattr(message_event.sender, 'nickname'):
                    sender_name = message_event.sender.nickname
                elif hasattr(message_event.sender, 'member_name'):
                    sender_name = message_event.sender.member_name

            # Use the same session_id format as monitoring_helper.py
            session_id = f'{launcher_type}_{launcher_id}'
            platform = launcher_type.value if hasattr(launcher_type, 'value') else str(launcher_type)

            await self.ap.monitoring_service.record_message(
                self.execution_context,
                bot_id=self.bot_entity.uuid,
                bot_name=self.bot_entity.name or self.bot_entity.uuid,
                pipeline_id=self.PIPELINE_DISCARD,
                pipeline_name=self.PIPELINE_DISCARD_DISPLAY_NAME,
                message_content=message_content,
                session_id=session_id,
                status='discarded',
                level='info',
                platform=platform,
                user_id=str(sender_id),
                user_name=sender_name,
            )

            # Ensure the session exists so the message appears in the session monitor.
            # Don't overwrite pipeline info — a session may have messages from
            # multiple pipelines; discarding shouldn't change the displayed pipeline.
            session_updated = await self.ap.monitoring_service.update_session_activity(
                self.execution_context,
                session_id,
            )
            if not session_updated:
                # No session yet (first message for this launcher was discarded).
                await self.ap.monitoring_service.record_session_start(
                    self.execution_context,
                    session_id=session_id,
                    bot_id=self.bot_entity.uuid,
                    bot_name=self.bot_entity.name or self.bot_entity.uuid,
                    pipeline_id=self.PIPELINE_DISCARD,
                    pipeline_name=self.PIPELINE_DISCARD_DISPLAY_NAME,
                    platform=platform,
                    user_id=str(sender_id),
                    user_name=sender_name,
                )
        except Exception as e:
            await self.logger.error(f'Failed to record discarded message: {e}')

    async def initialize(self):
        def tenant_scoped_listener(listener):
            """Bind adapter callbacks to a Workspace without holding a DB transaction."""

            @functools.wraps(listener)
            async def wrapped(*args, **kwargs):
                tenant_scope = getattr(self.ap.persistence_mgr, 'tenant_scope', None)
                cloud_runtime = (
                    getattr(getattr(self.ap.persistence_mgr, 'mode', None), 'value', None) == 'cloud_runtime'
                )
                if cloud_runtime:
                    if not callable(tenant_scope):
                        raise RuntimeError('Cloud platform callbacks require an explicit tenant scope')
                    async with tenant_scope(self.workspace_uuid):
                        return await listener(*args, **kwargs)
                return await listener(*args, **kwargs)

            return wrapped

        async def on_friend_message(
            event: platform_events.FriendMessage,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            await self.assert_execution_active()
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
                    self.execution_context,
                    event,
                    self.bot_entity.uuid,
                    adapter.__class__.__name__,
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
                pipeline_uuid, routed_by_rule = self.resolve_event_pipeline_uuid(
                    adapter,
                    'person',
                    launcher_id,
                    message_text,
                    element_types,
                )

                if pipeline_uuid == self.PIPELINE_DISCARD:
                    await self.logger.info('Person message discarded by routing rule')
                    await self._record_discarded_message(
                        provider_session.LauncherTypes.PERSON,
                        launcher_id,
                        event.sender.id,
                        event,
                        event.message_chain,
                    )
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
                    execution_context=self.execution_context,
                )
            else:
                await self.logger.info('Pipeline skipped for person message due to webhook response')

        async def on_group_message(
            event: platform_events.GroupMessage,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            await self.assert_execution_active()
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
                    self.execution_context,
                    event,
                    self.bot_entity.uuid,
                    adapter.__class__.__name__,
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
                pipeline_uuid, routed_by_rule = self.resolve_event_pipeline_uuid(
                    adapter,
                    'group',
                    launcher_id,
                    message_text,
                    element_types,
                )

                if pipeline_uuid == self.PIPELINE_DISCARD:
                    await self.logger.info('Group message discarded by routing rule')
                    await self._record_discarded_message(
                        provider_session.LauncherTypes.GROUP,
                        launcher_id,
                        event.sender.id,
                        event,
                        event.message_chain,
                    )
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
                    execution_context=self.execution_context,
                )
            else:
                await self.logger.info('Pipeline skipped for group message due to webhook response')

        self.adapter.register_listener(platform_events.FriendMessage, tenant_scoped_listener(on_friend_message))
        self.adapter.register_listener(platform_events.GroupMessage, tenant_scoped_listener(on_group_message))

        # Register feedback listener (only effective on adapters that support it)
        async def on_feedback(
            event: platform_events.FeedbackEvent,
            adapter: abstract_platform_adapter.AbstractMessagePlatformAdapter,
        ):
            try:
                await self.assert_execution_active()
                # Resolve pipeline name
                pipeline_name = ''
                if self.bot_entity.use_pipeline_uuid:
                    try:
                        pipeline_result = await self.ap.persistence_mgr.execute_async(
                            sqlalchemy.select(persistence_pipeline.LegacyPipeline.name).where(
                                persistence_pipeline.LegacyPipeline.workspace_uuid == self.workspace_uuid,
                                persistence_pipeline.LegacyPipeline.uuid == self.bot_entity.use_pipeline_uuid,
                            )
                        )
                        pipeline_row = pipeline_result.first()
                        if pipeline_row:
                            pipeline_name = pipeline_row[0]
                    except Exception:
                        pass

                await self.ap.monitoring_service.record_feedback(
                    self.execution_context,
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

        self.adapter.register_listener(platform_events.FeedbackEvent, tenant_scoped_listener(on_feedback))

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

    websocket_proxy_bots: dict[str, RuntimeBot]

    adapter_components: list[engine.Component]

    adapter_dict: dict[str, type[abstract_platform_adapter.AbstractMessagePlatformAdapter]]

    def __init__(self, ap: app.Application = None):
        self.ap = ap
        self.bots = []
        self.websocket_proxy_bots = {}
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

        await self.load_bots_from_db()

        # OSS may have no persisted bots.  Its singleton Workspace still needs
        # a debug WebSocket proxy.  SaaS creates proxies lazily from an explicit
        # request/runtime context instead of guessing among Workspaces.
        if not self.websocket_proxy_bots:
            try:
                binding = await self.ap.workspace_service.get_execution_binding()
            except Exception:
                pass
            else:
                await self.get_websocket_proxy_bot(
                    ExecutionContext(
                        instance_uuid=binding.instance_uuid,
                        workspace_uuid=binding.workspace_uuid,
                        placement_generation=binding.placement_generation,
                        trigger_principal=PrincipalContext(PrincipalType.SYSTEM),
                    )
                )

    @property
    def websocket_proxy_bot(self) -> RuntimeBot:
        """Compatibility accessor that is safe only for a singleton Workspace."""

        if len(self.websocket_proxy_bots) != 1:
            raise WorkspaceRequiredError('An explicit Workspace is required for the WebSocket proxy bot')
        return next(iter(self.websocket_proxy_bots.values()))

    @websocket_proxy_bot.setter
    def websocket_proxy_bot(self, runtime_bot: RuntimeBot) -> None:
        """Keep isolated tests that inject one proxy bot working."""

        workspace_uuid = getattr(runtime_bot, 'workspace_uuid', '__test_singleton__')
        self.websocket_proxy_bots = {workspace_uuid: runtime_bot}

    @staticmethod
    def _normalize_execution_context(
        context: ExecutionContext | RequestContext,
        *,
        bot_uuid: str | None = None,
        pipeline_uuid: str | None = None,
    ) -> ExecutionContext:
        if isinstance(context, RequestContext):
            return ExecutionContext.from_request(
                context,
                bot_uuid=bot_uuid,
                pipeline_uuid=pipeline_uuid,
            )
        if not isinstance(context, ExecutionContext):
            raise WorkspaceRequiredError('Runtime operations require an ExecutionContext')
        if not context.instance_uuid.strip() or not context.workspace_uuid.strip():
            raise WorkspaceRequiredError('Runtime operations require an instance and Workspace')
        if context.placement_generation <= 0:
            raise WorkspaceRequiredError('Runtime operations require a positive placement generation')
        updates = {}
        if bot_uuid is not None:
            if context.bot_uuid not in (None, bot_uuid):
                raise WorkspaceRequiredError('Runtime bot UUID does not match its ExecutionContext')
            updates['bot_uuid'] = bot_uuid
        if pipeline_uuid is not None:
            if context.pipeline_uuid not in (None, pipeline_uuid):
                raise WorkspaceRequiredError('Runtime pipeline UUID does not match its ExecutionContext')
            updates['pipeline_uuid'] = pipeline_uuid
        return dataclasses.replace(context, **updates) if updates else context

    async def get_websocket_proxy_bot(
        self,
        context: ExecutionContext | RequestContext,
    ) -> RuntimeBot:
        execution_context = self._normalize_execution_context(context)
        existing = self.websocket_proxy_bots.get(execution_context.workspace_uuid)
        if existing is not None:
            if existing.placement_generation != execution_context.placement_generation:
                raise WorkspaceRequiredError('WebSocket proxy placement generation is stale')
            return existing

        binding = await self.ap.workspace_service.get_execution_binding(
            execution_context.workspace_uuid,
            expected_generation=execution_context.placement_generation,
        )
        websocket_adapter_class = self.adapter_dict['websocket']
        websocket_logger = EventLogger(
            name='websocket-adapter',
            ap=self.ap,
            execution_context=execution_context,
            owner='websocket-proxy-bot',
        )
        websocket_adapter_inst = websocket_adapter_class({}, websocket_logger, ap=self.ap)
        proxy_context = dataclasses.replace(
            execution_context,
            instance_uuid=binding.instance_uuid,
            bot_uuid='websocket-proxy-bot',
        )
        runtime_bot = RuntimeBot(
            ap=self.ap,
            bot_entity=persistence_bot.Bot(
                uuid='websocket-proxy-bot',
                workspace_uuid=binding.workspace_uuid,
                name='WebSocket',
                description='',
                adapter='websocket',
                adapter_config={},
                enable=True,
            ),
            adapter=websocket_adapter_inst,
            logger=websocket_logger,
            execution_context=proxy_context,
        )
        await runtime_bot.initialize()
        self.websocket_proxy_bots[binding.workspace_uuid] = runtime_bot
        return runtime_bot

    def get_running_adapters(
        self,
        context: ExecutionContext | RequestContext,
    ) -> list[abstract_platform_adapter.AbstractMessagePlatformAdapter]:
        execution_context = self._normalize_execution_context(context)
        return [
            bot.adapter for bot in self.bots if bot.enable and bot.workspace_uuid == execution_context.workspace_uuid
        ]

    async def load_bots_from_db(self):
        self.ap.logger.info('Loading bots from db...')

        self.bots = []

        instance_uow = getattr(self.ap.persistence_mgr, 'instance_discovery_uow', None)
        tenant_scope = getattr(self.ap.persistence_mgr, 'tenant_scope', None)
        if callable(instance_uow) and callable(tenant_scope):
            async with instance_uow(self.ap.workspace_service.instance_uuid) as discovery:
                workspace_uuids = list(
                    (
                        await discovery.session.scalars(
                            sqlalchemy.select(persistence_workspace.WorkspaceExecutionState.workspace_uuid)
                            .where(
                                persistence_workspace.WorkspaceExecutionState.instance_uuid
                                == self.ap.workspace_service.instance_uuid,
                                persistence_workspace.WorkspaceExecutionState.state
                                == persistence_workspace.WorkspaceExecutionStatus.ACTIVE.value,
                                persistence_workspace.WorkspaceExecutionState.write_fenced.is_(False),
                            )
                            .order_by(persistence_workspace.WorkspaceExecutionState.workspace_uuid)
                        )
                    ).all()
                )
        else:
            # Compatibility for lightweight tests and pre-tenancy managers.
            result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_bot.Bot))
            workspace_uuids = sorted({bot.workspace_uuid for bot in result.all()})

        for workspace_uuid in workspace_uuids:
            try:
                if callable(tenant_scope):
                    async with tenant_scope(workspace_uuid):
                        await self._load_workspace_bots(workspace_uuid)
                else:
                    await self._load_workspace_bots(workspace_uuid)
            except Exception as e:
                self.ap.logger.error(
                    f'Failed to load Workspace bots for {workspace_uuid}: {e}\n{traceback.format_exc()}'
                )

    async def _load_workspace_bots(self, workspace_uuid: str) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_bot.Bot)
            .where(persistence_bot.Bot.workspace_uuid == workspace_uuid)
            .order_by(persistence_bot.Bot.uuid)
        )
        for bot in result.all():
            try:
                binding = await self.ap.workspace_service.get_execution_binding(workspace_uuid)
                execution_context = ExecutionContext(
                    instance_uuid=binding.instance_uuid,
                    workspace_uuid=binding.workspace_uuid,
                    placement_generation=binding.placement_generation,
                    bot_uuid=bot.uuid,
                    trigger_principal=PrincipalContext(PrincipalType.SYSTEM),
                )
                await self.load_bot(execution_context, bot)
            except platform_errors.AdapterNotFoundError as e:
                self.ap.logger.warning(f'Adapter {e.adapter_name} not found, skipping bot {bot.uuid}')
            except Exception as e:
                self.ap.logger.error(f'Failed to load bot {bot.uuid}: {e}\n{traceback.format_exc()}')

    async def load_bot(
        self,
        context: ExecutionContext | RequestContext,
        bot_entity: persistence_bot.Bot | sqlalchemy.Row[persistence_bot.Bot] | dict,
    ) -> RuntimeBot:
        """加载机器人"""
        if isinstance(bot_entity, sqlalchemy.Row):
            bot_entity = persistence_bot.Bot(**bot_entity._mapping)
        elif isinstance(bot_entity, dict):
            bot_entity = persistence_bot.Bot(**bot_entity)

        execution_context = self._normalize_execution_context(context, bot_uuid=bot_entity.uuid)
        if bot_entity.workspace_uuid != execution_context.workspace_uuid:
            raise WorkspaceRequiredError('Bot entity Workspace does not match its runtime context')
        await self.ap.workspace_service.get_execution_binding(
            execution_context.workspace_uuid,
            expected_generation=execution_context.placement_generation,
        )

        logger = EventLogger(
            name=f'platform-adapter-{bot_entity.name}',
            ap=self.ap,
            execution_context=execution_context,
            owner=bot_entity.uuid,
        )

        if bot_entity.adapter not in self.adapter_dict:
            raise platform_errors.AdapterNotFoundError(bot_entity.adapter)

        adapter_inst = self.adapter_dict[bot_entity.adapter](
            bot_entity.adapter_config,
            logger,
        )
        if hasattr(adapter_inst, 'ap'):
            adapter_inst.ap = self.ap

        # 如果 adapter 支持 set_bot_uuid 方法，设置 bot_uuid（用于统一 webhook）
        if hasattr(adapter_inst, 'set_bot_uuid'):
            adapter_inst.set_bot_uuid(bot_entity.uuid)

        runtime_bot = RuntimeBot(
            ap=self.ap,
            bot_entity=bot_entity,
            adapter=adapter_inst,
            logger=logger,
            execution_context=execution_context,
        )

        await runtime_bot.initialize()

        self.bots.append(runtime_bot)

        return runtime_bot

    async def get_bot_by_uuid(
        self,
        context: ExecutionContext | RequestContext,
        bot_uuid: str,
    ) -> RuntimeBot | None:
        execution_context = self._normalize_execution_context(context, bot_uuid=bot_uuid)
        proxy_bot = self.websocket_proxy_bots.get(execution_context.workspace_uuid)
        if proxy_bot and proxy_bot.bot_entity.uuid == bot_uuid:
            if proxy_bot.placement_generation != execution_context.placement_generation:
                return None
            return proxy_bot
        for bot in self.bots:
            if (
                bot.workspace_uuid == execution_context.workspace_uuid
                and bot.placement_generation == execution_context.placement_generation
                and bot.bot_entity.uuid == bot_uuid
            ):
                return bot
        return None

    async def resolve_public_bot(self, route_key: str) -> RuntimeBot | None:
        """Resolve an opaque public bot UUID without consulting request headers."""

        try:
            normalized = str(uuid.UUID(route_key))
        except (ValueError, AttributeError, TypeError):
            return None
        for bot in self.bots:
            if bot.bot_entity.uuid == normalized:
                try:
                    await self.ap.workspace_service.get_execution_binding(
                        bot.workspace_uuid,
                        expected_generation=bot.placement_generation,
                    )
                except Exception:
                    return None
                return bot
        return None

    async def remove_bot(
        self,
        context: ExecutionContext | RequestContext,
        bot_uuid: str,
    ) -> None:
        execution_context = self._normalize_execution_context(context, bot_uuid=bot_uuid)
        for bot in self.bots[:]:
            if bot.workspace_uuid == execution_context.workspace_uuid and bot.bot_entity.uuid == bot_uuid:
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
        for proxy_bot in self.websocket_proxy_bots.values():
            await proxy_bot.run()

        for bot in self.bots:
            if bot.enable:
                await bot.run()

    async def shutdown(self):
        for proxy_bot in self.websocket_proxy_bots.values():
            if proxy_bot.enable:
                await proxy_bot.shutdown()
        for bot in self.bots:
            if bot.enable:
                await bot.shutdown()
        self.ap.task_mgr.cancel_by_scope(core_entities.LifecycleControlScope.PLATFORM)
