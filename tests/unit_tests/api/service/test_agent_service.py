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
WORKSPACE_UUID = 'workspace-test'


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
        workspace_uuid=WORKSPACE_UUID,
        uuid=agent_uuid,
        name=name,
        description='Agent description',
        emoji='A',
        kind=AGENT_KIND_AGENT,
        component_ref='plugin:test/runner/default',
        config=config
        or {
            'runner': {'id': 'plugin:test/runner/default', 'expire-time': 0},
            'runner_config': {'plugin:test/runner/default': {'temperature': 0.2}},
        },
        supported_event_patterns=(supported_event_patterns if supported_event_patterns is not None else ['*']),
        created_at=dt.datetime(2026, 1, 1, 9, 0, 0),
        updated_at=updated_at or dt.datetime(2026, 1, 1, 10, 0, 0),
    )


def _serialize_agent(model_cls, entity, masked_columns=None):
    return {
        'workspace_uuid': entity.workspace_uuid,
        'uuid': entity.uuid,
        'name': entity.name,
        'description': entity.description,
        'emoji': entity.emoji,
        'kind': entity.kind,
        'component_ref': entity.component_ref,
        'config': entity.config,
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
        if not key.startswith(('uuid_', 'workspace_uuid_'))
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
    app.tool_mgr = None
    app.logger = Mock()
    return app


class TestAgentServiceMetadata:
    async def test_get_agent_metadata_exposes_runner_config_and_kind_capabilities(self):
        app = _make_app()
        ai_metadata = {'name': 'ai', 'stages': [{'name': 'runner'}]}
        app.pipeline_service.get_pipeline_metadata = AsyncMock(
            return_value=[{'name': 'trigger'}, ai_metadata, {'name': 'output'}]
        )
        host_tools = [
            {
                'name': 'exec',
                'source': 'builtin',
                'source_name': 'LangBot',
            },
            {
                'name': 'weather',
                'source': 'mcp',
                'source_name': 'weather-server',
            },
        ]
        app.tool_mgr = SimpleNamespace(get_resolved_tool_catalog=AsyncMock(return_value=host_tools))

        metadata = await AgentService(app).get_agent_metadata(WORKSPACE_UUID)
        app.pipeline_service.get_pipeline_metadata.assert_awaited_once_with(WORKSPACE_UUID)

        assert metadata['runner_config'] == ai_metadata
        assert any(tool['name'] == 'event_reply' for tool in metadata['platform_tools'])
        assert all(tool['name'] != 'call_platform_api' for tool in metadata['platform_tools'])
        assert metadata['host_tools'] == host_tools
        app.tool_mgr.get_resolved_tool_catalog.assert_awaited_once_with(
            WORKSPACE_UUID,
            include_skill_authoring=True,
            include_mcp_resource_tools=True,
        )
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


class TestAgentServiceDebug:
    @pytest.mark.parametrize('streaming', [False, True])
    async def test_debug_agent_runs_configured_runner_with_synthetic_event(self, streaming):
        app = _make_app()
        agent_config = _agent_row().config
        agent_config['allowed_platform_tools'] = ['platform_get_user_info']
        agent_config['event_tool_permissions'] = {
            'message.*': ['event_reply'],
            'group.member.joined': ['event_get_actor'],
        }
        agent_config['allowed_tools'] = ['exec', 'weather']

        visible_event = {
            'type': 'tool.call.started',
            'data': {'tool_name': 'exec', 'parameters': {'command': 'echo hi'}},
        }
        observer = AsyncMock() if streaming else None

        async def run_agent(event, binding, adapter_context):
            assert binding.delivery_policy.enable_streaming is streaming
            await adapter_context['_result_observer']({**visible_event, 'private_context': 'must not leak'})
            await adapter_context['_result_observer']({'type': 'state.updated', 'data': {'private': True}})
            yield SimpleNamespace(
                role='assistant',
                content='debug result',
                all_content=None,
            )

        app.agent_run_orchestrator = SimpleNamespace(run=Mock(side_effect=run_agent))
        service = AgentService(app)
        service.get_agent = AsyncMock(
            return_value={
                'uuid': 'agent-1',
                'kind': AGENT_KIND_AGENT,
                'supported_event_patterns': ['*'],
                'config': agent_config,
            }
        )
        context = SimpleNamespace(
            instance_uuid='instance-test',
            workspace_uuid=WORKSPACE_UUID,
            placement_generation=1,
            principal=SimpleNamespace(account_uuid='account-test'),
            entitlement_revision=0,
        )

        result = await service.debug_agent(
            context,
            'agent-1',
            {
                'event_type': 'group.member.joined',
                'text': 'A member joined.',
                'data': {'member_id': 'user-1'},
                'conversation_id': 'debug-session',
            },
            on_result=observer,
        )

        if streaming:
            observer.assert_awaited_once_with(visible_event)
            assert result['execution_events'] == []
        else:
            assert result['execution_events'] == [visible_event]
        assert result['event_type'] == 'group.member.joined'
        assert result['conversation_id'] == 'debug-session'
        assert result['final_text'] == 'debug result'
        assert result['outputs'] == [
            {
                'kind': 'SimpleNamespace',
                'role': 'assistant',
                'text': 'debug result',
            }
        ]
        event, binding = app.agent_run_orchestrator.run.call_args.args
        assert event.workspace_id == WORKSPACE_UUID
        assert event.delivery.platform_capabilities['debug_mock'] is True
        assert 'send_message' in event.delivery.platform_capabilities['supported_apis']
        assert event.delivery.reply_target['target_id'] == 'debug-group'
        assert binding.delivery_policy.enable_reply is False
        assert event.data == {'member_id': 'user-1'}
        assert binding.agent_id == 'agent-1'
        assert binding.runner_id == 'plugin:test/runner/default'
        assert binding.resource_policy.allowed_platform_tool_names == [
            'platform_get_user_info',
            'event_reply',
            'event_get_actor',
            'event_get_group',
            'event_get_group_member',
        ]
        assert binding.resource_policy.allow_all_tools is False
        assert binding.resource_policy.allowed_tool_names == ['exec', 'weather']
        assert (
            app.agent_run_orchestrator.run.call_args.kwargs['adapter_context']['_execution_context'].workspace_uuid
            == WORKSPACE_UUID
        )

    async def test_debug_agent_rejects_unsupported_event_type(self):
        app = _make_app()
        service = AgentService(app)
        service.get_agent = AsyncMock(
            return_value={
                'uuid': 'agent-1',
                'kind': AGENT_KIND_AGENT,
                'supported_event_patterns': ['message.*'],
                'config': _agent_row().config,
            }
        )
        context = SimpleNamespace(workspace_uuid=WORKSPACE_UUID)

        with pytest.raises(ValueError, match='does not support'):
            await service.debug_agent(
                context,
                'agent-1',
                {'event_type': 'group.member.joined'},
            )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'event_type',
    [
        'message.received',
        'message.edited',
        'message.deleted',
        'message.reaction',
        'group.member_joined',
        'group.member_left',
        'group.member_banned',
        'friend.request_received',
        'friend.added',
        'feedback.received',
        'bot.invited_to_group',
        'bot.muted',
        'bot.unmuted',
        'bot.removed_from_group',
        'platform.specific',
        'custom.probe',
    ],
)
async def test_debug_event_matrix_preserves_scope_targets_and_mock_options(event_type):
    app = _make_app()
    captured = []

    async def run(event, binding, adapter_context):
        captured.append((event, binding))
        if False:
            yield

    app.agent_run_orchestrator = SimpleNamespace(run=run)
    service = AgentService(app)
    service.get_agent = AsyncMock(
        return_value={'kind': AGENT_KIND_AGENT, 'supported_event_patterns': ['*'], 'config': _agent_row().config}
    )
    context = SimpleNamespace(
        instance_uuid='instance-test',
        workspace_uuid=WORKSPACE_UUID,
        placement_generation=1,
        principal=SimpleNamespace(account_uuid='account-test'),
        entitlement_revision=0,
    )
    data = {
        'group_id': '群组-42',
        'member_id': 'user-42',
        'member_name': '测试用户🙂',
        'request_id': 'request-42',
        'nested': {'value': [1, 2]},
    }
    await service.debug_agent(
        context,
        'agent-1',
        {
            'event_type': event_type,
            'text': 'probe',
            'data': data,
            'mock': {'errors': {'event_reply': 'denied'}, 'unsupported_apis': ['delete_message']},
        },
    )
    event, binding = captured[0]
    assert event.data == data
    assert event.actor.actor_name == '测试用户🙂'
    assert event.delivery.reply_target['target_id'] == '群组-42'
    assert 'delete_message' not in event.delivery.platform_capabilities['supported_apis']
    assert event.delivery.platform_capabilities['mock_options']['errors'] == {'event_reply': 'denied'}
    assert event.bot_id is None
    assert binding.delivery_policy.enable_reply is False


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'payload',
    [
        {'event_type': ''},
        {'data': []},
        {'data': None},
        {'data': False},
        {'mock': []},
        {'mock': {'errors': {'event_reply': None}}},
        {'actor': []},
    ],
)
async def test_debug_rejects_invalid_envelope_before_execution(payload):
    app = _make_app()
    app.agent_run_orchestrator = SimpleNamespace(run=Mock(side_effect=AssertionError('invalid request executed')))
    service = AgentService(app)
    service.get_agent = AsyncMock(
        return_value={'kind': AGENT_KIND_AGENT, 'supported_event_patterns': ['*'], 'config': _agent_row().config}
    )
    with pytest.raises(ValueError):
        await service.debug_agent(SimpleNamespace(workspace_uuid=WORKSPACE_UUID), 'agent-1', payload)


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

        agents = await AgentService(app).get_agents(
            WORKSPACE_UUID,
            sort_by='updated_at',
            sort_order='DESC',
        )

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

        result = await AgentService(app).get_agent(WORKSPACE_UUID, 'agent-1')

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

        result = await AgentService(app).get_agent(WORKSPACE_UUID, 'pipeline-1')

        assert result['kind'] == AGENT_KIND_PIPELINE
        assert 'enabled' not in result
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
            WORKSPACE_UUID,
            {
                'name': 'Support Agent',
                'description': 'Handles support events',
                'emoji': 'S',
                'component_ref': 'plugin:caller/must-not-win/default',
            },
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
        assert 'enabled' not in insert_values
        assert insert_values['supported_event_patterns'] == AGENT_DEFAULT_EVENT_PATTERNS
        app.pipeline_service._get_default_values_from_schema.assert_called_once_with(runner.config_schema)

    @pytest.mark.parametrize(
        'config',
        [
            None,
            [],
            {'runner': {'id': 'plugin:test/runner/default'}},
            {'runner': {'id': 123}, 'runner_config': {}},
            {
                'runner': {'id': 'plugin:test/runner/default'},
                'runner_config': {'plugin:test/runner/default': ['invalid']},
            },
            {
                'runner': {'id': 'plugin:test/runner/default'},
                'runner_config': {},
            },
        ],
    )
    async def test_create_agent_rejects_malformed_4x_runner_config(self, config):
        app = _make_app()

        with pytest.raises(ValueError, match='Agent config|runner_config'):
            await AgentService(app).create_agent(
                WORKSPACE_UUID,
                {'name': 'Invalid Agent', 'config': config},
            )

        app.persistence_mgr.execute_async.assert_not_awaited()

    @pytest.mark.parametrize(
        ('field_name', 'invalid_value'),
        [
            ('enable-all-tools', 0),
            ('enable-all-tools', None),
            ('enable-all-tools', 'false'),
            ('mcp-resource-agent-read-enabled', 0),
            ('mcp-resource-agent-read-enabled', None),
            ('mcp-resource-agent-read-enabled', 'false'),
        ],
    )
    async def test_create_agent_rejects_non_boolean_security_fields_before_write(
        self,
        field_name,
        invalid_value,
    ):
        app = _make_app()
        runner_id = 'plugin:test/runner/default'

        with pytest.raises(ValueError, match=f'{field_name}.*boolean'):
            await AgentService(app).create_agent(
                WORKSPACE_UUID,
                {
                    'name': 'Invalid Agent',
                    'config': {
                        'runner': {'id': runner_id},
                        'runner_config': {runner_id: {field_name: invalid_value}},
                    },
                },
            )

        app.persistence_mgr.execute_async.assert_not_awaited()

    @pytest.mark.parametrize('invalid_value', [0, None, 'false'])
    async def test_create_agent_rejects_non_boolean_mcp_resource_enabled_before_write(self, invalid_value):
        app = _make_app()
        runner_id = 'plugin:test/runner/default'

        with pytest.raises(ValueError, match=r'mcp-resources\[0\]\.enabled.*boolean'):
            await AgentService(app).create_agent(
                WORKSPACE_UUID,
                {
                    'name': 'Invalid Agent',
                    'config': {
                        'runner': {'id': runner_id},
                        'runner_config': {
                            runner_id: {
                                'mcp-resources': [
                                    {'uri': 'file:///README.md', 'enabled': invalid_value},
                                ]
                            }
                        },
                    },
                },
            )

        app.persistence_mgr.execute_async.assert_not_awaited()

    async def test_create_agent_derives_empty_component_ref_from_empty_runner(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(return_value=Mock())

        await AgentService(app).create_agent(
            WORKSPACE_UUID,
            {
                'name': 'Unconfigured Agent',
                'component_ref': 'plugin:caller/must-not-win/default',
                'config': {
                    'runner': {'id': ''},
                    'runner_config': {},
                },
            },
        )

        insert_values = _compiled_params(app.persistence_mgr.execute_async.await_args.args[0])
        assert insert_values['component_ref'] is None

    async def test_create_agent_preserves_explicit_empty_event_scope(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(return_value=Mock())

        await AgentService(app).create_agent(
            WORKSPACE_UUID,
            {
                'name': 'Dormant Agent',
                'supported_event_patterns': [],
                'config': {
                    'runner': {'id': ''},
                    'runner_config': {},
                },
            },
        )

        insert_values = _compiled_params(app.persistence_mgr.execute_async.await_args.args[0])
        assert insert_values['supported_event_patterns'] == []

    async def test_update_agent_rejects_malformed_4x_runner_config_before_write(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(return_value=_result(first_item=_agent_row(agent_uuid='agent-1')))

        with pytest.raises(ValueError, match='runner_config'):
            await AgentService(app).update_agent(
                WORKSPACE_UUID,
                'agent-1',
                {
                    'config': {
                        'runner': {'id': 'plugin:test/runner/default'},
                        'runner_config': {'plugin:test/runner/default': 'invalid'},
                    }
                },
            )

        assert app.persistence_mgr.execute_async.await_count == 1

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
            WORKSPACE_UUID,
            'agent-1',
            {
                'uuid': 'caller-owned-uuid',
                'kind': AGENT_KIND_PIPELINE,
                'created_at': '2020-01-01T00:00:00',
                'updated_at': '2020-01-01T00:00:00',
                'capability': {'message_only': True},
                'component_ref': 'plugin:caller/must-not-win/default',
                'name': 'Updated Agent',
                'config': new_config,
                'supported_event_patterns': [],
            },
        )

        update_values = _compiled_update_values(app.persistence_mgr.execute_async.await_args_list[1].args[0])
        assert update_values == {
            'name': 'Updated Agent',
            'config': new_config,
            'supported_event_patterns': [],
            'component_ref': 'plugin:test/new-runner/default',
        }

    async def test_update_agent_ignores_component_ref_without_config(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(
            side_effect=[
                _result(first_item=_agent_row(agent_uuid='agent-1')),
                Mock(),
            ]
        )

        await AgentService(app).update_agent(
            WORKSPACE_UUID,
            'agent-1',
            {
                'name': 'Updated Agent',
                'component_ref': 'plugin:caller/must-not-win/default',
            },
        )

        update_values = _compiled_update_values(app.persistence_mgr.execute_async.await_args_list[1].args[0])
        assert update_values == {
            'name': 'Updated Agent',
            'component_ref': 'plugin:test/runner/default',
        }

    async def test_update_agent_component_ref_only_repairs_from_existing_config(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(
            side_effect=[
                _result(first_item=_agent_row(agent_uuid='agent-1')),
                Mock(),
            ]
        )

        await AgentService(app).update_agent(
            WORKSPACE_UUID,
            'agent-1',
            {'component_ref': 'plugin:caller/must-not-win/default'},
        )

        update_values = _compiled_update_values(app.persistence_mgr.execute_async.await_args_list[1].args[0])
        assert update_values == {'component_ref': 'plugin:test/runner/default'}

    async def test_update_agent_clears_component_ref_for_empty_runner(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(
            side_effect=[
                _result(first_item=_agent_row(agent_uuid='agent-1')),
                Mock(),
            ]
        )
        config = {'runner': {'id': ''}, 'runner_config': {}}

        await AgentService(app).update_agent(
            WORKSPACE_UUID,
            'agent-1',
            {
                'component_ref': 'plugin:caller/must-not-win/default',
                'config': config,
            },
        )

        update_values = _compiled_update_values(app.persistence_mgr.execute_async.await_args_list[1].args[0])
        assert update_values == {'config': config, 'component_ref': None}

    async def test_pipeline_kind_create_update_delete_delegate_to_pipeline_service(self):
        app = _make_app()
        app.persistence_mgr.execute_async = AsyncMock(return_value=_result(first_item=None))
        app.pipeline_service.create_pipeline = AsyncMock(return_value='pipeline-created')
        app.pipeline_service.get_pipeline = AsyncMock(return_value={'uuid': 'pipeline-1'})
        service = AgentService(app)

        created = await service.create_agent(
            WORKSPACE_UUID,
            {
                'kind': AGENT_KIND_PIPELINE,
                'name': 'Pipeline Agent',
                'description': 'Legacy pipeline',
                'emoji': 'P',
            },
        )
        await service.update_agent(
            WORKSPACE_UUID,
            'pipeline-1',
            {'name': 'Updated Pipeline'},
        )
        await service.delete_agent(WORKSPACE_UUID, 'pipeline-1')

        assert created == {'uuid': 'pipeline-created', 'kind': AGENT_KIND_PIPELINE}
        app.pipeline_service.create_pipeline.assert_awaited_once_with(
            WORKSPACE_UUID,
            {
                'name': 'Pipeline Agent',
                'description': 'Legacy pipeline',
                'emoji': 'P',
                'config': {},
            },
        )
        app.pipeline_service.update_pipeline.assert_awaited_once_with(
            WORKSPACE_UUID,
            'pipeline-1',
            {'name': 'Updated Pipeline'},
        )
        app.pipeline_service.delete_pipeline.assert_awaited_once_with(
            WORKSPACE_UUID,
            'pipeline-1',
        )
