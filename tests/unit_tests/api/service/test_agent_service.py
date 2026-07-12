from __future__ import annotations

import datetime as dt
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.agent import (
    AGENT_DEFAULT_EVENT_PATTERNS,
    AGENT_KIND_AGENT,
    AGENT_KIND_PIPELINE,
    PIPELINE_EVENT_PATTERNS,
    AgentService,
)


pytestmark = pytest.mark.asyncio


def _result(items: list | None = None, first_item=None):
    result = Mock()
    result.all = Mock(return_value=items or [])
    result.first = Mock(return_value=first_item)
    return result


def _agent_row(
    agent_uuid: str = 'agent-1',
    name: str = 'Test Agent',
    updated_at: dt.datetime | str | None = None,
    config: dict | None = None,
    supported_event_patterns: list[str] | None = None,
):
    return SimpleNamespace(
        uuid=agent_uuid,
        name=name,
        description='Agent description',
        emoji='A',
        kind=AGENT_KIND_AGENT,
        component_ref='plugin:test/runner/default',
        config=config or {
            'runner': {'id': 'plugin:test/runner/default', 'expire-time': 0},
            'runner_config': {'plugin:test/runner/default': {'temperature': 0.2}},
        },
        enabled=True,
        supported_event_patterns=supported_event_patterns or ['*'],
        created_at=dt.datetime(2026, 1, 1, 9, 0, 0),
        updated_at=updated_at or dt.datetime(2026, 1, 1, 10, 0, 0),
    )


def _serialize_agent(model_cls, entity, masked_columns=None):
    return {
        'uuid': entity.uuid,
        'name': entity.name,
        'description': entity.description,
        'emoji': entity.emoji,
        'kind': entity.kind,
        'component_ref': entity.component_ref,
        'config': entity.config,
        'enabled': entity.enabled,
        'supported_event_patterns': entity.supported_event_patterns,
        'created_at': entity.created_at,
        'updated_at': entity.updated_at,
    }


def _compiled_params(statement):
    return statement.compile().params


def _compiled_update_values(statement):
    return {
        key: value
        for key, value in statement.compile().params.items()
        if not key.startswith('uuid_')
    }


def _make_app():
    app = SimpleNamespace()
    app.persistence_mgr = SimpleNamespace(
        execute_async=AsyncMock(),
        serialize_model=Mock(side_effect=_serialize_agent),
    )
    app.pipeline_service = SimpleNamespace(
        get_pipeline_metadata=AsyncMock(return_value=[]),
        get_pipelines=AsyncMock(return_value=[]),
        get_pipeline=AsyncMock(return_value=None),
        create_pipeline=AsyncMock(),
        update_pipeline=AsyncMock(),
        delete_pipeline=AsyncMock(),
        _get_default_values_from_schema=Mock(return_value={}),
    )
    app.agent_runner_registry = None
    app.logger = Mock()
    return app


class TestAgentServiceMetadata:
    async def test_get_agent_metadata_exposes_runner_config_and_kind_capabilities(self):
        app = _make_app()
        ai_metadata = {'name': 'ai', 'stages': [{'name': 'runner'}]}
        app.pipeline_service.get_pipeline_metadata = AsyncMock(
            return_value=[{'name': 'trigger'}, ai_metadata, {'name': 'output'}]
        )

        metadata = await AgentService(app).get_agent_metadata()

        assert metadata['runner_config'] == ai_metadata
        assert metadata['kinds'] == [
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
        ]


class TestAgentServiceListAndLookup:
    async def test_get_agents_merges_agents_and_pipelines_without_leaking_config(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(
            return_value=_result(
                items=[
                    _agent_row(
                        agent_uuid='agent-1',
                        updated_at=dt.datetime(2026, 1, 1, 10, 0, 0),
                        supported_event_patterns=['platform.member.*'],
                    )
                ]
            )
        )
        app.pipeline_service.get_pipelines = AsyncMock(
            return_value=[
                {
                    'uuid': 'pipeline-1',
                    'name': 'Pipeline Agent',
                    'description': 'Legacy pipeline',
                    'emoji': 'P',
                    'config': {'ai': {'runner': {'id': 'pipeline-runner'}}},
                    'created_at': '2026-01-01T08:00:00',
                    'updated_at': '2026-01-01T11:00:00',
                }
            ]
        )

        agents = await AgentService(app).get_agents(sort_by='updated_at', sort_order='DESC')

        assert [agent['uuid'] for agent in agents] == ['pipeline-1', 'agent-1']
        assert agents[0]['kind'] == AGENT_KIND_PIPELINE
        assert agents[0]['component_ref'] == 'pipeline'
        assert agents[0]['capability'] == {
            'supported_event_patterns': PIPELINE_EVENT_PATTERNS,
            'message_only': True,
        }
        assert agents[1]['kind'] == AGENT_KIND_AGENT
        assert agents[1]['capability'] == {
            'supported_event_patterns': ['platform.member.*'],
            'message_only': False,
        }
        assert all('config' not in agent for agent in agents)

    async def test_get_agent_returns_agent_with_config_before_pipeline_fallback(self):
        app = _make_app()
        agent = _agent_row(agent_uuid='agent-1')
        app.persistence_mgr.execute_async = AsyncMock(return_value=_result(first_item=agent))

        result = await AgentService(app).get_agent('agent-1')

        assert result['uuid'] == 'agent-1'
        assert result['kind'] == AGENT_KIND_AGENT
        assert result['config'] == agent.config
        app.pipeline_service.get_pipeline.assert_not_awaited()

    async def test_get_agent_falls_back_to_pipeline_product_item_with_config(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(return_value=_result(first_item=None))
        app.pipeline_service.get_pipeline = AsyncMock(
            return_value={
                'uuid': 'pipeline-1',
                'name': 'Pipeline Agent',
                'description': 'Legacy pipeline',
                'emoji': 'P',
                'config': {'ai': {'runner': {'id': 'pipeline-runner'}}},
                'created_at': '2026-01-01T08:00:00',
                'updated_at': '2026-01-01T11:00:00',
            }
        )

        result = await AgentService(app).get_agent('pipeline-1')

        assert result['kind'] == AGENT_KIND_PIPELINE
        assert result['enabled'] is True
        assert result['config'] == {'ai': {'runner': {'id': 'pipeline-runner'}}}
        assert result['capability']['message_only'] is True


class TestAgentServiceCreateUpdateDelete:
    async def test_create_agent_uses_default_runner_config_from_registry(self):
        app = _make_app()
        runner = SimpleNamespace(
            id='plugin:langbot-team/LocalAgent/default',
            config_schema=[
                {'name': 'model', 'default': 'gpt-4.1'},
                {'name': 'temperature', 'default': 0.2},
                {'name': 'no-default'},
            ],
        )
        app.agent_runner_registry = SimpleNamespace(list_runners=AsyncMock(return_value=[runner]))
        app.pipeline_service._get_default_values_from_schema = Mock(
            return_value={'model': 'gpt-4.1', 'temperature': 0.2}
        )
        app.persistence_mgr.execute_async = AsyncMock(return_value=Mock())

        result = await AgentService(app).create_agent(
            {
                'name': 'Support Agent',
                'description': 'Handles support events',
                'emoji': 'S',
            }
        )

        insert_values = _compiled_params(app.persistence_mgr.execute_async.await_args.args[0])
        assert result['kind'] == AGENT_KIND_AGENT
        assert result['uuid'] == insert_values['uuid']
        assert insert_values['name'] == 'Support Agent'
        assert insert_values['component_ref'] == runner.id
        assert insert_values['config'] == {
            'runner': {'id': runner.id, 'expire-time': 0},
            'runner_config': {runner.id: {'model': 'gpt-4.1', 'temperature': 0.2}},
        }
        assert insert_values['enabled'] is True
        assert insert_values['supported_event_patterns'] == AGENT_DEFAULT_EVENT_PATTERNS
        app.pipeline_service._get_default_values_from_schema.assert_called_once_with(runner.config_schema)

    async def test_update_agent_protects_immutable_fields_and_recalculates_component_ref(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(
            side_effect=[
                _result(first_item=_agent_row(agent_uuid='agent-1')),
                Mock(),
            ]
        )
        new_config = {
            'runner': {'id': 'plugin:test/new-runner/default', 'expire-time': 0},
            'runner_config': {'plugin:test/new-runner/default': {'timeout': 30}},
        }

        await AgentService(app).update_agent(
            'agent-1',
            {
                'uuid': 'caller-owned-uuid',
                'kind': AGENT_KIND_PIPELINE,
                'created_at': '2020-01-01T00:00:00',
                'updated_at': '2020-01-01T00:00:00',
                'capability': {'message_only': True},
                'name': 'Updated Agent',
                'config': new_config,
                'supported_event_patterns': [],
            },
        )

        update_values = _compiled_update_values(app.persistence_mgr.execute_async.await_args_list[1].args[0])
        assert update_values == {
            'name': 'Updated Agent',
            'config': new_config,
            'supported_event_patterns': AGENT_DEFAULT_EVENT_PATTERNS,
            'component_ref': 'plugin:test/new-runner/default',
        }

    async def test_pipeline_kind_create_update_delete_delegate_to_pipeline_service(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(return_value=_result(first_item=None))
        app.pipeline_service.create_pipeline = AsyncMock(return_value='pipeline-created')
        app.pipeline_service.get_pipeline = AsyncMock(return_value={'uuid': 'pipeline-1'})
        service = AgentService(app)

        created = await service.create_agent(
            {
                'kind': AGENT_KIND_PIPELINE,
                'name': 'Pipeline Agent',
                'description': 'Legacy pipeline',
                'emoji': 'P',
            }
        )
        await service.update_agent('pipeline-1', {'name': 'Updated Pipeline'})
        await service.delete_agent('pipeline-1')

        assert created == {'uuid': 'pipeline-created', 'kind': AGENT_KIND_PIPELINE}
        app.pipeline_service.create_pipeline.assert_awaited_once_with(
            {
                'name': 'Pipeline Agent',
                'description': 'Legacy pipeline',
                'emoji': 'P',
                'config': {},
            }
        )
        app.pipeline_service.update_pipeline.assert_awaited_once_with(
            'pipeline-1',
            {'name': 'Updated Pipeline'},
        )
        app.pipeline_service.delete_pipeline.assert_awaited_once_with('pipeline-1')
