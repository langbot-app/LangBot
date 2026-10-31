"""Native identity provenance across the Host/SDK and persisted resume boundary."""

import hashlib
import json
from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from langbot_plugin.api.entities.builtin.runner.context import RunnerContext
from langbot_plugin.api.proxies.invocation import bind_invocation
from langbot_plugin.entities.io.context import InstallationBinding
from langbot.pkg.agent.runner.query_entry_adapter import QueryEntryAdapter
from langbot.pkg.agent.runner.context_builder import RunnerContextBuilder
from langbot.pkg.agent.runner.host_models import AgentEventEnvelope
from tests.unit_tests.agent import test_event_first_protocol as event_fixtures
from tests.unit_tests.agent.test_context_validation import TestContextValidation as Helpers
from tests.utils.legacy_plugin_contract import load_identity_helper, verified_plugin_root


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
@pytest.fixture(scope='session')
def official_plugin_root():
    return verified_plugin_root()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'runner,folder,method,error_name,local_identity',
    [
        pytest.param(
            'DifyAgent',
            'dify-agent',
            '_get_user_tag',
            'DifyConfigError',
            'person_Session_007',
            marks=pytest.mark.contract('dify_identity'),
        ),
        pytest.param(
            'N8nAgent',
            'n8n-agent',
            '_get_user_tag',
            'N8nConfigError',
            'person_Session_007',
            marks=pytest.mark.contract('n8n_identity'),
        ),
        pytest.param(
            'CozeAgent',
            'coze-agent',
            '_get_user_id',
            'CozeConfigError',
            'person_launcher-123',
            marks=pytest.mark.contract('coze_identity'),
        ),
        pytest.param(
            'TboxAgent',
            'tbox-agent',
            '_get_user_id',
            'TboxConfigError',
            'bot-uuid-123',
            marks=pytest.mark.contract('tbox_identity'),
        ),
    ],
)
@pytest.mark.parametrize('missing', [False, True], ids=['trusted-identity', 'missing-identity'])
@pytest.mark.parametrize('profile', ['dedicated', 'shared'])
@pytest.mark.plugin_identity
async def test_real_plugin_identity_helper_with_host_payload(
    mock_query, monkeypatch, official_plugin_root, runner, folder, method, error_name, local_identity, missing, profile
):
    # Keep exact Host identity selection above; current supported plugins namespace
    # that identity to prevent collisions across Workspaces and installations.
    helper, config_error = load_identity_helper(official_plugin_root, folder, method, error_name)
    monkeypatch.setenv('LANGBOT_PLUGIN_RUNTIME_PROFILE', profile)
    mock_query.session.launcher_id = 'Session_007'
    event = QueryEntryAdapter.query_to_event(mock_query)
    if missing:
        event.legacy_identity = None
        event.bot_id = None
    source = 'legacy-bot' if runner == 'TboxAgent' else 'legacy-session'
    context, _ = await build(event, runner, source)
    sdk = RunnerContext.model_validate(context)
    handler = SimpleNamespace()
    consumer = SimpleNamespace(_plugin_runtime_handler=handler)
    binding = InstallationBinding(
        instance_uuid='identity-instance',
        workspace_uuid=event.workspace_id,
        installation_uuid='00000000-0000-4000-8000-000000000007',
        runtime_revision=1,
        artifact_digest='a' * 64,
    )
    if profile == 'shared':
        # A stale connection binding must never win over the active invocation.
        handler.bound_action_context = binding.model_copy(
            update={'workspace_uuid': 'foreign-workspace', 'installation_uuid': 'foreign-installation'}
        )
    authority = bind_invocation(handler, binding=binding) if profile == 'shared' else nullcontext()
    with authority:
        if missing:
            with pytest.raises(config_error, match='trusted Host identity') as caught:
                helper(consumer, sdk)
            assert caught.value.code == f'{folder.removesuffix("-agent")}.identity_unavailable'
        else:
            # The expected local IDs above are independent of the actual Host
            # payload and plugin output, preserving session-vs-event provenance.
            scope = (
                ['identity-instance', event.workspace_id, '00000000-0000-4000-8000-000000000007']
                if profile == 'shared'
                else [event.workspace_id]
            )
            encoded = json.dumps([scope, local_identity], ensure_ascii=False, separators=(',', ':')).encode()
            expected = 'lb_' + hashlib.sha256(encoded).hexdigest()
            assert helper(consumer, sdk) == expected
