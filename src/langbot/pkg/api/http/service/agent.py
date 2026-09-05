from __future__ import annotations

import datetime
import copy
import fnmatch
import time
import uuid
import typing

import sqlalchemy
from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.agent_runner.event import (
    ActorContext,
    RawEventRef,
    SubjectContext,
)
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput

from ....core import app
from ....agent.runner.config_resolver import RunnerConfigResolver
from ....agent.runner.host_models import (
    AgentBinding,
    AgentEventEnvelope,
    BindingScope,
    DeliveryPolicy,
    StatePolicy,
)
from ....agent.runner.resource_policy import ResourcePolicyProjector
from ....agent.runner.platform_tools import (
    PLATFORM_TOOL_DEFINITIONS,
    platform_tool_catalog,
    resolve_agent_platform_tool_names,
    validate_debug_mock_options,
)
from ....entity.persistence import agent as persistence_agent
from ....workspace.errors import WorkspaceNotFoundError
from ..context import ExecutionContext, RequestContext
from .tenant import TenantContext, require_workspace_uuid, scope_statement


AGENT_KIND_AGENT = 'agent'
AGENT_KIND_PIPELINE = 'pipeline'
PIPELINE_EVENT_PATTERNS = ['message.*']
AGENT_DEFAULT_EVENT_PATTERNS = ['*']


class AgentService:
    """Unified processor facade for the peer Agent and Pipeline types."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_agent_metadata(self, context: TenantContext) -> dict[str, typing.Any]:
        """Return metadata needed by Agent forms."""
        pipeline_metadata = await self.ap.pipeline_service.get_pipeline_metadata(context)
        ai_metadata = next((item for item in pipeline_metadata if item.get('name') == 'ai'), None)
        host_tools: list[dict[str, typing.Any]] | None = None
        get_tool_catalog = getattr(getattr(self.ap, 'tool_mgr', None), 'get_resolved_tool_catalog', None)
        if get_tool_catalog is not None:
            try:
                host_tools = await get_tool_catalog(
                    context,
                    include_skill_authoring=True,
                    include_mcp_resource_tools=True,
                )
            except Exception as exc:
                self.ap.logger.warning(f'Failed to load Agent Host tool catalog: {exc}')
        return {
            'runner_config': ai_metadata,
            'platform_tools': platform_tool_catalog(),
            'host_tools': host_tools,
            'kinds': [
                {
                    'name': AGENT_KIND_AGENT,
                    'supported_event_patterns': AGENT_DEFAULT_EVENT_PATTERNS,
                    'message_only': False,
                },
                {
                    'name': AGENT_KIND_PIPELINE,
                    'supported_event_patterns': PIPELINE_EVENT_PATTERNS,
                    'message_only': True,
                },
            ],
        }

    async def get_agents(
        self,
        context: TenantContext,
        sort_by: str = 'updated_at',
        sort_order: str = 'DESC',
    ) -> list[dict]:
        agents = await self._get_agent_rows(context)
        pipelines = await self.ap.pipeline_service.get_pipelines(
            context,
            sort_by='updated_at',
            sort_order='DESC',
        )

        items = [self._agent_to_product_item(agent) for agent in agents]
        items.extend(self._pipeline_to_product_item(pipeline) for pipeline in pipelines)

        reverse = sort_order == 'DESC'
        sort_key = sort_by if sort_by in {'created_at', 'updated_at'} else 'updated_at'
        return sorted(items, key=lambda item: self._parse_sort_time(item.get(sort_key)), reverse=reverse)

    async def get_agent(self, context: TenantContext, agent_uuid: str) -> dict | None:
        agent = await self._get_agent_row(context, agent_uuid)
        if agent is not None:
            return self._agent_to_product_item(agent, include_config=True)

        pipeline = await self.ap.pipeline_service.get_pipeline(context, agent_uuid)
        if pipeline is not None:
            return self._pipeline_to_product_item(pipeline, include_config=True)

        return None

    async def debug_agent(
        self,
        context: RequestContext,
        agent_uuid: str,
        payload: dict[str, typing.Any],
        *,
        on_result: typing.Callable[[dict[str, typing.Any]], typing.Awaitable[None]] | None = None,
    ) -> dict[str, typing.Any]:
        """Execute one synthetic event against a configured Agent.

        The debug surface uses a trusted Workspace execution context, never
        delivers outputs to a real platform, and supports both message and
        non-message event envelopes.
        """
        agent = await self.get_agent(context, agent_uuid)
        if agent is None or agent.get('kind') != AGENT_KIND_AGENT:
            raise ValueError('Agent not found')

        event_type = str(payload.get('event_type', 'message.received')).strip()
        if not event_type or len(event_type) > 128:
            raise ValueError('Invalid event_type')
        if not self._supports_event_type(
            agent.get('supported_event_patterns'),
            event_type,
        ):
            raise ValueError('Agent does not support this event type')

        text = str(payload.get('text') or '').strip()
        if len(text) > 20_000:
            raise ValueError('Debug input is too long')
        event_data = payload.get('data', {})
        if not isinstance(event_data, dict):
            raise ValueError('Debug event data must be an object')
        mock_options = validate_debug_mock_options(payload.get('mock', {}))

        config = agent.get('config')
        if not isinstance(config, dict):
            raise ValueError('Agent configuration is invalid')
        _, runner_id, runner_config = RunnerConfigResolver.resolve_agent_runner_config(config)
        if not runner_id:
            raise ValueError('Agent has no configured runner')

        conversation_id = str(payload.get('conversation_id') or f'debug:{agent_uuid}').strip()
        if not conversation_id or len(conversation_id) > 256:
            raise ValueError('Invalid debug conversation_id')

        actor_payload = payload.get(
            'actor',
            {
                'actor_type': 'user',
                'actor_id': str(
                    event_data.get('member_id')
                    or event_data.get('requester_id')
                    or event_data.get('user_id')
                    or 'debug-user'
                ),
                'actor_name': str(
                    event_data.get('member_name')
                    or event_data.get('requester_name')
                    or event_data.get('user_name')
                    or 'Debug User'
                ),
            },
        )
        subject_payload = payload.get(
            'subject',
            {
                'subject_type': 'message' if event_type.startswith('message.') else event_type.split('.', 1)[0],
                'subject_id': 'debug-subject',
                'data': event_data,
            },
        )
        if not isinstance(actor_payload, dict) or not isinstance(subject_payload, dict):
            raise ValueError('Debug actor and subject must be objects')

        event_id = f'debug:{agent_uuid}:{uuid.uuid4()}'
        is_group = event_type.startswith(('group.', 'bot.')) or bool(event_data.get('group_id'))
        actor = ActorContext.model_validate(actor_payload)
        target_id = str(event_data.get('group_id') or 'debug-group') if is_group else actor.actor_id
        event = AgentEventEnvelope(
            event_id=event_id,
            event_type=event_type,
            event_time=int(time.time()),
            source='webui',
            source_event_type=event_type,
            workspace_id=context.workspace_uuid,
            conversation_id=conversation_id,
            actor=actor,
            subject=SubjectContext.model_validate(subject_payload),
            input=AgentInput.model_validate(
                {
                    'text': text or event_type,
                    'contents': [
                        {'type': 'text', 'text': text or event_type},
                    ],
                    'attachments': [],
                }
            ),
            delivery=DeliveryContext(
                surface='webui',
                reply_target={
                    'target_type': 'group' if is_group else 'person',
                    'target_id': target_id,
                    **({'group_id': target_id} if is_group else {}),
                    **(
                        {'message_id': str(event_data.get('message_id') or 'debug-message')}
                        if event_type.startswith('message.')
                        else {}
                    ),
                },
                supports_streaming=on_result is not None,
                supports_edit=False,
                supports_reaction=False,
                platform_capabilities={
                    'event_type': event_type,
                    'debug': True,
                    'debug_mock': True,
                    'supported_apis': sorted(
                        {tool.api for tool in PLATFORM_TOOL_DEFINITIONS} - set(mock_options.get('unsupported_apis', []))
                    ),
                    'mock_options': mock_options,
                },
            ),
            raw_ref=RawEventRef(ref_id=event_id, storage_key=None),
            data=event_data,
        )
        binding = AgentBinding(
            binding_id=f'debug:{agent_uuid}:{runner_id}',
            scope=BindingScope(scope_type='agent', scope_id=agent_uuid),
            event_types=[event_type],
            runner_id=runner_id,
            runner_config=runner_config,
            resource_policy=ResourcePolicyProjector.from_runner_config(
                runner_config,
                allowed_platform_tool_names=resolve_agent_platform_tool_names(config, event_type),
                allowed_host_tool_names=config.get('allowed_tools'),
                override_runner_tools='allowed_tools' in config,
            ),
            state_policy=StatePolicy(
                state_scopes=['conversation', 'actor', 'subject', 'runner'],
            ),
            delivery_policy=DeliveryPolicy(
                enable_streaming=on_result is not None,
                enable_reply=False,
                enable_interactions=False,
            ),
            agent_id=agent_uuid,
            processor_type='agent',
            processor_id=agent_uuid,
        )
        execution_context = ExecutionContext.from_request(
            context,
            query_uuid=event_id,
        )

        output_items: list[dict[str, typing.Any]] = []
        execution_events: list[dict[str, typing.Any]] = []

        async def observe_result(result: dict[str, typing.Any]) -> None:
            if result.get('type') not in {
                'message.delta',
                'message.completed',
                'tool.call.started',
                'tool.call.completed',
                'run.completed',
                'run.failed',
            }:
                return
            visible_result = copy.deepcopy(
                {
                    key: result[key]
                    for key in ('type', 'data', 'sequence', 'timestamp', 'run_id', 'usage')
                    if key in result
                }
            )
            if on_result is not None:
                await on_result(visible_result)
            elif len(execution_events) < 1000:
                execution_events.append(visible_result)

        final_text = ''
        async for output in self.ap.agent_run_orchestrator.run(
            event,
            binding,
            adapter_context={'_execution_context': execution_context, '_result_observer': observe_result},
        ):
            output_text = self._provider_output_to_text(output)
            if output_text:
                final_text = output_text
            output_items.append(
                {
                    'kind': output.__class__.__name__,
                    'role': str(getattr(output, 'role', '') or ''),
                    'text': output_text,
                }
            )

        return {
            'event_id': event_id,
            'event_type': event_type,
            'conversation_id': conversation_id,
            'final_text': final_text,
            'outputs': output_items,
            'execution_events': execution_events,
        }

    @staticmethod
    def _supports_event_type(patterns: typing.Any, event_type: str) -> bool:
        normalized = patterns if isinstance(patterns, list) else AGENT_DEFAULT_EVENT_PATTERNS
        return any(isinstance(pattern, str) and fnmatch.fnmatchcase(event_type, pattern) for pattern in normalized)

    @staticmethod
    def _provider_output_to_text(output: typing.Any) -> str:
        all_content = getattr(output, 'all_content', None)
        if all_content:
            return str(all_content)
        content = getattr(output, 'content', None)
        if content is None:
            return ''
        if isinstance(content, str):
            return content
        if isinstance(content, list):
            parts: list[str] = []
            for item in content:
                item_data = item.model_dump(mode='json') if hasattr(item, 'model_dump') else item
                if isinstance(item_data, dict) and item_data.get('text') is not None:
                    parts.append(str(item_data['text']))
                elif item_data is not None and not isinstance(item_data, dict):
                    parts.append(str(item_data))
            return ''.join(parts)
        return str(content)

    async def create_agent(self, context: TenantContext, agent_data: dict) -> dict[str, str]:
        workspace_uuid = require_workspace_uuid(context)
        kind = agent_data.get('kind') or AGENT_KIND_AGENT
        if kind == AGENT_KIND_PIPELINE:
            pipeline_uuid = await self.ap.pipeline_service.create_pipeline(
                context,
                {
                    'name': agent_data.get('name') or 'New Pipeline',
                    'description': agent_data.get('description') or '',
                    'emoji': agent_data.get('emoji') or '⚙️',
                    'config': {},
                },
            )
            return {'uuid': pipeline_uuid, 'kind': AGENT_KIND_PIPELINE}

        if kind != AGENT_KIND_AGENT:
            raise ValueError(f'Unsupported agent kind: {kind}')

        config = agent_data['config'] if 'config' in agent_data else await self._get_default_agent_config(context)
        config, runner_id, _ = RunnerConfigResolver.resolve_agent_runner_config(config)
        new_uuid = str(uuid.uuid4())
        values = {
            'workspace_uuid': workspace_uuid,
            'uuid': new_uuid,
            'name': agent_data.get('name') or 'New Agent',
            'description': agent_data.get('description') or '',
            'emoji': agent_data.get('emoji') or '🤖',
            'kind': AGENT_KIND_AGENT,
            'component_ref': runner_id,
            'config': config,
            'supported_event_patterns': (
                agent_data['supported_event_patterns']
                if 'supported_event_patterns' in agent_data
                else AGENT_DEFAULT_EVENT_PATTERNS
            ),
        }
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_agent.Agent).values(**values))
        return {'uuid': new_uuid, 'kind': AGENT_KIND_AGENT}

    async def update_agent(self, context: TenantContext, agent_uuid: str, agent_data: dict) -> None:
        existing_agent = await self._get_agent_row(context, agent_uuid)
        if existing_agent is None:
            pipeline = await self.ap.pipeline_service.get_pipeline(context, agent_uuid)
            if pipeline is None:
                raise ValueError(f'Agent {agent_uuid} not found')
            await self.ap.pipeline_service.update_pipeline(context, agent_uuid, agent_data)
            return

        update_data = {
            field: agent_data[field]
            for field in ('name', 'description', 'emoji', 'config', 'supported_event_patterns')
            if field in agent_data
        }
        if 'config' in update_data:
            config, runner_id, _ = RunnerConfigResolver.resolve_agent_runner_config(update_data['config'])
            update_data['config'] = config
        else:
            _, runner_id, _ = RunnerConfigResolver.resolve_agent_runner_config(existing_agent.config)
        update_data['component_ref'] = runner_id
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_agent.Agent)
                .where(persistence_agent.Agent.uuid == agent_uuid)
                .values(**update_data),
                persistence_agent.Agent,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Agent not found')

    async def delete_agent(self, context: TenantContext, agent_uuid: str) -> None:
        existing_agent = await self._get_agent_row(context, agent_uuid)
        if existing_agent is not None:
            result = await self.ap.persistence_mgr.execute_async(
                scope_statement(
                    sqlalchemy.delete(persistence_agent.Agent).where(persistence_agent.Agent.uuid == agent_uuid),
                    persistence_agent.Agent,
                    context,
                )
            )
            if getattr(result, 'rowcount', None) == 0:
                raise WorkspaceNotFoundError('Agent not found')
            return

        pipeline = await self.ap.pipeline_service.get_pipeline(context, agent_uuid)
        if pipeline is None:
            raise ValueError(f'Agent {agent_uuid} not found')
        await self.ap.pipeline_service.delete_pipeline(context, agent_uuid)

    async def _get_agent_rows(self, context: TenantContext) -> list[persistence_agent.Agent]:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_agent.Agent),
                persistence_agent.Agent,
                context,
            )
        )
        return list(result.all())

    async def _get_agent_row(
        self,
        context: TenantContext,
        agent_uuid: str,
    ) -> persistence_agent.Agent | None:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_agent.Agent).where(persistence_agent.Agent.uuid == agent_uuid),
                persistence_agent.Agent,
                context,
            )
        )
        return result.first()

    async def _get_default_agent_config(self, context: TenantContext) -> dict[str, typing.Any]:
        runners = []
        if getattr(self.ap, 'agent_runner_registry', None) is not None:
            try:
                runners = await self.ap.agent_runner_registry.list_runners(context, bound_plugins=None)
            except Exception as e:
                if getattr(self.ap, 'logger', None):
                    self.ap.logger.warning(f'Failed to load plugin agent runners for default agent config: {e}')

        if not runners:
            return {'runner': {'id': '', 'expire-time': 0}, 'runner_config': {}}

        selected_runner = runners[0]
        return {
            'runner': {'id': selected_runner.id, 'expire-time': 0},
            'runner_config': {
                selected_runner.id: self.ap.pipeline_service._get_default_values_from_schema(
                    selected_runner.config_schema
                )
            },
        }

    def _agent_to_product_item(
        self,
        agent: persistence_agent.Agent,
        include_config: bool = False,
    ) -> dict[str, typing.Any]:
        item = self.ap.persistence_mgr.serialize_model(persistence_agent.Agent, agent)
        item['kind'] = AGENT_KIND_AGENT
        supported_event_patterns = item.get('supported_event_patterns')
        item['capability'] = {
            'supported_event_patterns': (
                supported_event_patterns if isinstance(supported_event_patterns, list) else AGENT_DEFAULT_EVENT_PATTERNS
            ),
            'message_only': False,
        }
        if not include_config:
            item.pop('config', None)
        return item

    @staticmethod
    def _pipeline_to_product_item(pipeline: dict, include_config: bool = False) -> dict[str, typing.Any]:
        item = pipeline.copy()
        item['kind'] = AGENT_KIND_PIPELINE
        item['component_ref'] = 'pipeline'
        item['supported_event_patterns'] = PIPELINE_EVENT_PATTERNS
        item['capability'] = {
            'supported_event_patterns': PIPELINE_EVENT_PATTERNS,
            'message_only': True,
        }
        if not include_config:
            item.pop('config', None)
        return item

    @staticmethod
    def _parse_sort_time(value: typing.Any) -> datetime.datetime:
        if isinstance(value, datetime.datetime):
            return value
        if isinstance(value, str):
            try:
                return datetime.datetime.fromisoformat(value)
            except ValueError:
                return datetime.datetime.min
        return datetime.datetime.min
