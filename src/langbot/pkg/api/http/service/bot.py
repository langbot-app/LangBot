from __future__ import annotations

import uuid
import typing
import json
import asyncio
import datetime
import sqlalchemy

from ....core import app
from ....discover import engine
from ....command import processor as command_processor
from ....entity.persistence import agent as persistence_agent
from ....entity.persistence import bot as persistence_bot
from ....entity.persistence import pipeline as persistence_pipeline
from ....workspace.errors import WorkspaceNotFoundError
from .bot_errors import BotApplyError, bot_error_message
from .tenant import TenantContext, require_workspace_uuid, scope_statement
from ....utils import httpclient
from ....platform.sources import http_bot_signing
from ....platform.adapter_names import canonical_adapter_name
from ....cloud.plan_policy import require_workspace_platform
from ....agent.runner.errors import RunnerNotFoundError
from ....message_policy import schema as message_policy_schema

from ...application.contracts import ApplicationAPIError, ApplicationAPIException
from ....i18n import t, language_scope
from ....i18n.workspace import get_workspace_language
from ....platform.command_registration import (
    PlatformCommandRegistrar,
    build_command_plan,
    command_sets,
    command_set_hash,
)


class BotService:
    """Bot service"""

    ap: app.Application
    FAILURE_ROUTE_NOT_FOUND = 'route_not_found'
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
        'plugin_processors',
        'command_settings',
        'message_policy',
    }

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self._default_pipeline_lock = asyncio.Lock()

    def _get_adapter_component(self, adapter_name: str) -> engine.Component | None:
        """Return the discovered platform adapter component for an adapter name."""
        adapter_name = canonical_adapter_name(adapter_name)
        for component in self.ap.discover.get_components_by_kind('MessagePlatformAdapter'):
            if component.metadata.name == adapter_name:
                return component
        return None

    def _adapter_declares_webhook_url(self, adapter_name: str) -> bool:
        """Whether the manifest needs a generated public bot ingress URL."""
        component = self._get_adapter_component(adapter_name)
        if component is None:
            return False

        for config_item in component.spec.get('config', []):
            if config_item.get('type') == 'webhook-url' or config_item.get('name') == '__system.onebot_ws_url':
                return True
        return False

    @staticmethod
    def _is_message_event_pattern(event_pattern: str) -> bool:
        return event_pattern == 'message.received'

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
        patterns = supported_patterns if isinstance(supported_patterns, list) else ['*']
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
        if target_type in {'agent', 'pipeline', 'event_processor'}:
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
    def _extract_dry_run_bot_account_id(
        context: typing.Any,
        event_data: typing.Any,
    ) -> str | None:
        """Extract bot_account_id from dry-run context for is_at_bot filter support."""
        if isinstance(context, dict):
            val = context.get('bot_account_id')
            if val is not None:
                return str(val)
        if isinstance(event_data, dict):
            val = event_data.get('bot_account_id')
            if val is not None:
                return str(val)
        return None

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

    async def _get_pipeline_entity(
        self, context: TenantContext, pipeline_uuid: str
    ) -> persistence_pipeline.LegacyPipeline | None:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                    persistence_pipeline.LegacyPipeline.uuid == pipeline_uuid
                ),
                persistence_pipeline.LegacyPipeline,
                context,
            )
        )
        return result.first()

    async def _get_agent_entity(self, context: TenantContext, agent_uuid: str) -> persistence_agent.Agent | None:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_agent.Agent).where(persistence_agent.Agent.uuid == agent_uuid),
                persistence_agent.Agent,
                context,
            )
        )
        return result.first()

    async def dry_run_event_route(
        self,
        tenant_context: TenantContext,
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

        bot = await self.get_bot(tenant_context, bot_uuid, include_secret=False)
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
            bot_account_id=self._extract_dry_run_bot_account_id(context, event_data),
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
            pipeline = await self._get_pipeline_entity(tenant_context, target_uuid) if target_uuid else None
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

        if target_type in {'agent', 'event_processor'}:
            agent = await self._get_agent_entity(tenant_context, target_uuid)
            if agent is None or getattr(agent, 'kind', 'agent') != target_type:
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

    async def _build_default_event_bindings(self, context: TenantContext) -> list[dict]:
        """Build the default event bindings for a new bot.

        Two bindings route message.received to the first available pipeline:
        - private chat: always respond
        - group chat: require an @mention of the bot (is_at_bot=true)

        The group @mention check runs at the routing layer, so messages that
        do not match never create a pipeline task. Existing bots keep their
        current bindings; this only applies to bots created without any.
        """
        # Serialize first-bot setup without retaining an unbounded lock per Workspace.
        async with self._default_pipeline_lock:
            pipelines = await self.ap.pipeline_service.get_pipelines(context)
            if pipelines:
                selected = next((item for item in pipelines if item.get('is_default')), pipelines[0])
                pipeline_uuid = selected.get('uuid')
            else:
                pipeline_uuid = await self.ap.pipeline_service.create_pipeline(
                    context, {'name': t('New Pipeline'), 'description': '', 'emoji': '⚙️'}, default=True
                )
        if not pipeline_uuid:
            return []

        return [
            {
                'id': str(uuid.uuid4()),
                'event_pattern': 'message.received',
                'target_type': 'pipeline',
                'target_uuid': pipeline_uuid,
                'filters': [
                    {'field': 'chat_type', 'operator': 'eq', 'value': 'person'},
                ],
                'priority': 0,
                'enabled': True,
                'description': 'Private chat: respond directly',
                'order': 0,
            },
            {
                'id': str(uuid.uuid4()),
                'event_pattern': 'message.received',
                'target_type': 'pipeline',
                'target_uuid': pipeline_uuid,
                'filters': [
                    {'field': 'chat_type', 'operator': 'eq', 'value': 'group'},
                    {'field': 'is_at_bot', 'operator': 'eq', 'value': True},
                ],
                'priority': 0,
                'enabled': True,
                'description': 'Group chat: respond only when the bot is @mentioned',
                'order': 1,
            },
        ]

    async def _normalize_event_bindings(
        self,
        context: TenantContext,
        bindings: list[dict] | None,
        *,
        current_bindings: typing.Any = None,
    ) -> list[dict]:
        """Validate and normalize Bot event bindings.

        A binding may carry a ``policy``: a partial message policy overriding
        the bot's for messages this route matches. A write that names an
        existing binding by id but omits ``policy`` keeps the stored override,
        so clients unaware of policies cannot drop one by saving routes; an
        explicit ``null`` removes it.
        """
        if not bindings:
            return []

        current_policies: dict[str, typing.Any] = {}
        if isinstance(current_bindings, str):
            try:
                current_bindings = json.loads(current_bindings)
            except json.JSONDecodeError:
                current_bindings = None
        for binding in current_bindings if isinstance(current_bindings, list) else []:
            if isinstance(binding, dict) and binding.get('id') and isinstance(binding.get('policy'), dict):
                current_policies[str(binding['id'])] = binding['policy']

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
                    raise ValueError('Pipeline can only be bound to message.received')
                result = await self.ap.persistence_mgr.execute_async(
                    scope_statement(
                        sqlalchemy.select(persistence_pipeline.LegacyPipeline.uuid).where(
                            persistence_pipeline.LegacyPipeline.uuid == target_uuid
                        ),
                        persistence_pipeline.LegacyPipeline,
                        context,
                    )
                )
                if result.first() is None:
                    raise ValueError('Pipeline not found')
            elif target_type == 'agent':
                result = await self.ap.persistence_mgr.execute_async(
                    scope_statement(
                        sqlalchemy.select(persistence_agent.Agent).where(persistence_agent.Agent.uuid == target_uuid),
                        persistence_agent.Agent,
                        context,
                    )
                )
                agent = result.first()
                if agent is None or agent.kind != target_type:
                    raise ValueError('Processor not found')
                if not self._agent_supports_event_pattern(agent.supported_event_patterns, event_pattern):
                    raise ValueError('Agent does not support this event pattern')
            elif target_type == 'discard':
                target_uuid = ''
            else:
                raise ValueError(f'Unsupported event binding target type: {target_type}')

            binding_id = raw_binding.get('id') or str(uuid.uuid4())
            item = {
                'id': binding_id,
                'event_pattern': event_pattern,
                'target_type': target_type,
                'target_uuid': target_uuid,
                'filters': raw_binding.get('filters') or [],
                'priority': int(raw_binding.get('priority') or 0),
                'enabled': bool(raw_binding.get('enabled', True)),
                'description': raw_binding.get('description') or '',
                'order': index,
            }
            if target_type != 'discard':
                if 'policy' in raw_binding:
                    policy = message_policy_schema.validate_policy(
                        raw_binding['policy'], field=f'event_bindings[{index}].policy'
                    )
                else:
                    policy = current_policies.get(str(binding_id))
                if policy:
                    item['policy'] = policy
            normalized.append(item)

        return normalized

    async def _normalize_plugin_processors(self, context: TenantContext, subscriptions: typing.Any) -> list[dict]:
        """Validate explicit subscriptions within this Workspace; events come from the Runner."""
        if not isinstance(subscriptions, list):
            raise ValueError('plugin_processors must be an array')
        normalized = []
        seen = set()
        for subscription in subscriptions:
            if not isinstance(subscription, dict):
                raise ValueError('Each plugin processor binding must be an object')
            processor_uuid = subscription.get('processor_uuid')
            if not isinstance(processor_uuid, str) or not processor_uuid.strip():
                raise ValueError('Plugin processor UUID is required')
            if processor_uuid in seen:
                raise ValueError('A plugin processor can only be bound once per bot')
            enabled = subscription.get('enabled', True)
            if not isinstance(enabled, bool):
                raise ValueError('Plugin processor enabled must be a boolean')
            agent = await self._get_agent_entity(context, processor_uuid)
            if agent is None or agent.kind != 'event_processor':
                raise ValueError('Plugin processor not found')
            if enabled:
                try:
                    descriptor = await self.ap.runner_registry.get(context, agent.component_ref)
                except RunnerNotFoundError as exc:
                    raise ValueError('Runner component is unavailable') from exc
                if 'event' not in descriptor.usages or not descriptor.supported_event_patterns:
                    raise ValueError('Select an available Runner that declares event usage')
            seen.add(processor_uuid)
            normalized.append({'processor_uuid': processor_uuid, 'enabled': enabled})
        return normalized

    async def _normalize_command_settings(self, context: TenantContext, settings: typing.Any) -> dict:
        """Validate command settings for a bot."""
        if not isinstance(settings, dict):
            raise ValueError('command_settings must be an object')
        enabled = settings.get('enabled', True)
        if not isinstance(enabled, bool):
            raise ValueError('command_settings.enabled must be a boolean')

        prefixes = settings.get('prefixes', ['/'])
        if not isinstance(prefixes, list) or len(prefixes) == 0:
            raise ValueError('command_settings.prefixes must be a non-empty list')
        normalized_prefixes = []
        for p in prefixes:
            if not isinstance(p, str) or not p.strip() or any(c.isspace() for c in p):
                raise ValueError('Each prefix must be a non-empty string without whitespace')
            if p not in normalized_prefixes:
                normalized_prefixes.append(p)

        processors = settings.get('processors', [])
        if not isinstance(processors, list):
            raise ValueError('command_settings.processors must be a list')

        normalized_processors = []
        seen_processors: set[str] = set()
        seen_plugins: set[str] = set()
        for item in processors:
            if not isinstance(item, dict):
                raise ValueError('Each command processor binding must be an object')
            processor_uuid = item.get('processor_uuid')
            if not isinstance(processor_uuid, str) or not processor_uuid.strip():
                raise ValueError('Command processor UUID is required')
            processor_uuid = processor_uuid.strip()
            if processor_uuid in seen_processors:
                raise ValueError('A command processor can only be bound once per bot')
            processor_enabled = item.get('enabled', True)
            if not isinstance(processor_enabled, bool):
                raise ValueError('Command processor enabled must be a boolean')
            agent = await self._get_agent_entity(context, processor_uuid)
            if agent is None or agent.kind != command_processor.COMMAND_PROCESSOR_KIND:
                raise ValueError('Command processor not found')
            plugin_id = command_processor.plugin_id_from_component_ref(agent.component_ref)
            if plugin_id is None:
                raise ValueError('Command processor has no plugin')
            if plugin_id in seen_plugins:
                # Two instances of one plugin expose the same commands; the later one could never match.
                raise ValueError('Only one command processor per plugin can be bound to a bot')
            seen_processors.add(processor_uuid)
            seen_plugins.add(plugin_id)
            normalized_processors.append({'processor_uuid': processor_uuid, 'enabled': processor_enabled})

        normalized = {'enabled': enabled, 'prefixes': normalized_prefixes, 'processors': normalized_processors}
        if 'platform_commands' in settings:
            registration = settings['platform_commands']
            if not isinstance(registration, dict) or not isinstance(registration.get('enabled'), bool):
                raise ValueError(t('platform_commands.enabled must be a boolean'))
            selected = registration.get('selected', [])
            if not isinstance(selected, list) or any(not isinstance(name, str) or not name for name in selected):
                raise ValueError(t('platform_commands.selected must be a list of command names'))
            normalized['platform_commands'] = {
                'enabled': registration['enabled'],
                'selected': list(dict.fromkeys(selected)),
            }
        return normalized

    def get_message_policy_metadata(self) -> dict[str, typing.Any]:
        """Describe the message policy for editors: form metadata and reference values.

        ``default`` is what a new bot starts with; ``neutral`` is what an
        omitted setting means (admit everything, change nothing).
        """
        return {
            'configs': list(getattr(self.ap, 'message_policy_meta', None) or []),
            'default': message_policy_schema.default_policy(),
            'neutral': message_policy_schema.neutral_policy(),
        }

    async def _prepare_bot_data(
        self,
        context: TenantContext,
        bot_data: dict,
        *,
        include_uuid: bool,
        current_bindings: typing.Any = None,
    ) -> dict:
        """Normalize Bot write payloads to the current event-routing model."""
        update_data = bot_data.copy()
        if not include_uuid:
            update_data.pop('uuid', None)

        update_data = {key: value for key, value in update_data.items() if key in self.BOT_FIELDS}
        if 'adapter' in update_data:
            update_data['adapter'] = canonical_adapter_name(update_data['adapter'])
        if 'event_bindings' in update_data:
            update_data['event_bindings'] = await self._normalize_event_bindings(
                context, update_data.get('event_bindings'), current_bindings=current_bindings
            )
        if 'message_policy' in update_data:
            # Stored complete, so readers never have to guess an omitted value.
            update_data['message_policy'] = message_policy_schema.resolve_policy(
                message_policy_schema.validate_policy(update_data['message_policy'])
            )
        if 'plugin_processors' in update_data:
            update_data['plugin_processors'] = await self._normalize_plugin_processors(
                context, update_data['plugin_processors']
            )
        if 'command_settings' in update_data:
            update_data['command_settings'] = await self._normalize_command_settings(
                context, update_data['command_settings']
            )
        return update_data

    async def get_bots(self, context: TenantContext, include_secret: bool = False) -> list[dict]:
        """获取所有机器人"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(persistence_bot.Bot), persistence_bot.Bot, context)
        )

        bots = result.all()

        masked_columns = []
        if not include_secret:
            masked_columns = ['adapter_config']

        serialized = [self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot, masked_columns) for bot in bots]
        for bot in serialized:
            bot['adapter'] = canonical_adapter_name(bot['adapter'])
        return serialized

    async def require_processor_unbound(self, context: TenantContext, processor_uuid: str) -> None:
        """Refuse to remove a Pipeline or Agent that a Bot still routes events to.

        Deleting a bound target used to leave the binding dangling, so every
        matching inbound event was routed to a missing target and dropped.
        """
        from ....platform.botmgr import RuntimeBot

        processor_uuid = str(processor_uuid or '').strip()
        if not processor_uuid:
            return
        bot_names: list[str] = []
        for bot in await self.get_bots(context):
            bindings = RuntimeBot._get_event_bindings_from_value(bot.get('event_bindings') or [])
            subscriptions = bot.get('plugin_processors') or []
            if any(str(binding.get('target_uuid') or '').strip() == processor_uuid for binding in bindings) or any(
                isinstance(subscription, dict) and subscription.get('processor_uuid') == processor_uuid
                for subscription in (subscriptions if isinstance(subscriptions, list) else [])
            ):
                bot_names.append(str(bot.get('name') or bot.get('uuid')))
        if bot_names:
            raise ApplicationAPIException(
                ApplicationAPIError(
                    'resource_in_use',
                    t(
                        'This item is still used by the event bindings of these bots: {bots}. '
                        'Change those bindings first, then delete it.',
                        bots=', '.join(sorted(bot_names)),
                    ),
                    409,
                    {'bots': sorted(bot_names)},
                )
            )

    async def get_bot(self, context: TenantContext, bot_uuid: str, include_secret: bool = False) -> dict | None:
        """获取机器人"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid),
                persistence_bot.Bot,
                context,
            )
        )

        bot = result.first()

        if bot is None:
            return None

        masked_columns = []
        if not include_secret:
            masked_columns = ['adapter_config']

        serialized = self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot, masked_columns)
        serialized['adapter'] = canonical_adapter_name(serialized['adapter'])
        adapter_class = getattr(getattr(self.ap, 'platform_mgr', None), 'adapter_dict', {}).get(serialized['adapter'])
        if adapter_class is not None and hasattr(adapter_class, 'command_registration_capability'):
            try:
                serialized['platform_command_registration'] = await self._platform_command_plan(
                    context, serialized, adapter_class
                )
            except Exception as exc:
                serialized['platform_command_registration'] = {'error': type(exc).__name__}
        return serialized

    async def _platform_command_plan(self, context, bot: dict, adapter) -> dict:
        settings = bot.get('command_settings') or {}
        plugin_ids = []
        for binding in settings.get('processors', []):
            if not binding.get('enabled', True):
                continue
            agent = await self._get_agent_entity(context, binding['processor_uuid'])
            if agent is not None and agent.kind == command_processor.COMMAND_PROCESSOR_KIND:
                plugin_id = command_processor.plugin_id_from_component_ref(agent.component_ref)
                if plugin_id and plugin_id not in plugin_ids:
                    plugin_ids.append(plugin_id)
        manifests = await self.ap.plugin_connector.list_commands(plugin_ids) if plugin_ids else []
        language = await get_workspace_language(self.ap, require_workspace_uuid(context))
        return build_command_plan(settings, manifests, plugin_ids, adapter.command_registration_capability(), language)

    async def sync_platform_commands(self, context: TenantContext, bot_uuid: str) -> dict:
        await self.ap.plugin_connector.require_workspace_context(context)
        runtime = await self.ap.platform_mgr.get_bot_by_uuid(context, bot_uuid)
        if runtime is None or not isinstance(runtime.adapter, PlatformCommandRegistrar):
            raise ValueError(t('Platform command registration requires a running supported bot'))
        async with runtime._platform_command_sync_lock:
            await runtime.assert_execution_active()
            bot = await self.get_bot(context, bot_uuid)
            if bot is None:
                raise WorkspaceNotFoundError('Bot not found')
            previous = bot.get('platform_command_sync') or {}
            enabled = (bot.get('command_settings') or {}).get('platform_commands', {}).get('enabled', False)
            if not enabled and not previous:
                return {'status': 'disabled'}
            state = dict(previous)
            try:
                plan = bot['platform_command_registration']
                if plan.get('error'):
                    raise RuntimeError(plan['error'])
                language = await get_workspace_language(self.ap, require_workspace_uuid(context))
                specs = command_sets(plan, bot['adapter'], language)
                digest = command_set_hash({'language': language, 'adapter': bot['adapter'], 'commands': specs})
                if digest == previous.get('hash') and not previous.get('error'):
                    return {**previous, 'skipped': True}
                for locale in previous.get('locales', []):
                    specs.setdefault(locale, [])
                state['locales'] = list(specs)
                with language_scope(language):
                    result = await runtime.adapter.sync_platform_commands(specs)
                if not result.get('success', False):
                    raise RuntimeError(result.get('error') or 'Platform command synchronization failed')
                state = {
                    'hash': digest,
                    'synced_at': datetime.datetime.now(datetime.timezone.utc).isoformat(),
                    'error': None,
                    'locales': list(specs),
                    'rejected': plan['rejected'],
                }
            except Exception as exc:
                state['error'] = bot_error_message(exc, {'adapter_config': getattr(runtime.adapter, 'config', {})})
                state['attempted_at'] = datetime.datetime.now(datetime.timezone.utc).isoformat()
            await runtime.assert_execution_active()
            await self.ap.persistence_mgr.execute_async(
                scope_statement(
                    sqlalchemy.update(persistence_bot.Bot)
                    .where(persistence_bot.Bot.uuid == bot_uuid)
                    .values(platform_command_sync=state),
                    persistence_bot.Bot,
                    context,
                )
            )
            runtime.bot_entity.platform_command_sync = state
            return state

    async def get_runtime_bot_info(
        self,
        context: TenantContext,
        bot_uuid: str,
        include_secret: bool = False,
    ) -> dict:
        """获取机器人运行时信息"""
        persistence_bot = await self.get_bot(context, bot_uuid, include_secret)
        if persistence_bot is None:
            raise WorkspaceNotFoundError('Bot not found')

        adapter_runtime_values = {}

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(context, bot_uuid)
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

    async def create_bot(self, context: TenantContext, bot_data: dict) -> str:
        """Create bot"""
        workspace_uuid = require_workspace_uuid(context)
        if not isinstance(bot_data, dict):
            raise ValueError('bot_data must be an object')
        for field in ('name', 'adapter'):
            if not isinstance(bot_data.get(field), str) or not bot_data[field].strip():
                raise ValueError(f'bot_data.{field} is required and must be a non-empty string')
        if not isinstance(bot_data.get('adapter_config'), dict):
            raise ValueError('bot_data.adapter_config is required and must be an object')
        # Check limitation
        from .workspace_limits import workspace_limits

        limitation = await workspace_limits(self.ap, workspace_uuid)
        max_bots = limitation.get('max_bots', -1)
        if max_bots >= 0:
            existing_bots = await self.get_bots(context)
            if len(existing_bots) >= max_bots:
                raise ValueError(f'Maximum number of bots ({max_bots}) reached')

        bot_data = await self._prepare_bot_data(context, bot_data, include_uuid=True)
        await require_workspace_platform(self.ap, workspace_uuid, bot_data['adapter'])
        bot_data['uuid'] = str(uuid.uuid4())
        bot_data['workspace_uuid'] = workspace_uuid
        if not bot_data.get('event_bindings'):
            bot_data['event_bindings'] = await self._build_default_event_bindings(context)
        else:
            bot_data['event_bindings'] = await self._normalize_event_bindings(context, bot_data['event_bindings'])
        bot_data.setdefault('plugin_processors', [])
        bot_data.setdefault('command_settings', {'enabled': True, 'prefixes': ['/'], 'processors': []})
        bot_data.setdefault('message_policy', message_policy_schema.default_policy())
        # The column is NOT NULL; a caller that omits the optional description
        # must not get a 500 from the database constraint.
        bot_data.setdefault('description', '')

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_bot.Bot).values(bot_data))

        bot = await self.get_bot(context, bot_data['uuid'], include_secret=True)

        try:
            if bot.get('enable'):
                await self.ap.platform_mgr.load_bot(context, bot)
        except Exception as exc:
            raise BotApplyError(bot_error_message(exc, bot), bot['uuid']) from exc

        return bot_data['uuid']

    async def update_bot(self, context: TenantContext, bot_uuid: str, bot_data: dict) -> None:
        """Update bot"""
        workspace_uuid = require_workspace_uuid(context)
        current_bindings = None
        if isinstance(bot_data, dict) and bot_data.get('event_bindings'):
            stored = await self.get_bot(context, bot_uuid, include_secret=False)
            current_bindings = (stored or {}).get('event_bindings')
        update_data = await self._prepare_bot_data(
            context, bot_data, include_uuid=False, current_bindings=current_bindings
        )
        update_data.pop('workspace_uuid', None)
        if 'adapter' in update_data or 'adapter_config' in update_data:
            current = await self.get_bot(context, bot_uuid, include_secret=True)
            if current is not None and any(
                key in update_data and update_data[key] != current.get(key) for key in ('adapter', 'adapter_config')
            ):
                update_data['platform_command_sync'] = {}
        if 'adapter' in update_data or update_data.get('enable'):
            current = await self.get_bot(context, bot_uuid, include_secret=True)
            await require_workspace_platform(self.ap, workspace_uuid, update_data.get('adapter', current['adapter']))

        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_bot.Bot).values(update_data).where(persistence_bot.Bot.uuid == bot_uuid),
                persistence_bot.Bot,
                workspace_uuid,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Bot not found')

        runtime_fields = {
            'adapter',
            'adapter_config',
            'enable',
            'event_bindings',
            'plugin_processors',
            'command_settings',
        }
        if not runtime_fields.intersection(update_data):
            runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(context, bot_uuid)
            if runtime_bot is not None:
                if 'name' in update_data:
                    runtime_bot.bot_entity.name = update_data['name']
                if 'description' in update_data:
                    runtime_bot.bot_entity.description = update_data['description']
                if 'message_policy' in update_data:
                    # A policy change needs no adapter restart: swap it in place
                    # and drop the runtimes compiled from the old one.
                    runtime_bot.bot_entity.message_policy = update_data['message_policy']
            if 'message_policy' in update_data:
                policy_mgr = getattr(self.ap, 'message_policy_mgr', None)
                if policy_mgr is not None:
                    policy_mgr.invalidate_bot(workspace_uuid, bot_uuid)
            return

        # Persisted configuration is distinct from applying it to the running adapter.
        bot = await self.get_bot(context, bot_uuid, include_secret=True)
        if update_data.get('command_settings', {}).get('platform_commands', {}).get('enabled') is False:
            runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(context, bot_uuid)
            if runtime_bot is not None and isinstance(runtime_bot.adapter, PlatformCommandRegistrar):
                await self.sync_platform_commands(context, bot_uuid)
        try:
            await self.ap.platform_mgr.remove_bot(context, bot_uuid)
            if bot.get('enable'):
                runtime_bot = await self.ap.platform_mgr.load_bot(context, bot)
                await runtime_bot.run()
        except Exception as exc:
            raise BotApplyError(bot_error_message(exc, bot), bot['uuid']) from exc

        # Reset conversations using this bot after its configuration is applied.
        for session in self.ap.sess_mgr.session_list:
            if (
                session.using_conversation is not None
                and session.using_conversation.bot_uuid == bot_uuid
                and getattr(session, 'workspace_uuid', workspace_uuid) == workspace_uuid
            ):
                session.using_conversation = None

    async def delete_bot(self, context: TenantContext, bot_uuid: str) -> None:
        """Delete bot"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid),
                persistence_bot.Bot,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Bot not found')
        await self.ap.platform_mgr.remove_bot(context, bot_uuid)

    async def list_event_logs(
        self, context: TenantContext, bot_uuid: str, from_index: int, max_count: int
    ) -> tuple[list[dict], int]:
        if await self.get_bot(context, bot_uuid, include_secret=False) is None:
            raise WorkspaceNotFoundError('Bot not found')
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(context, bot_uuid)
        if runtime_bot is None:
            # Saved but disabled/unconfigured bots have no runtime logs yet.
            return [], 0

        logs, total_count = await runtime_bot.logger.get_logs(from_index, max_count)

        return [log.to_json() for log in logs], total_count

    async def list_event_route_statuses(self, context: TenantContext, bot_uuid: str) -> dict[str, typing.Any]:
        """Return recent runtime status for Bot event routes from in-memory Bot logs."""
        from ....platform.botmgr import RuntimeBot

        bot = await self.get_bot(context, bot_uuid, include_secret=False)
        if bot is None:
            raise WorkspaceNotFoundError('Bot not found')
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(context, bot_uuid)

        latest_by_binding: dict[str, dict[str, typing.Any]] = {}
        unmatched_events: list[dict[str, typing.Any]] = []
        runtime_logs = getattr(getattr(runtime_bot, 'logger', None), 'logs', [])
        for log in runtime_logs:
            status = self._event_route_status_from_log(log)
            if status is None:
                continue
            binding_id = status.get('binding_id')
            if binding_id:
                latest_by_binding[str(binding_id)] = status
            else:
                unmatched_events.append(status)

        runtime_entity = getattr(runtime_bot, 'bot_entity', None)
        raw_bindings = getattr(runtime_entity, 'event_bindings', None) if runtime_entity is not None else None
        if raw_bindings is None:
            raw_bindings = bot.get('event_bindings') or []
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

    async def preview_group_filter_migration(self, context: TenantContext, bot_uuid: str) -> dict[str, typing.Any]:
        """Preview the effect of promoting the at-bot rule to a routing-layer filter.

        Detects routes whose message policy still requires at-bot and whose
        filters do not already select group messages by is_at_bot. Returns the
        proposed binding changes plus a per-processor summary. Does not persist.
        """
        from ....platform.botmgr import RuntimeBot

        bot = await self.get_bot(context, bot_uuid, include_secret=False)
        if bot is None:
            raise WorkspaceNotFoundError('Bot not found')

        bindings = RuntimeBot._get_event_bindings_from_value(bot.get('event_bindings') or [])

        # The at-bot rule is part of the message policy in effect for each route.
        bot_policy = bot.get('message_policy')

        def _group_rules(binding: dict) -> dict[str, typing.Any]:
            policy = message_policy_schema.resolve_policy(bot_policy, binding.get('policy'))
            rules = policy['trigger']['group-respond-rules']
            return rules if rules.get('enabled', True) else {}

        pipeline_flags: dict[str, dict[str, typing.Any]] = {}
        for binding in bindings:
            pipeline_uuid = str(binding.get('target_uuid') or '')
            if binding.get('target_type') != 'pipeline' or not pipeline_uuid:
                continue
            group_rules = _group_rules(binding)
            flags = pipeline_flags.setdefault(
                pipeline_uuid,
                {
                    'at_bot_enabled': False,
                    'prefix': group_rules.get('prefix', []),
                    'regexp': group_rules.get('regexp', []),
                    'random': group_rules.get('random', 0.0),
                },
            )
            flags['at_bot_enabled'] = flags['at_bot_enabled'] or bool(group_rules.get('at'))

        # A binding "already has the at-bot filter" if it filters chat_type=group
        # AND requires is_at_bot=true (or non-false).
        def _has_group_at_filter(binding: dict) -> bool:
            filters = binding.get('filters') or []
            if not isinstance(filters, list):
                return False
            has_group = any(
                isinstance(f, dict)
                and f.get('field') == 'chat_type'
                and f.get('operator', 'eq') == 'eq'
                and f.get('value') == 'group'
                for f in filters
            )
            has_at = any(
                isinstance(f, dict)
                and f.get('field') == 'is_at_bot'
                and f.get('operator', 'eq') == 'eq'
                and f.get('value') is True
                for f in filters
            )
            return has_group and has_at

        needs_migration = [pipeline_uuid for pipeline_uuid, flags in pipeline_flags.items() if flags['at_bot_enabled']]
        bindings_with_at_filter = [b for b in bindings if _has_group_at_filter(b)]
        bindings_missing_at_filter = [
            b
            for b in bindings
            if b.get('target_type') == 'pipeline'
            and str(b.get('target_uuid') or '') in needs_migration
            and bool(_group_rules(b).get('at'))
            and not _has_group_at_filter(b)
        ]

        proposed_bindings: list[dict[str, typing.Any]] = []
        for binding in bindings_missing_at_filter:
            new_binding = json.loads(json.dumps(binding))
            filters = list(new_binding.get('filters') or [])
            if not any(
                isinstance(f, dict) and f.get('field') == 'chat_type' and f.get('value') == 'group' for f in filters
            ):
                filters.append({'field': 'chat_type', 'operator': 'eq', 'value': 'group'})
            if not any(isinstance(f, dict) and f.get('field') == 'is_at_bot' for f in filters):
                filters.append({'field': 'is_at_bot', 'operator': 'eq', 'value': True})
            new_binding['filters'] = filters
            proposed_bindings.append(new_binding)

        return {
            'bot_uuid': bot_uuid,
            'needs_migration': bool(bindings_missing_at_filter),
            'pipelines_with_at_bot': sorted(needs_migration),
            'pipeline_flags': pipeline_flags,
            'bindings_already_filtered': [b.get('id') for b in bindings_with_at_filter],
            'bindings_to_update': [
                {
                    'binding_id': b.get('id'),
                    'event_pattern': b.get('event_pattern'),
                    'target_type': b.get('target_type'),
                    'target_uuid': b.get('target_uuid'),
                    'current_filters': b.get('filters') or [],
                    'proposed_filters': next(
                        (p.get('filters') for p in proposed_bindings if p.get('id') == b.get('id')),
                        b.get('filters') or [],
                    ),
                }
                for b in bindings_missing_at_filter
            ],
        }

    async def apply_group_filter_migration(
        self,
        context: TenantContext,
        bot_uuid: str,
        *,
        disable_pipeline_at_bot: bool = True,
    ) -> dict[str, typing.Any]:
        """Apply the group filter migration previewed by preview_group_filter_migration.

        Updates the bot's event_bindings to add is_at_bot=true filter on group
        routes whose message policy still has at-bot enabled. Optionally turns
        the at-bot rule off in those routes' policy so it is not checked twice.
        Existing prefix/regexp/random rules remain untouched. Idempotent.
        """
        from ....platform.botmgr import RuntimeBot

        preview = await self.preview_group_filter_migration(context, bot_uuid)
        if not preview['needs_migration']:
            return {'bot_uuid': bot_uuid, 'applied': False, 'reason': 'no_migration_needed'}

        bot = await self.get_bot(context, bot_uuid, include_secret=False)
        if bot is None:
            raise WorkspaceNotFoundError('Bot not found')

        bindings = RuntimeBot._get_event_bindings_from_value(bot.get('event_bindings') or [])
        bindings_by_id = {b.get('id'): b for b in bindings if b.get('id')}
        updated_pipelines: set[str] = set()
        for item in preview['bindings_to_update']:
            binding_id = item['binding_id']
            existing = bindings_by_id.get(binding_id)
            if existing is None:
                continue
            existing['filters'] = item['proposed_filters']
            if disable_pipeline_at_bot:
                # The route filter now does the check; turn the policy rule off
                # for this route so it is not applied twice.
                existing['policy'] = message_policy_schema.merge_policy(
                    existing.get('policy'),
                    {'trigger': {'group-respond-rules': {'at': False}}},
                )
                updated_pipelines.add(str(existing.get('target_uuid') or ''))

        update_payload = {
            'event_bindings': await self._normalize_event_bindings(context, bindings),
        }
        await self.update_bot(context, bot_uuid, update_payload)

        return {
            'bot_uuid': bot_uuid,
            'applied': True,
            'updated_bindings': [item['binding_id'] for item in preview['bindings_to_update']],
            'disabled_pipeline_at_bot': sorted(updated_pipelines),
        }

    async def send_http_bot_test_message(
        self,
        context: TenantContext,
        bot_uuid: str,
        message: str,
    ) -> dict:
        """Send a signed test message through the HTTP Bot public ingress."""
        bot = await self.get_bot(context, bot_uuid, include_secret=True)
        if bot is None:
            raise WorkspaceNotFoundError('Bot not found')
        if bot.get('adapter') != 'http_bot':
            raise ValueError('Inbound test is only available for HTTP Bot')
        if not bot.get('enable'):
            raise ValueError('Bot must be enabled before sending a test message')

        text = message.strip()
        if not text or len(text) > 2000:
            raise ValueError('Test message must contain 1 to 2000 characters')

        payload = {
            'session_id': f'wizard-{uuid.uuid4().hex}',
            'sender': {'id': 'wizard-user', 'name': 'Wizard Test'},
            'message': [{'type': 'Plain', 'text': text}],
        }
        body = json.dumps(payload, ensure_ascii=False, separators=(',', ':')).encode()
        config = bot.get('adapter_config') or {}
        headers = {'Content-Type': 'application/json'}
        if config.get('signature_required', True):
            secret = str(config.get('inbound_secret') or '')
            if not secret:
                raise ValueError('HTTP Bot inbound signing secret is required')
            timestamp, signature = http_bot_signing.sign(secret, body)
            headers[http_bot_signing.HEADER_TIMESTAMP] = timestamp
            headers[http_bot_signing.HEADER_SIGNATURE] = signature

        port = int(self.ap.instance_config.data.get('api', {}).get('port', 5300))
        session = httpclient.get_session()
        async with session.post(
            f'http://127.0.0.1:{port}/bots/{bot_uuid}',
            data=body,
            headers=headers,
        ) as response:
            result = await httpclient.read_json_limited(response)
            if response.status not in {200, 202}:
                raise ValueError(result.get('msg') or f'HTTP Bot test failed with status {response.status}')
            return result.get('data') or {}

    async def send_message(
        self,
        context: TenantContext,
        bot_uuid: str,
        target_type: str,
        target_id: str,
        message_chain_data: dict,
    ) -> None:
        """Send message to a specific target via bot

        Args:
            bot_uuid: The UUID of the bot
            target_type: The type of the target, can be "group", "person"
            target_id: The ID of the target
            message_chain_data: The message chain data in dict format
        """
        if await self.get_bot(context, bot_uuid, include_secret=False) is None:
            raise WorkspaceNotFoundError('Bot not found')

        # Import here to avoid circular imports
        import langbot_plugin.api.entities.builtin.platform.message as platform_message

        # Get runtime bot
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(context, bot_uuid)
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

    async def get_bot_admins(self, context: TenantContext, bot_uuid: str) -> list[dict]:
        from ....entity.persistence import bot as persistence_bot

        if await self.get_bot(context, bot_uuid, include_secret=False) is None:
            raise WorkspaceNotFoundError('Bot not found')
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_bot.BotAdmin).where(persistence_bot.BotAdmin.bot_uuid == bot_uuid),
                persistence_bot.BotAdmin,
                context,
            )
        )
        return [{'id': r.id, 'launcher_type': r.launcher_type, 'launcher_id': r.launcher_id} for r in result.all()]

    async def add_bot_admin(self, context: TenantContext, bot_uuid: str, launcher_type: str, launcher_id: str) -> int:
        from ....entity.persistence import bot as persistence_bot

        workspace_uuid = require_workspace_uuid(context)
        if await self.get_bot(context, bot_uuid, include_secret=False) is None:
            raise WorkspaceNotFoundError('Bot not found')
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_bot.BotAdmin).values(
                workspace_uuid=workspace_uuid,
                bot_uuid=bot_uuid,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
            )
        )
        return result.inserted_primary_key[0]

    async def delete_bot_admin(self, context: TenantContext, bot_uuid: str, admin_id: int) -> None:
        from ....entity.persistence import bot as persistence_bot

        if await self.get_bot(context, bot_uuid, include_secret=False) is None:
            raise WorkspaceNotFoundError('Bot not found')
        await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(persistence_bot.BotAdmin).where(
                    persistence_bot.BotAdmin.bot_uuid == bot_uuid,
                    persistence_bot.BotAdmin.id == admin_id,
                ),
                persistence_bot.BotAdmin,
                context,
            )
        )
