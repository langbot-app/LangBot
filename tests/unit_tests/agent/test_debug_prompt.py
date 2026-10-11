"""Stored Agent config -> debug orchestration -> authenticated SDK prompt pull.

Only plugin discovery/transport are local doubles. Agent persistence, Query and
RunnerContext entities, orchestration, session authorization and GET_PROMPT run
normally; no model or live runtime is needed.
"""

from __future__ import annotations

import copy
import logging
from types import SimpleNamespace

import pytest
from sqlalchemy.ext.asyncio import create_async_engine

from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.provider.prompt import Prompt
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.proxies.runner import RunnerAPIProxy
from langbot_plugin.entities.io.actions.enums import PluginToRuntimeAction
from langbot_plugin.entities.io.context import InstallationBinding

from langbot.pkg.agent.runner.descriptor import RunnerDescriptor
from langbot.pkg.agent.runner.execution_context import build_execution_query
from langbot.pkg.agent.runner.host_models import AgentBinding, AgentEventEnvelope, BindingScope
from langbot.pkg.agent.runner.orchestrator import AgentRunOrchestrator
from langbot.pkg.agent.runner.persistent_state_store import reset_persistent_state_store
from langbot.pkg.agent.runner.session_registry import get_session_registry
from langbot.pkg.api.http.service.model import LLMModelsService
from langbot.pkg.api.http.context import (
    ExecutionContext,
    PrincipalContext,
    PrincipalType,
    RequestContext,
    WorkspaceContext,
)
from langbot.pkg.api.http.service.agent import AgentService
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.plugin.handler import RuntimeConnectionHandler


RUNNER_ID = 'plugin:langbot-team/LocalAgent/default'
DEFAULT_PROMPT = [{'role': 'system', 'content': 'Schema default'}]
STORED_PROMPT = [{'role': 'system', 'content': 'Reply only with STORED_MARKER'}]


def request_context(workspace='workspace-a'):
    return RequestContext(
        instance_uuid='instance-test',
        placement_generation=1,
        request_id='debug-prompt-test',
        auth_type='user_token',
        principal=PrincipalContext(PrincipalType.ACCOUNT, account_uuid='account-test'),
        workspace=WorkspaceContext(workspace, 'membership-test', 'owner', frozenset()),
    )


class LocalPersistence:
    serialize_model = PersistenceManager.serialize_model

    def __init__(self, engine):
        self.engine = engine

    def get_db_engine(self):
        return self.engine

    async def execute_async(self, statement):
        async with self.engine.begin() as conn:
            return await conn.execute(statement)


class ScopedRunnerRegistry:
    def __init__(self):
        self.descriptors = {}
        self.calls = []

    async def get(self, context, runner_id, bound_plugins=None):
        self.calls.append((context.workspace_uuid, runner_id))
        return self.descriptors[(context.workspace_uuid, runner_id)]


class PromptPullConnector:
    """Loop back the real SDK prompt API into the real Host action handler."""

    is_enable_plugin = True

    def __init__(self, ap):
        self.ap = ap
        self.observations = []

    async def run_runner(self, plugin_author, plugin_name, runner_name, context):
        ctx = RunnerContext.model_validate(context)
        session = await get_session_registry().get(ctx.run_id)
        query = session['execution_query']
        binding = InstallationBinding(
            instance_uuid='instance-test',
            workspace_uuid=ctx.conversation.workspace_id,
            placement_generation=1,
            installation_uuid='00000000-0000-4000-8000-000000000001',
            runtime_revision=1,
            artifact_digest='a' * 64,
        )
        handler = RuntimeConnectionHandler(None, None, self.ap)
        handler.register_installation_binding(binding, plugin_author=plugin_author, plugin_name=plugin_name)

        async def call_action(action, data, timeout):
            assert action == PluginToRuntimeAction.GET_PROMPT
            token = handler._current_action_context.set(binding)
            try:
                response = await handler.actions[action.value](
                    {**data, 'caller_plugin_identity': f'{plugin_author}/{plugin_name}'}
                )
                assert response.code == 0, response
                return response.data
            finally:
                handler._current_action_context.reset(token)

        prompt = await RunnerAPIProxy(ctx, SimpleNamespace(call_action=call_action)).get_prompt()
        self.observations.append((ctx, query, prompt))
        yield {'type': 'run.completed', 'data': {'finish_reason': 'stop'}}


@pytest.fixture
async def harness():
    reset_persistent_state_store()
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    tables = [
        Base.metadata.tables[name]
        for name in (
            'agents',
            'agent_run',
            'agent_run_event',
            'runner_state',
            'event_log',
            'transcript',
        )
    ]
    async with engine.begin() as conn:
        await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=tables))

    async def get_execution_binding(workspace_uuid, *, expected_generation):
        assert expected_generation == 1
        return SimpleNamespace(instance_uuid='instance-test', workspace_uuid=workspace_uuid, placement_generation=1)

    ap = SimpleNamespace(
        logger=logging.getLogger(__name__),
        persistence_mgr=LocalPersistence(engine),
        ver_mgr=SimpleNamespace(get_current_version=lambda: 'test'),
        workspace_service=SimpleNamespace(get_execution_binding=get_execution_binding),
        runner_registry=ScopedRunnerRegistry(),
    )
    ap.plugin_connector = PromptPullConnector(ap)
    ap.llm_model_service = LLMModelsService(ap)
    ap.agent_run_orchestrator = AgentRunOrchestrator(ap, ap.runner_registry)
    ap.agent_service = AgentService(ap)
    try:
        yield ap
    finally:
        reset_persistent_state_store()
        await engine.dispose()


def install_descriptor(ap, workspace='workspace-a', field_name='prompt', schema=True):
    descriptor = RunnerDescriptor(
        id=RUNNER_ID,
        source='plugin',
        label={'en_US': 'LocalAgent'},
        plugin_author='langbot-team',
        plugin_name='LocalAgent',
        runner_name='default',
        usages=['agent'],
        config_schema=[{'name': field_name, 'type': 'prompt-editor', 'default': copy.deepcopy(DEFAULT_PROMPT)}]
        if schema
        else [],
    )
    ap.runner_registry.descriptors[(workspace, RUNNER_ID)] = descriptor
    return descriptor


async def create_agent(ap, context, params):
    config = {
        'runner': {'id': RUNNER_ID},
        'runner_config': {
            RUNNER_ID: copy.deepcopy(params),
            'plugin:other/Runner/default': {'prompt': [{'role': 'system', 'content': 'WRONG RUNNER'}]},
        },
        'allowed_tools': [],
        'allowed_platform_tools': [],
    }
    created = await ap.agent_service.create_agent(context, {'name': 'Prompt regression', 'config': config})
    saved = await ap.agent_service.get_agent(context, created['uuid'])
    assert saved['config'] == config
    return created['uuid'], config


@pytest.mark.parametrize(
    ('field_name', 'params', 'schema', 'expected'),
    [
        pytest.param(
            'prompt',
            {
                'prompt': STORED_PROMPT,
                'mcp-resources': [{'server_name': 'docs', 'uri': 'test://docs', 'enabled': False}],
                'mcp-resource-agent-read-enabled': False,
            },
            True,
            STORED_PROMPT,
            id='stored-localagent-prompt',
        ),
        pytest.param(
            'instructions',
            {'instructions': STORED_PROMPT, 'prompt': DEFAULT_PROMPT},
            True,
            STORED_PROMPT,
            id='schema-selected-field',
        ),
        pytest.param('prompt', {}, True, DEFAULT_PROMPT, id='schema-default'),
        pytest.param('prompt', {'prompt': []}, True, [], id='explicit-empty'),
        pytest.param('prompt', {'prompt': STORED_PROMPT}, False, [], id='no-prompt-editor'),
    ],
)
async def test_debug_prompt_pull_uses_stored_selected_runner_config(harness, field_name, params, schema, expected):
    ap = harness
    install_descriptor(ap, field_name=field_name, schema=schema)
    context = request_context()
    agent_id, config = await create_agent(ap, context, params)
    result = await ap.agent_service.debug_agent(
        context,
        agent_id,
        {
            'text': 'Return your configured workspace marker.',
            'conversation_id': 'same-conversation',
        },
    )
    ctx, query, pulled = ap.plugin_connector.observations[-1]
    assert ctx.context.available_apis.prompt_get is True
    assert ctx.config == params
    assert query.instance_uuid == context.instance_uuid
    assert query.workspace_uuid == context.workspace_uuid
    assert query.placement_generation == context.placement_generation
    assert query.query_uuid == result['event_id']
    assert query.variables['_pipeline_mcp_resource_attachments'] == params.get('mcp-resources', [])
    assert query.variables['_pipeline_mcp_resource_agent_read_enabled'] is params.get(
        'mcp-resource-agent-read-enabled', True
    )
    assert pulled == [Message(**message).model_dump(mode='json') for message in expected]
    assert result['execution_events'][-1]['type'] == 'run.completed'
    assert (await ap.agent_service.get_agent(context, agent_id))['config'] == config


async def test_debug_prompt_is_scoped_to_workspace_and_agent(harness):
    ap = harness
    for workspace, field in [('workspace-a', 'prompt'), ('workspace-b', 'instructions')]:
        install_descriptor(ap, workspace, field)
        context = request_context(workspace)
        for agent_name in ['first', 'second']:
            prompt = [{'role': 'system', 'content': f'{workspace}/{agent_name}'}]
            agent_id, _ = await create_agent(ap, context, {field: prompt})
            await ap.agent_service.debug_agent(
                context,
                agent_id,
                {
                    'text': 'Return your configured workspace marker.',
                    'conversation_id': 'same-conversation',
                    'actor': {'actor_type': 'user', 'actor_id': 'same-actor'},
                },
            )
            ctx, query, pulled = ap.plugin_connector.observations[-1]
            assert ctx.conversation.workspace_id == workspace
            assert query.workspace_uuid == workspace
            assert pulled == [Message(**message).model_dump(mode='json') for message in prompt]
    assert {workspace for workspace, _ in ap.runner_registry.calls} == {'workspace-a', 'workspace-b'}


@pytest.mark.parametrize('query_backed', [True, False], ids=['query-backed', 'event-only'])
@pytest.mark.parametrize('effective', [STORED_PROMPT, []], ids=['preprocessed', 'explicit-empty'])
async def test_non_debug_query_keeps_effective_prompt_instead_of_static_config(harness, effective, query_backed):
    ap = harness
    install_descriptor(ap)
    event = AgentEventEnvelope(
        event_id='platform-event',
        event_type='message.received',
        source='platform',
        workspace_id='workspace-a',
        conversation_id='same-conversation',
        input={'text': 'hello'},
        delivery={'surface': 'test'},
    )
    query = build_execution_query(event, [])
    query.prompt = Prompt(name='preprocessed', messages=[Message(**message) for message in effective])
    original = query.prompt
    binding = AgentBinding(
        binding_id='pipeline-binding',
        scope=BindingScope(scope_type='agent', scope_id='pipeline-test'),
        runner_id=RUNNER_ID,
        runner_config={'prompt': DEFAULT_PROMPT},
        processor_type='pipeline',
        processor_id='pipeline-test',
    )
    outputs = [
        output
        async for output in ap.agent_run_orchestrator.run(
            event,
            binding,
            adapter_context={
                **({'_query': query} if query_backed else {}),
                '_execution_context': ExecutionContext.from_request(request_context()),
            },
        )
    ]
    assert outputs == []
    _, observed_query, pulled = ap.plugin_connector.observations[-1]
    if query_backed:
        assert observed_query is query
        assert query.prompt is original
        assert pulled == [message.model_dump(mode='json') for message in original.messages]
    else:
        assert pulled == [Message(**message).model_dump(mode='json') for message in DEFAULT_PROMPT]
