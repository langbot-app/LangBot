from __future__ import annotations

import datetime
import uuid
import typing

import sqlalchemy

from ....core import app
from ....entity.persistence import agent as persistence_agent


AGENT_KIND_AGENT = 'agent'
AGENT_KIND_PIPELINE = 'pipeline'
PIPELINE_EVENT_PATTERNS = ['message.*']
AGENT_DEFAULT_EVENT_PATTERNS = ['*']


class AgentService:
    """Unified product surface for Agent processors and Pipelines."""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_agent_metadata(self) -> dict[str, typing.Any]:
        """Return metadata needed by Agent forms."""
        pipeline_metadata = await self.ap.pipeline_service.get_pipeline_metadata()
        ai_metadata = next((item for item in pipeline_metadata if item.get('name') == 'ai'), None)
        return {
            'runner_config': ai_metadata,
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

    async def get_agents(self, sort_by: str = 'updated_at', sort_order: str = 'DESC') -> list[dict]:
        agents = await self._get_agent_rows()
        pipelines = await self.ap.pipeline_service.get_pipelines(sort_by='updated_at', sort_order='DESC')

        items = [self._agent_to_product_item(agent) for agent in agents]
        items.extend(self._pipeline_to_product_item(pipeline) for pipeline in pipelines)

        reverse = sort_order == 'DESC'
        sort_key = sort_by if sort_by in {'created_at', 'updated_at'} else 'updated_at'
        return sorted(items, key=lambda item: self._parse_sort_time(item.get(sort_key)), reverse=reverse)

    async def get_agent(self, agent_uuid: str) -> dict | None:
        agent = await self._get_agent_row(agent_uuid)
        if agent is not None:
            return self._agent_to_product_item(agent, include_config=True)

        pipeline = await self.ap.pipeline_service.get_pipeline(agent_uuid)
        if pipeline is not None:
            return self._pipeline_to_product_item(pipeline, include_config=True)

        return None

    async def create_agent(self, agent_data: dict) -> dict[str, str]:
        kind = agent_data.get('kind') or AGENT_KIND_AGENT
        if kind == AGENT_KIND_PIPELINE:
            pipeline_uuid = await self.ap.pipeline_service.create_pipeline(
                {
                    'name': agent_data.get('name') or 'New Pipeline',
                    'description': agent_data.get('description') or '',
                    'emoji': agent_data.get('emoji') or '⚙️',
                    'config': {},
                }
            )
            return {'uuid': pipeline_uuid, 'kind': AGENT_KIND_PIPELINE}

        if kind != AGENT_KIND_AGENT:
            raise ValueError(f'Unsupported agent kind: {kind}')

        config = agent_data.get('config') or await self._get_default_agent_config()
        runner_id = self._resolve_runner_id(config)
        new_uuid = str(uuid.uuid4())
        values = {
            'uuid': new_uuid,
            'name': agent_data.get('name') or 'New Agent',
            'description': agent_data.get('description') or '',
            'emoji': agent_data.get('emoji') or '🤖',
            'kind': AGENT_KIND_AGENT,
            'component_ref': agent_data.get('component_ref') or runner_id,
            'config': config,
            'enabled': agent_data.get('enabled', True),
            'supported_event_patterns': agent_data.get('supported_event_patterns') or AGENT_DEFAULT_EVENT_PATTERNS,
        }
        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_agent.Agent).values(**values))
        return {'uuid': new_uuid, 'kind': AGENT_KIND_AGENT}

    async def update_agent(self, agent_uuid: str, agent_data: dict) -> None:
        existing_agent = await self._get_agent_row(agent_uuid)
        if existing_agent is None:
            pipeline = await self.ap.pipeline_service.get_pipeline(agent_uuid)
            if pipeline is None:
                raise ValueError(f'Agent {agent_uuid} not found')
            await self.ap.pipeline_service.update_pipeline(agent_uuid, agent_data)
            return

        update_data = agent_data.copy()
        for protected_field in ('uuid', 'kind', 'created_at', 'updated_at', 'capability'):
            update_data.pop(protected_field, None)
        if 'config' in update_data:
            update_data['component_ref'] = update_data.get('component_ref') or self._resolve_runner_id(
                update_data['config']
            )
        if 'supported_event_patterns' in update_data and not update_data['supported_event_patterns']:
            update_data['supported_event_patterns'] = AGENT_DEFAULT_EVENT_PATTERNS

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_agent.Agent)
            .where(persistence_agent.Agent.uuid == agent_uuid)
            .values(**update_data)
        )

    async def delete_agent(self, agent_uuid: str) -> None:
        existing_agent = await self._get_agent_row(agent_uuid)
        if existing_agent is not None:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.delete(persistence_agent.Agent).where(persistence_agent.Agent.uuid == agent_uuid)
            )
            return

        pipeline = await self.ap.pipeline_service.get_pipeline(agent_uuid)
        if pipeline is None:
            raise ValueError(f'Agent {agent_uuid} not found')
        await self.ap.pipeline_service.delete_pipeline(agent_uuid)

    async def _get_agent_rows(self) -> list[persistence_agent.Agent]:
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_agent.Agent))
        return list(result.all())

    async def _get_agent_row(self, agent_uuid: str) -> persistence_agent.Agent | None:
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_agent.Agent).where(persistence_agent.Agent.uuid == agent_uuid)
        )
        return result.first()

    async def _get_default_agent_config(self) -> dict[str, typing.Any]:
        runners = []
        if getattr(self.ap, 'agent_runner_registry', None) is not None:
            try:
                runners = await self.ap.agent_runner_registry.list_runners(bound_plugins=None)
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

    @staticmethod
    def _resolve_runner_id(config: dict[str, typing.Any]) -> str | None:
        runner = config.get('runner') if isinstance(config, dict) else None
        if isinstance(runner, dict):
            runner_id = runner.get('id')
            if runner_id:
                return runner_id
        return None

    def _agent_to_product_item(
        self,
        agent: persistence_agent.Agent,
        include_config: bool = False,
    ) -> dict[str, typing.Any]:
        item = self.ap.persistence_mgr.serialize_model(persistence_agent.Agent, agent)
        item['kind'] = AGENT_KIND_AGENT
        item['capability'] = {
            'supported_event_patterns': item.get('supported_event_patterns') or AGENT_DEFAULT_EVENT_PATTERNS,
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
        item['enabled'] = True
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
