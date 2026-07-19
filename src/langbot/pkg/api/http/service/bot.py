from __future__ import annotations

import uuid
import sqlalchemy
import typing

from ....core import app
from ....discover import engine
from ....entity.persistence import agent as persistence_agent
from ....entity.persistence import bot as persistence_bot
from ....entity.persistence import pipeline as persistence_pipeline


class BotService:
    """Bot service"""

    ap: app.Application
    FAILURE_ROUTE_NOT_FOUND = 'route_not_found'
    FAILURE_PROCESSOR_DISABLED = 'processor_disabled'
    FAILURE_PROCESSOR_NOT_FOUND = 'processor_not_found'
    FAILURE_PROCESSOR_INCOMPATIBLE = 'processor_incompatible'
    FAILURE_INVALID_EVENT = 'invalid_event'
    ROUTE_TRACE_KIND = 'event_route_trace'

    BOT_FIELDS = {
        'uuid',
        'name',
        'description',
        'adapter',
        'adapter_config',
        'enable',
        'event_bindings',
    }

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    def _get_adapter_component(self, adapter_name: str) -> engine.Component | None:
        """Return the discovered platform adapter component for an adapter name."""
        for component in self.ap.discover.get_components_by_kind('MessagePlatformAdapter'):
            if component.metadata.name == adapter_name:
                return component
        return None

    def _adapter_declares_webhook_url(self, adapter_name: str) -> bool:
        """Whether the adapter manifest declares a generated webhook URL config item."""
        component = self._get_adapter_component(adapter_name)
        if component is None:
            return False

        for config_item in component.spec.get('config', []):
            if config_item.get('type') == 'webhook-url':
                return True
        return False

    @staticmethod
    def _is_message_event_pattern(event_pattern: str) -> bool:
        return event_pattern == 'message.*' or event_pattern.startswith('message.')

    @staticmethod
    def _event_pattern_covers(supported_pattern: str, binding_pattern: str) -> bool:
        if supported_pattern == '*':
            return True
        if supported_pattern == binding_pattern:
            return True
        if binding_pattern == '*':
            return False
        if supported_pattern.endswith('.*'):
            namespace = supported_pattern[:-2]
            return binding_pattern == f'{namespace}.*' or binding_pattern.startswith(f'{namespace}.')
        return False

    @classmethod
    def _agent_supports_event_pattern(cls, supported_patterns: list[str] | None, event_pattern: str) -> bool:
        patterns = supported_patterns or ['*']
        return any(cls._event_pattern_covers(pattern, event_pattern) for pattern in patterns)

    @staticmethod
    def _format_diagnostic_step(step: dict[str, typing.Any]) -> str:
        step_name = step.get('step') or 'diagnostic'
        reason = step.get('reason') or step.get('failure_code') or 'No reason provided'

        if step_name == 'evaluate_binding':
            route_number = step.get('binding_index')
            if not isinstance(route_number, int):
                route_number = step.get('order')
            route_label = f'Route {int(route_number) + 1}' if isinstance(route_number, int) else 'Route'
            event_pattern = step.get('event_pattern') or '*'
            if step.get('selected'):
                return f'{route_label} ({event_pattern}) selected: {reason}'
            if step.get('matched'):
                return f'{route_label} ({event_pattern}) matched: {reason}'
            return f'{route_label} ({event_pattern}) skipped: {reason}'

        if step_name == 'validate_processor':
            target_type = step.get('target_type') or 'processor'
            target_uuid = step.get('target_uuid') or ''
            suffix = f' {target_uuid}' if target_uuid else ''
            return f'Validate {target_type}{suffix}: {reason}'

        return str(reason)

    @classmethod
    def _format_diagnostic_steps(cls, diagnostic_details: list[dict[str, typing.Any]] | None) -> list[str]:
        return [cls._format_diagnostic_step(step) for step in diagnostic_details or []]

    @classmethod
    def _event_route_status_from_log(cls, log: typing.Any) -> dict[str, typing.Any] | None:
        if hasattr(log, 'to_json'):
            log_data = log.to_json()
        elif isinstance(log, dict):
            log_data = log
        else:
            log_data = {
                'seq_id': getattr(log, 'seq_id', None),
                'timestamp': getattr(log, 'timestamp', None),
                'level': getattr(getattr(log, 'level', None), 'value', getattr(log, 'level', None)),
                'text': getattr(log, 'text', None),
                'metadata': getattr(log, 'metadata', None),
            }

        metadata = log_data.get('metadata')
        if not isinstance(metadata, dict) or metadata.get('kind') != cls.ROUTE_TRACE_KIND:
            return None

        return {
            'binding_id': metadata.get('binding_id'),
            'event_pattern': metadata.get('event_pattern'),
            'event_type': metadata.get('event_type'),
            'target_type': metadata.get('target_type'),
            'target_uuid': metadata.get('target_uuid') or '',
            'last_status': metadata.get('status'),
            'failure_code': metadata.get('failure_code'),
            'reason': metadata.get('reason') or log_data.get('text') or '',
            'run_id': metadata.get('run_id'),
            'timestamp': log_data.get('timestamp'),
            'seq_id': log_data.get('seq_id'),
            'level': log_data.get('level'),
            'message': log_data.get('text') or '',
        }

    @staticmethod
    def _target_kind(target_type: typing.Any, target_kind: str | None = None) -> str | None:
        if target_kind:
            return target_kind
        if target_type == 'discard':
            return 'discard'
        if target_type in {'agent', 'pipeline'}:
            return str(target_type)
        return None

    @classmethod
    def _diagnostic_result(
        cls,
        *,
        matched: bool,
        failure_code: str | None = None,
        reason: str = '',
        binding: dict[str, typing.Any] | None = None,
        diagnostic_steps: list[dict[str, typing.Any]] | None = None,
        target_name: str | None = None,
        target_kind: str | None = None,
    ) -> dict[str, typing.Any]:
        binding = binding or {}
        target_type = binding.get('target_type')
        target_uuid = binding.get('target_uuid') or ''
        matched_binding_index = binding.get('_dry_run_index')
        if not isinstance(matched_binding_index, int):
            matched_binding_index = binding.get('order')
        if not isinstance(matched_binding_index, int):
            matched_binding_index = None
        target = None
        if target_type:
            target = {
                'target_type': target_type,
                'target_uuid': target_uuid or None,
                'target_name': target_name,
                'kind': cls._target_kind(target_type, target_kind),
            }
        return {
            'matched': matched,
            'binding_id': binding.get('id'),
            'matched_binding_id': binding.get('id'),
            'matched_binding_index': matched_binding_index,
            'event_pattern': binding.get('event_pattern'),
            'target_type': binding.get('target_type'),
            'target_uuid': target_uuid,
            'target': target,
            'reason': reason,
            'failure_code': failure_code,
            'diagnostic_steps': cls._format_diagnostic_steps(diagnostic_steps),
            'diagnostic_details': diagnostic_steps or [],
        }

    @staticmethod
    def _build_dry_run_event(event_type: str, event_data: typing.Any, context: typing.Any) -> dict[str, typing.Any]:
        event: dict[str, typing.Any] = {}
        if isinstance(event_data, dict):
            event.update(event_data)
        elif event_data is not None:
            raise ValueError('event_data must be an object')
        event['type'] = event_type

        if context is None:
            return event
        if not isinstance(context, dict):
            raise ValueError('context must be an object')
        event['context'] = context
        return event

    @staticmethod
    def _normalize_dry_run_bindings(bindings: typing.Any) -> list[dict[str, typing.Any]]:
        if bindings is None:
            return []
        if not isinstance(bindings, list):
            raise ValueError('event_bindings must be an array')

        normalized: list[dict[str, typing.Any]] = []
        for index, raw_binding in enumerate(bindings):
            if not isinstance(raw_binding, dict):
                continue
            event_pattern = str(raw_binding.get('event_pattern') or '').strip()
            target_type = str(raw_binding.get('target_type') or '').strip()
            if not event_pattern or not target_type:
                continue

            try:
                priority = int(raw_binding.get('priority') or 0)
            except (TypeError, ValueError):
                priority = 0

            target_uuid = str(raw_binding.get('target_uuid') or '').strip()
            if target_type == 'discard':
                target_uuid = ''

            filters = raw_binding.get('filters') if isinstance(raw_binding.get('filters'), list) else []
            normalized.append(
                {
                    'id': raw_binding.get('id'),
                    'event_pattern': event_pattern,
                    'target_type': target_type,
                    'target_uuid': target_uuid,
                    'filters': filters,
                    'priority': priority,
                    'enabled': bool(raw_binding.get('enabled', True)),
                    # For draft bindings, current array order is the effective order
                    # that would be persisted on save.
                    'order': index,
                    '_dry_run_index': index,
                }
            )
        return normalized

    @staticmethod
    def _index_event_bindings(bindings: list[dict[str, typing.Any]]) -> list[dict[str, typing.Any]]:
        indexed: list[dict[str, typing.Any]] = []
        for index, binding in enumerate(bindings):
            copied = binding.copy()
            copied.setdefault('_dry_run_index', index)
            indexed.append(copied)
        return indexed

    async def _get_pipeline_entity(self, pipeline_uuid: str) -> persistence_pipeline.LegacyPipeline | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
            )
        )
        return result.first()

    async def _get_agent_entity(self, agent_uuid: str) -> persistence_agent.Agent | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_agent.Agent).where(persistence_agent.Agent.uuid == agent_uuid)
        )
        return result.first()

    async def dry_run_event_route(
        self,
        bot_uuid: str,
        event_type: str,
        event_data: dict[str, typing.Any] | None = None,
        context: dict[str, typing.Any] | None = None,
        event_bindings: list[dict[str, typing.Any]] | None = None,
    ) -> dict[str, typing.Any]:
        """Diagnose Bot event routing without dispatching to Agent, Pipeline, or platform actions."""
        from ....platform.botmgr import RuntimeBot

        event_type = str(event_type or '').strip()
        if not event_type:
            return self._diagnostic_result(
                matched=False,
                failure_code=self.FAILURE_INVALID_EVENT,
                reason='event_type is required',
                diagnostic_steps=[
                    {
                        'step': 'validate_event',
                        'matched': False,
                        'failure_code': self.FAILURE_INVALID_EVENT,
                        'reason': 'event_type is required',
                    }
                ],
            )

        bot = await self.get_bot(bot_uuid, include_secret=False)
        if bot is None:
            raise Exception('Bot not found')

        try:
            event = self._build_dry_run_event(event_type, event_data, context)
            bindings = (
                self._normalize_dry_run_bindings(event_bindings)
                if event_bindings is not None
                else self._index_event_bindings(
                    RuntimeBot._get_event_bindings_from_value(bot.get('event_bindings') or [])
                )
            )
        except ValueError as exc:
            return self._diagnostic_result(
                matched=False,
                failure_code=self.FAILURE_INVALID_EVENT,
                reason=str(exc),
                diagnostic_steps=[
                    {
                        'step': 'validate_event',
                        'matched': False,
                        'failure_code': self.FAILURE_INVALID_EVENT,
                        'reason': str(exc),
                    }
                ],
            )

        selected_binding, diagnostic_steps = RuntimeBot._evaluate_eba_event_bindings(
            bindings,
            event,
            event_type,
        )
        if selected_binding is None:
            return self._diagnostic_result(
                matched=False,
                failure_code=self.FAILURE_ROUTE_NOT_FOUND,
                reason='No enabled event binding matched event_type and filters',
                diagnostic_steps=diagnostic_steps,
            )

        target_type = selected_binding.get('target_type')
        target_uuid = str(selected_binding.get('target_uuid') or '')

        if target_type == 'discard':
            return self._diagnostic_result(
                matched=True,
                binding=selected_binding,
                reason='Event route matched discard target',
                diagnostic_steps=diagnostic_steps,
            )

        if target_type == 'pipeline':
            if not RuntimeBot._is_message_event_type(event_type):
                return self._diagnostic_result(
                    matched=False,
                    binding=selected_binding,
                    failure_code=self.FAILURE_PROCESSOR_INCOMPATIBLE,
                    reason='Pipeline targets only support message events',
                    diagnostic_steps=diagnostic_steps
                    + [
                        {
                            'step': 'validate_processor',
                            'binding_id': selected_binding.get('id'),
                            'target_type': target_type,
                            'target_uuid': target_uuid,
                            'matched': False,
                            'failure_code': self.FAILURE_PROCESSOR_INCOMPATIBLE,
                            'reason': 'Pipeline targets only support message events',
                        }
                    ],
                )
            pipeline = await self._get_pipeline_entity(target_uuid) if target_uuid else None
            if pipeline is None:
                return self._diagnostic_result(
                    matched=False,
                    binding=selected_binding,
                    failure_code=self.FAILURE_PROCESSOR_NOT_FOUND,
                    reason='Pipeline target not found',
                    diagnostic_steps=diagnostic_steps
                    + [
                        {
                            'step': 'validate_processor',
                            'binding_id': selected_binding.get('id'),
                            'target_type': target_type,
                            'target_uuid': target_uuid,
                            'matched': False,
                            'failure_code': self.FAILURE_PROCESSOR_NOT_FOUND,
                            'reason': 'Pipeline target not found',
                        }
                    ],
                )
            return self._diagnostic_result(
                matched=True,
                binding=selected_binding,
                target_name=getattr(pipeline, 'name', None),
                reason='Event route matched pipeline target',
                diagnostic_steps=diagnostic_steps,
            )

        if target_type == 'agent':
            agent = await self._get_agent_entity(target_uuid)
            if agent is None or getattr(agent, 'kind', 'agent') != 'agent':
                return self._diagnostic_result(
                    matched=False,
                    binding=selected_binding,
                    failure_code=self.FAILURE_PROCESSOR_NOT_FOUND,
                    reason='Agent target not found',
                    diagnostic_steps=diagnostic_steps
                    + [
                        {
                            'step': 'validate_processor',
                            'binding_id': selected_binding.get('id'),
                            'target_type': target_type,
                            'target_uuid': target_uuid,
                            'matched': False,
                            'failure_code': self.FAILURE_PROCESSOR_NOT_FOUND,
                            'reason': 'Agent target not found',
                        }
                    ],
                )
            if not getattr(agent, 'enabled', True):
                return self._diagnostic_result(
                    matched=False,
                    binding=selected_binding,
                    failure_code=self.FAILURE_PROCESSOR_DISABLED,
                    reason='Agent target is disabled',
                    diagnostic_steps=diagnostic_steps
                    + [
                        {
                            'step': 'validate_processor',
                            'binding_id': selected_binding.get('id'),
                            'target_type': target_type,
                            'target_uuid': target_uuid,
                            'matched': False,
                            'failure_code': self.FAILURE_PROCESSOR_DISABLED,
                            'reason': 'Agent target is disabled',
                        }
                    ],
                )
            if not RuntimeBot._agent_supports_event_type(getattr(agent, 'supported_event_patterns', None), event_type):
                return self._diagnostic_result(
                    matched=False,
                    binding=selected_binding,
                    failure_code=self.FAILURE_PROCESSOR_INCOMPATIBLE,
                    reason='Agent target does not support this event type',
                    diagnostic_steps=diagnostic_steps
                    + [
                        {
                            'step': 'validate_processor',
                            'binding_id': selected_binding.get('id'),
                            'target_type': target_type,
                            'target_uuid': target_uuid,
                            'matched': False,
                            'failure_code': self.FAILURE_PROCESSOR_INCOMPATIBLE,
                            'reason': 'Agent target does not support this event type',
                        }
                    ],
                )
            return self._diagnostic_result(
                matched=True,
                binding=selected_binding,
                target_name=getattr(agent, 'name', None),
                target_kind=getattr(agent, 'kind', None),
                reason='Event route matched agent target',
                diagnostic_steps=diagnostic_steps,
            )

        return self._diagnostic_result(
            matched=False,
            binding=selected_binding,
            failure_code=self.FAILURE_PROCESSOR_INCOMPATIBLE,
            reason=f'Unsupported event binding target type: {target_type}',
            diagnostic_steps=diagnostic_steps
            + [
                {
                    'step': 'validate_processor',
                    'binding_id': selected_binding.get('id'),
                    'target_type': target_type,
                    'target_uuid': target_uuid,
                    'matched': False,
                    'failure_code': self.FAILURE_PROCESSOR_INCOMPATIBLE,
                    'reason': f'Unsupported event binding target type: {target_type}',
                }
            ],
        )

    async def _normalize_event_bindings(self, bindings: list[dict] | None) -> list[dict]:
        """Validate and normalize Bot event bindings."""
        if not bindings:
            return []

        normalized: list[dict] = []
        for index, raw_binding in enumerate(bindings):
            if not isinstance(raw_binding, dict):
                continue

            event_pattern = str(raw_binding.get('event_pattern') or '').strip()
            target_type = str(raw_binding.get('target_type') or '').strip()
            target_uuid = str(raw_binding.get('target_uuid') or '').strip()
            if not event_pattern or not target_type:
                continue

            if target_type == 'pipeline':
                if not self._is_message_event_pattern(event_pattern):
                    raise ValueError('Pipeline can only be bound to message events')
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(persistence_pipeline.LegacyPipeline.uuid).where(
                        persistence_pipeline.LegacyPipeline.uuid == target_uuid
                    )
                )
                if result.first() is None:
                    raise ValueError('Pipeline not found')
            elif target_type == 'agent':
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(persistence_agent.Agent).where(persistence_agent.Agent.uuid == target_uuid)
                )
                agent = result.first()
                if agent is None:
                    raise ValueError('Agent not found')
                if not self._agent_supports_event_pattern(agent.supported_event_patterns, event_pattern):
                    raise ValueError('Agent does not support this event pattern')
            elif target_type == 'discard':
                target_uuid = ''
            else:
                raise ValueError(f'Unsupported event binding target type: {target_type}')

            normalized.append(
                {
                    'id': raw_binding.get('id') or str(uuid.uuid4()),
                    'event_pattern': event_pattern,
                    'target_type': target_type,
                    'target_uuid': target_uuid,
                    'filters': raw_binding.get('filters') or [],
                    'priority': int(raw_binding.get('priority') or 0),
                    'enabled': bool(raw_binding.get('enabled', True)),
                    'description': raw_binding.get('description') or '',
                    'order': index,
                }
            )

        return normalized

    async def _prepare_bot_data(self, bot_data: dict, *, include_uuid: bool) -> dict:
        """Normalize Bot write payloads to the current event-routing model."""
        update_data = bot_data.copy()
        if not include_uuid:
            update_data.pop('uuid', None)

        update_data = {key: value for key, value in update_data.items() if key in self.BOT_FIELDS}
        if 'event_bindings' in update_data:
            update_data['event_bindings'] = await self._normalize_event_bindings(update_data.get('event_bindings'))
        return update_data

    async def get_bots(self, include_secret: bool = True) -> list[dict]:
        """获取所有机器人"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_bot.Bot))

        bots = result.all()

        masked_columns = []
        if not include_secret:
            masked_columns = ['adapter_config']

        return [self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot, masked_columns) for bot in bots]

    async def get_bot(self, bot_uuid: str, include_secret: bool = True) -> dict | None:
        """获取机器人"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid)
        )

        bot = result.first()

        if bot is None:
            return None

        masked_columns = []
        if not include_secret:
            masked_columns = ['adapter_config']

        return self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot, masked_columns)

    async def get_runtime_bot_info(self, bot_uuid: str, include_secret: bool = True) -> dict:
        """获取机器人运行时信息"""
        persistence_bot = await self.get_bot(bot_uuid, include_secret)
        if persistence_bot is None:
            raise Exception('Bot not found')

        adapter_runtime_values = {}

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is not None:
            adapter_runtime_values['bot_account_id'] = runtime_bot.adapter.bot_account_id

        # Webhook URL for adapters that declare a generated webhook config item.
        # This is manifest-driven so EBA adapters do not need to be mirrored in a
        # second hard-coded list.
        if self._adapter_declares_webhook_url(persistence_bot['adapter']):
            webhook_prefix = self.ap.instance_config.data['api'].get('webhook_prefix', 'http://127.0.0.1:5300')
            extra_webhook_prefix = self.ap.instance_config.data['api'].get('extra_webhook_prefix', '')
            webhook_url = f'/bots/{bot_uuid}'
            adapter_runtime_values['webhook_url'] = webhook_url
            adapter_runtime_values['webhook_full_url'] = f'{webhook_prefix}{webhook_url}'
            adapter_runtime_values['extra_webhook_full_url'] = (
                f'{extra_webhook_prefix}{webhook_url}' if extra_webhook_prefix else ''
            )
        else:
            adapter_runtime_values['webhook_url'] = None
            adapter_runtime_values['webhook_full_url'] = None
            adapter_runtime_values['extra_webhook_full_url'] = None

        persistence_bot['adapter_runtime_values'] = adapter_runtime_values

        return persistence_bot

    async def create_bot(self, bot_data: dict) -> str:
        """Create bot"""
        # Check limitation
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_bots = limitation.get('max_bots', -1)
        if max_bots >= 0:
            existing_bots = await self.get_bots()
            if len(existing_bots) >= max_bots:
                raise ValueError(f'Maximum number of bots ({max_bots}) reached')

        # TODO: 检查配置信息格式
        bot_data = await self._prepare_bot_data(bot_data, include_uuid=True)
        bot_data['uuid'] = str(uuid.uuid4())
        bot_data.setdefault('event_bindings', [])

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_bot.Bot).values(bot_data))

        bot = await self.get_bot(bot_data['uuid'])

        runtime_bot = await self.ap.platform_mgr.load_bot(bot)
        if runtime_bot.enable:
            await runtime_bot.run()

        return bot_data['uuid']

    async def update_bot(self, bot_uuid: str, bot_data: dict) -> None:
        """Update bot"""
        update_data = await self._prepare_bot_data(bot_data, include_uuid=False)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_bot.Bot).values(update_data).where(persistence_bot.Bot.uuid == bot_uuid)
        )
        await self.ap.platform_mgr.remove_bot(bot_uuid)

        # select from db
        bot = await self.get_bot(bot_uuid)

        runtime_bot = await self.ap.platform_mgr.load_bot(bot)

        if runtime_bot.enable:
            await runtime_bot.run()

        # update all conversation that use this bot
        for session in self.ap.sess_mgr.session_list:
            if session.using_conversation is not None and session.using_conversation.bot_uuid == bot_uuid:
                session.using_conversation = None

    async def delete_bot(self, bot_uuid: str) -> None:
        """Delete bot"""
        await self.ap.platform_mgr.remove_bot(bot_uuid)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid)
        )

    async def list_event_logs(
        self, bot_uuid: str, from_index: int, max_count: int
    ) -> typing.Tuple[list[dict], int, int, int]:
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None:
            raise Exception('Bot not found')

        logs, total_count = await runtime_bot.logger.get_logs(from_index, max_count)

        return [log.to_json() for log in logs], total_count

    async def list_event_route_statuses(self, bot_uuid: str) -> dict[str, typing.Any]:
        """Return recent runtime status for Bot event routes from in-memory Bot logs."""
        from ....platform.botmgr import RuntimeBot

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None:
            raise Exception('Bot not found')

        latest_by_binding: dict[str, dict[str, typing.Any]] = {}
        unmatched_events: list[dict[str, typing.Any]] = []
        for log in getattr(runtime_bot.logger, 'logs', []):
            status = self._event_route_status_from_log(log)
            if status is None:
                continue
            binding_id = status.get('binding_id')
            if binding_id:
                latest_by_binding[str(binding_id)] = status
            else:
                unmatched_events.append(status)

        raw_bindings = getattr(getattr(runtime_bot, 'bot_entity', None), 'event_bindings', [])
        bindings = RuntimeBot._get_event_bindings_from_value(raw_bindings)
        routes: list[dict[str, typing.Any]] = []
        current_binding_ids: set[str] = set()
        for index, binding in enumerate(bindings):
            binding_id = binding.get('id')
            if binding_id:
                current_binding_ids.add(str(binding_id))
            route_status = {
                'binding_id': binding_id,
                'event_pattern': binding.get('event_pattern'),
                'event_type': None,
                'target_type': binding.get('target_type'),
                'target_uuid': binding.get('target_uuid') or '',
                'last_status': None,
                'failure_code': None,
                'reason': None,
                'run_id': None,
                'timestamp': None,
                'seq_id': None,
                'level': None,
                'message': '',
                'order': binding.get('order', index),
                'enabled': binding.get('enabled', True),
                'current': True,
            }
            if binding_id and str(binding_id) in latest_by_binding:
                route_status.update(latest_by_binding[str(binding_id)])
                route_status['order'] = binding.get('order', index)
                route_status['enabled'] = binding.get('enabled', True)
                route_status['current'] = True
            routes.append(route_status)

        stale_routes = [
            {**status, 'current': False}
            for binding_id, status in latest_by_binding.items()
            if binding_id not in current_binding_ids
        ]

        return {
            'routes': routes,
            'unmatched_events': unmatched_events[-10:],
            'stale_routes': stale_routes,
        }

    async def dispatch_test_event_route(
        self,
        bot_uuid: str,
        event_type: str,
        payload: dict[str, typing.Any] | None = None,
    ) -> dict[str, typing.Any]:
        """Dispatch a synthetic event through the saved Bot runtime route configuration."""
        event_type = str(event_type or '').strip()
        if not event_type:
            return {
                'dispatched': False,
                'event_type': '',
                'failure_code': self.FAILURE_INVALID_EVENT,
                'reason': 'event_type is required',
                'suppressed_outputs': [],
                'route_status': {
                    'routes': [],
                    'unmatched_events': [],
                    'stale_routes': [],
                },
            }
        if payload is not None and not isinstance(payload, dict):
            return {
                'dispatched': False,
                'event_type': event_type,
                'failure_code': self.FAILURE_INVALID_EVENT,
                'reason': 'payload must be an object',
                'suppressed_outputs': [],
                'route_status': {
                    'routes': [],
                    'unmatched_events': [],
                    'stale_routes': [],
                },
            }

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None:
            raise Exception('Bot not found')

        dispatch_result = await runtime_bot.dispatch_test_event(event_type, payload or {})
        route_status = await self.list_event_route_statuses(bot_uuid)
        return {
            'dispatched': bool(dispatch_result.get('dispatched')),
            'event_type': event_type,
            'status': dispatch_result.get('status'),
            'binding_id': dispatch_result.get('binding_id'),
            'failure_code': dispatch_result.get('failure_code'),
            'reason': dispatch_result.get('reason'),
            'suppressed_outputs': dispatch_result.get('suppressed_outputs', []),
            'route_status': route_status,
        }

    async def send_message(self, bot_uuid: str, target_type: str, target_id: str, message_chain_data: dict) -> None:
        """Send message to a specific target via bot

        Args:
            bot_uuid: The UUID of the bot
            target_type: The type of the target, can be "group", "person"
            target_id: The ID of the target
            message_chain_data: The message chain data in dict format
        """
        # Import here to avoid circular imports
        import langbot_plugin.api.entities.builtin.platform.message as platform_message

        # Get runtime bot
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None:
            raise Exception(f'Bot not found: {bot_uuid}')

        # Validate and convert message chain
        try:
            message_chain = platform_message.MessageChain.model_validate(message_chain_data)
        except Exception as e:
            raise Exception(f'Invalid message_chain format: {str(e)}')

        # Send message via adapter
        await runtime_bot.adapter.send_message(target_type, str(target_id), message_chain)

    # ============ Bot Admins ============

    async def get_bot_admins(self, bot_uuid: str) -> list[dict]:
        from ....entity.persistence import bot as persistence_bot

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_bot.BotAdmin).where(persistence_bot.BotAdmin.bot_uuid == bot_uuid)
        )
        return [{'id': r.id, 'launcher_type': r.launcher_type, 'launcher_id': r.launcher_id} for r in result.all()]

    async def add_bot_admin(self, bot_uuid: str, launcher_type: str, launcher_id: str) -> int:
        from ....entity.persistence import bot as persistence_bot

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_bot.BotAdmin).values(
                bot_uuid=bot_uuid,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
            )
        )
        return result.inserted_primary_key[0]

    async def delete_bot_admin(self, bot_uuid: str, admin_id: int) -> None:
        from ....entity.persistence import bot as persistence_bot

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_bot.BotAdmin).where(
                persistence_bot.BotAdmin.bot_uuid == bot_uuid,
                persistence_bot.BotAdmin.id == admin_id,
            )
        )
