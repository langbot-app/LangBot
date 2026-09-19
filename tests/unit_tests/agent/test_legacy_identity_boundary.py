"""Native identity provenance across the Host/SDK and persisted resume boundary."""

import ast
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
from langbot.pkg.agent.runner.context_builder import RunnerContextBuilder
from langbot.pkg.agent.runner.host_models import AgentEventEnvelope
from langbot.pkg.agent.runner.interaction_manager import InteractionManager
from langbot.pkg.agent.runner.interaction_store import InteractionStore
from langbot.pkg.entity.persistence.base import Base
from sqlalchemy.ext.asyncio import create_async_engine
from tests.unit_tests.agent import test_event_first_protocol as event_fixtures
from tests.unit_tests.agent.test_context_validation import TestContextValidation as Helpers


@pytest.fixture
def mock_query():
    return event_fixtures.mock_query.__wrapped__()


async def build(event, runner, source='legacy-session'):
    helper = Helpers()
    binding = helper._make_binding()
    binding.runner_id = f'plugin:langbot-team/{runner}/default'
    binding.processor_type = 'pipeline'
    binding.processor_id = 'pipeline-uuid-456'
    binding.runner_config = {'user-id-source': source}
    builder = RunnerContextBuilder(helper._make_mock_app())
    builder._build_context_access = AsyncMock(return_value={})
    with patch('langbot.pkg.agent.runner.context_builder.get_persistent_state_store') as store:
        store.return_value.build_snapshot_from_event = AsyncMock(return_value={})
        context = await builder.build_context_from_event(
            event, binding, helper._make_descriptor(), helper._make_resources()
        )
    return context, binding


@pytest.mark.asyncio
@pytest.mark.parametrize('runner', ['DifyAgent', 'N8nAgent', 'CozeAgent'])
@pytest.mark.parametrize('kind', ['group', 'person'])
async def test_exact_native_identity_survives_serialization(mock_query, runner, kind):
    mock_query.launcher_type.value = kind
    mock_query.launcher_id = ' Event_007 '
    mock_query.session.launcher_type.value = 'person' if kind == 'group' else 'group'
    mock_query.session.launcher_id = ' Session_008 '
    event = AgentEventEnvelope.model_validate_json(QueryEntryAdapter.query_to_event(mock_query).model_dump_json())
    context, _ = await build(event, runner)
    expected = (
        (kind, ' Event_007 ') if runner == 'CozeAgent' else (mock_query.session.launcher_type.value, ' Session_008 ')
    )
    assert (context['conversation']['launcher_type'], context['conversation']['launcher_id']) == expected
    assert context['actor']['actor_id'] == 'sender-123'
    assert context['conversation']['sender_id'] == 'sender-123'


@pytest.mark.asyncio
@pytest.mark.parametrize('runner', ['DifyAgent', 'N8nAgent', 'CozeAgent'])
async def test_missing_authoritative_fields_never_fall_back_to_raw_data(mock_query, runner):
    mock_query.session.launcher_id = None
    mock_query.launcher_id = None
    mock_query.variables.update({'launcher_id': 'spoof', 'session_id': 'group_spoof'})
    event = QueryEntryAdapter.query_to_event(mock_query)
    event.data.update({'launcher_type': 'group', 'launcher_id': 'spoof'})
    context, _ = await build(event, runner)
    assert context['conversation']['launcher_id'] is None


@pytest.mark.asyncio
async def test_tbox_and_sender_defaults_unchanged(mock_query):
    event = QueryEntryAdapter.query_to_event(mock_query)
    context, _ = await build(event, 'TboxAgent', 'legacy-bot')
    assert context['conversation']['bot_id'] == mock_query.bot_uuid
    context, _ = await build(event, 'DifyAgent', 'sender')
    assert context['actor']['actor_id'] == 'sender-123'
    assert context['conversation']['launcher_id'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('field', ['workspace_id', 'bot_id'])
async def test_provenance_cannot_cross_scope(mock_query, field):
    event = QueryEntryAdapter.query_to_event(mock_query)
    setattr(event, field, 'different')
    context, _ = await build(event, 'DifyAgent')
    assert context['conversation']['launcher_id'] is None


@pytest.mark.asyncio
async def test_provenance_cannot_cross_pipeline(mock_query):
    event = QueryEntryAdapter.query_to_event(mock_query)
    event.legacy_identity.pipeline_id = 'other-pipeline'
    context, _ = await build(event, 'DifyAgent')
    assert context['conversation']['launcher_id'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', [None, 'workspace_id', 'bot_id', 'processor_id', 'actor_id'])
async def test_resume_uses_persisted_identity_not_new_session(tmp_path, mock_query, changed):
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    try:
        store = InteractionStore(engine)
        event = QueryEntryAdapter.query_to_event(mock_query)
        context, binding = await build(event, 'DifyAgent')
        manager = InteractionManager(SimpleNamespace(), store)
        descriptor = Helpers()._make_descriptor()
        descriptor.id = binding.runner_id
        descriptor.capabilities.interactions = True
        descriptor.permissions.interactions = ['request']
        binding.delivery_policy.enable_interactions = True
        import sqlalchemy as sa
        from langbot.pkg.entity.persistence.pipeline import LegacyPipeline

        config = {
            'ai': {'runner': {'id': binding.runner_id}, 'runner_config': {binding.runner_id: binding.runner_config}}
        }
        mock_query.pipeline_config = config
        conversation = mock_query.session.using_conversation
        async with engine.begin() as conn:
            await conn.execute(
                sa.insert(LegacyPipeline).values(
                    uuid=binding.processor_id,
                    workspace_uuid=event.workspace_id,
                    name='test',
                    description='',
                    for_version='4.11',
                    stages=[],
                    config=config,
                    extensions_preferences={},
                )
            )
        adapter = SimpleNamespace(
            get_supported_apis=lambda: ['interaction.request'], call_platform_api=AsyncMock(return_value={})
        )
        mock_query.adapter = adapter
        await manager.handle_result(
            result_dict={
                'data': {
                    'action': 'interaction.requested',
                    'payload': {'interaction_id': 'form', 'title': 'Approve', 'fallback_text': 'Approve'},
                }
            },
            event=event,
            binding=binding,
            descriptor=descriptor,
            run_id='original',
            adapter_context={
                '_delivery_adapter': adapter,
                '_query': mock_query,
                '_pipeline_expected_config': config,
                '_pipeline_conversation': conversation,
            },
        )
        token = adapter.call_platform_api.call_args.args[1]['callback_token']
        record = await manager.consume_callback(
            callback_token=token,
            submission={'interaction_id': 'form', 'values': {}},
            bot_id=event.bot_id,
            conversation_id='person_launcher-123',
            actor_id='sender-123',
        )
        mock_query.variables['_interaction_submission'] = record['submission']
        mock_query.session.launcher_id = 'wrong-new-session'
        resumed = QueryEntryAdapter.query_to_event(mock_query)
        if changed in ('workspace_id', 'bot_id'):
            setattr(resumed, changed, 'other')
        elif changed == 'processor_id':
            binding.processor_id = 'other'
        elif changed == 'actor_id':
            resumed.actor.actor_id = 'other'
        # A fresh manager/store represents a process restart, not an in-memory cache.
        manager = InteractionManager(SimpleNamespace(), InteractionStore(engine))
        await manager.restore_legacy_identity(resumed, binding)
        result, _ = await build(resumed, 'DifyAgent')
        assert result['conversation']['launcher_id'] == (None if changed else 'launcher-123')
    finally:
        await engine.dispose()


@pytest.mark.asyncio
async def test_tbox_resume_without_persisted_identity_fails_closed(mock_query):
    event = QueryEntryAdapter.query_to_event(mock_query)
    event.event_type = 'interaction.submitted'
    event.legacy_identity = None
    context, _ = await build(event, 'TboxAgent', 'legacy-bot')
    assert context['conversation']['bot_id'] is None
    assert context['runtime']['metadata']['bot_id'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'runner,folder,method',
    [
        ('DifyAgent', 'dify-agent', '_get_user_tag'),
        ('N8nAgent', 'n8n-agent', '_get_user_tag'),
        ('CozeAgent', 'coze-agent', '_get_user_id'),
        ('TboxAgent', 'tbox-agent', '_get_user_id'),
    ],
)
@pytest.mark.parametrize('missing', [False, True])
async def test_real_plugin_identity_helper_with_host_payload(mock_query, runner, folder, method, missing):
    # Execute the actual pure helper AST without loading vendor clients or making network calls.
    root = Path(__file__).resolve().parents[3].parent / 'langbot-plugins-411-migration'
    path = root / 'Runner' / folder / 'components/runner/default.py'
    if not path.exists():
        pytest.skip('sibling plugin source checkout is required for cross-repository contract gate')
    tree = ast.parse(path.read_text())
    function = next(node for node in ast.walk(tree) if isinstance(node, ast.FunctionDef) and node.name == method)

    class ConfigError(Exception):
        def __init__(self, message, **kwargs):
            super().__init__(message)

    namespace = {
        'RunnerContext': RunnerContext,
        **{name: ConfigError for name in ('DifyConfigError', 'N8nConfigError', 'CozeConfigError', 'TboxConfigError')},
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(path), 'exec'), namespace)
    mock_query.session.launcher_id = 'Session_007'
    event = QueryEntryAdapter.query_to_event(mock_query)
    if missing:
        event.legacy_identity = None
        event.bot_id = None
    source = 'legacy-bot' if runner == 'TboxAgent' else 'legacy-session'
    context, _ = await build(event, runner, source)
    sdk = RunnerContext.model_validate(context)
    if missing:
        with pytest.raises(ConfigError, match='trusted Host identity'):
            namespace[method](None, sdk)
    else:
        expected = (
            mock_query.bot_uuid
            if runner == 'TboxAgent'
            else ('person_launcher-123' if runner == 'CozeAgent' else 'person_Session_007')
        )
        assert namespace[method](None, sdk) == expected
