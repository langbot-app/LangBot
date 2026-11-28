"""Bot message policy and route policy overrides in BotService."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.service.bot import BotService
from langbot.pkg.message_policy import schema

WORKSPACE = 'workspace'


async def test_dry_run_reports_live_policy_item_without_charging_rate_limit():
    from langbot.pkg.api.http.context import ExecutionContext
    from langbot.pkg.message_policy.manager import MessagePolicyManager
    from tests.factories import FakeApp, text_query

    context = ExecutionContext(instance_uuid='inst', workspace_uuid=WORKSPACE, placement_generation=1)
    app = FakeApp()
    app.message_policy_mgr = MessagePolicyManager(app)
    service = BotService(app)
    policy = {'safety': {'rate-limit': {'enabled': True, 'window-length': 3600, 'limitation': 1}}}
    binding = {
        'target_type': 'agent',
        'id': 'first',
        'target_uuid': 'agent',
        'event_pattern': 'message.received',
        'policy': policy,
    }
    bot = {'event_bindings': [binding]}
    service.get_bot = AsyncMock(return_value=bot)
    sample = {'chat_id': 'person-1', 'message_text': 'hello', 'user_id': 'person-1'}
    assert await service._preview_message_policy(context, 'bot', bot, binding, sample) == (None, None)
    runtime = await app.message_policy_mgr.compile(policy, bot_uuid='bot')
    query = text_query('hello', sender_id='person-1', pipeline_uuid=None, bot_uuid='bot')
    object.__setattr__(query, '_execution_context', context)
    runtime.attach(query)
    async with runtime.admit(query) as item:
        assert item is None
    result = await service.dry_run_event_route(context, 'bot', 'message.received', sample)
    assert result['failure_code'] == 'message_policy'
    assert result['reason'] == 'route:first: safety.rate-limit'


async def test_registration_lists_processor_scope_for_each_hook():
    stored = {}
    service = make_service(stored_bot=stored)
    service.ap.plugin_connector = SimpleNamespace(
        require_workspace_context=AsyncMock(),
        list_plugin_registrations=AsyncMock(
            return_value={
                'a/b': {
                    'events': [
                        'PromptPreProcessing',
                        'GroupCommandSent',
                        'NormalMessageResponded',
                        'GroupMessageReceived',
                    ]
                }
            }
        ),
    )
    registrations = await service.get_plugin_registrations(WORKSPACE, 'bot')
    assert registrations['plugins']['a/b']['event_processors'] == {
        'PromptPreProcessing': ['messaging'],
        'GroupCommandSent': ['command'],
        'NormalMessageResponded': ['messaging', 'agent'],
        'GroupMessageReceived': ['messaging', 'agent', 'command'],
    }
    service.ap.plugin_connector.list_plugin_registrations.assert_awaited_with(None)

    stored['message_policy'] = {'plugins': {'enable_all': False, 'plugins': [{'author': 'a', 'name': 'b'}]}}
    await service.get_plugin_registrations(WORKSPACE, 'bot')
    service.ap.plugin_connector.list_plugin_registrations.assert_awaited_with(['a/b'])
    await service.get_plugin_registrations(WORKSPACE, 'bot', include_disabled=True)
    service.ap.plugin_connector.list_plugin_registrations.assert_awaited_with(None)


def make_service(*, stored_bot=None, runtime_bot=None):
    """A BotService whose Messaging targets all exist."""
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={}),
        persistence_mgr=SimpleNamespace(
            execute_async=AsyncMock(return_value=Mock(first=Mock(return_value=('found',)), rowcount=1))
        ),
        platform_mgr=SimpleNamespace(
            get_bot_by_uuid=AsyncMock(return_value=runtime_bot),
            remove_bot=AsyncMock(),
            load_bot=AsyncMock(return_value=SimpleNamespace(enable=False, run=AsyncMock())),
        ),
        pipeline_service=SimpleNamespace(get_pipelines=AsyncMock(), create_pipeline=AsyncMock()),
        message_policy_mgr=Mock(),
        sess_mgr=SimpleNamespace(session_list=[]),
    )
    service = BotService(ap)
    service.get_bot = AsyncMock(return_value=stored_bot)
    return service


def route(route_id=None, target_type='pipeline', **extra):
    binding = {
        'event_pattern': 'message.received',
        'target_type': target_type,
        'target_uuid': '' if target_type == 'discard' else 'processor',
    }
    if route_id:
        binding['id'] = route_id
    binding.update(extra)
    return binding


OVERRIDE = {'trigger': {'group-respond-rules': {'enabled': True, 'at': True, 'prefix': ['ai']}}}


def stored_values(service):
    statement = service.ap.persistence_mgr.execute_async.await_args_list[-1].args[0]
    return {column.key: value.value for column, value in statement._values.items()}


# ---------------------------------------------------------------- bot policy


@pytest.mark.asyncio
async def test_old_runtime_reports_unknown_plugin_registrations():
    from langbot.pkg.plugin.handler import RuntimeConnectionHandler
    from langbot_plugin.entities.io.errors import ActionCallError

    handler = SimpleNamespace(
        call_action=AsyncMock(side_effect=ActionCallError('ValueError: Action list_plugin_registrations not found'))
    )
    assert await RuntimeConnectionHandler.list_plugin_registrations(handler, ['author/plugin']) is None


@pytest.mark.asyncio
async def test_plugin_selection_survives_older_policy_updates():
    selection = {'enable_all': False, 'plugins': [{'author': 'owner', 'name': 'plugin'}]}
    stored = {'uuid': 'bot', 'message_policy': {'plugins': selection}}
    service = make_service(stored_bot=stored)
    await service.update_bot(WORKSPACE, 'bot', {'message_policy': OVERRIDE})
    assert stored_values(service)['message_policy']['plugins'] == selection
    await service.update_bot(WORKSPACE, 'bot', {'message_policy': {'plugins': None}})
    assert 'plugins' not in stored_values(service)['message_policy']


@pytest.mark.asyncio
async def test_a_partial_bot_policy_is_validated_and_stored_complete():
    service = make_service()

    prepared = await service._prepare_bot_data(
        WORKSPACE,
        {'message_policy': {'output': {'misc': {'at-sender': 'true'}}}},
        include_uuid=False,
    )

    policy = prepared['message_policy']
    assert policy['output']['misc']['at-sender'] is True
    # Everything not stated takes the neutral value, and nothing is missing.
    assert policy == schema.resolve_policy({'output': {'misc': {'at-sender': True}}})
    for section, blocks in schema.POLICY_SCHEMA.items():
        for block, keys in blocks.items():
            assert set(policy[section][block]) == set(keys)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('policy', 'message'),
    [
        ('strict', 'message_policy must be an object'),
        ({'ai': {}}, 'message_policy.ai is not a message policy section'),
        ({'safety': {'rate-limit': {'window-length': 0}}}, 'window-length must be at least 1'),
    ],
)
async def test_an_invalid_bot_policy_is_rejected(policy, message):
    service = make_service()

    with pytest.raises(ValueError, match=message):
        await service._prepare_bot_data(WORKSPACE, {'message_policy': policy}, include_uuid=False)


@pytest.mark.asyncio
async def test_a_new_bot_starts_with_the_default_policy_unless_one_is_given():
    service = make_service(stored_bot={'enable': False})
    base = {'name': 'Bot', 'adapter': 'onebot-v11', 'adapter_config': {}, 'event_bindings': [route('r1', 'discard')]}

    await service.create_bot(WORKSPACE, dict(base))
    assert stored_values(service)['message_policy'] == schema.default_policy()

    await service.create_bot(WORKSPACE, {**base, 'message_policy': {}})
    assert stored_values(service)['message_policy'] == schema.neutral_policy()


@pytest.mark.asyncio
async def test_a_policy_only_update_is_applied_in_place_without_restarting_the_adapter():
    runtime_bot = SimpleNamespace(bot_entity=SimpleNamespace(message_policy=schema.neutral_policy()))
    service = make_service(stored_bot={'uuid': 'bot'}, runtime_bot=runtime_bot)

    await service.update_bot(WORKSPACE, 'bot', {'message_policy': {'output': {'misc': {'quote-origin': True}}}})

    assert stored_values(service)['message_policy']['output']['misc']['quote-origin'] is True
    assert runtime_bot.bot_entity.message_policy['output']['misc']['quote-origin'] is True
    service.ap.message_policy_mgr.invalidate_bot.assert_called_once_with(WORKSPACE, 'bot')
    service.ap.platform_mgr.remove_bot.assert_not_awaited()
    service.ap.platform_mgr.load_bot.assert_not_awaited()


# ------------------------------------------------------------ route overrides


@pytest.mark.asyncio
async def test_a_route_may_carry_a_validated_partial_policy_override():
    service = make_service()

    bindings = await service._normalize_event_bindings(
        WORKSPACE,
        [
            route('r1', policy={'trigger': {'group-respond-rules': {'at': 'true', 'prefix': ['ai']}}}),
            route('r2'),
            route('r3', policy={}),
            route('r4', 'discard', policy=OVERRIDE),
        ],
    )

    by_id = {binding['id']: binding for binding in bindings}
    # Stored as written (partial), with form values coerced.
    assert by_id['r1']['policy'] == {'trigger': {'group-respond-rules': {'at': True, 'prefix': ['ai']}}}
    assert 'policy' not in by_id['r2']
    assert 'policy' not in by_id['r3'], 'an empty override is the same as none'
    assert 'policy' not in by_id['r4'], 'a discarded message has no policy to apply'


@pytest.mark.asyncio
async def test_an_invalid_route_override_names_the_route():
    service = make_service()

    with pytest.raises(ValueError, match=r'event_bindings\[1\]\.policy\.output\.misc\.remove-think is not'):
        await service._normalize_event_bindings(
            WORKSPACE,
            [route('r1'), route('r2', policy={'output': {'misc': {'remove-think': True}}})],
        )


@pytest.mark.asyncio
async def test_saving_routes_without_policy_keeps_stored_overrides():
    """A client that predates message policies must not strip them by saving routes."""
    service = make_service()
    current = [route('r1', policy=OVERRIDE), route('r2', policy=OVERRIDE), route('r3', policy=OVERRIDE)]

    bindings = await service._normalize_event_bindings(
        WORKSPACE,
        [
            route('r1', priority=7),  # edited, policy key absent -> kept
            route('r2', policy=None),  # explicit null -> removed
            route('r3', policy={'output': {'misc': {'at-sender': True}}}),  # replaced
            route('r-new'),  # new route -> bot default
            route(),  # no id at all -> new route
        ],
        current_bindings=current,
    )

    assert bindings[0]['policy'] == OVERRIDE and bindings[0]['priority'] == 7
    assert 'policy' not in bindings[1]
    assert bindings[2]['policy'] == {'output': {'misc': {'at-sender': True}}}
    assert 'policy' not in bindings[3]
    assert 'policy' not in bindings[4]


@pytest.mark.asyncio
async def test_update_bot_keeps_overrides_of_routes_resubmitted_without_them():
    stored = {'uuid': 'bot', 'enable': False, 'event_bindings': [route('r1', policy=OVERRIDE)]}
    service = make_service(stored_bot=stored)

    await service.update_bot(WORKSPACE, 'bot', {'event_bindings': [route('r1', enabled=False)]})

    update = service.ap.persistence_mgr.execute_async.await_args_list
    values = next(
        {column.key: value.value for column, value in call.args[0]._values.items()}
        for call in update
        if hasattr(call.args[0], '_values') and call.args[0]._values
    )
    assert values['event_bindings'][0]['policy'] == OVERRIDE
    assert values['event_bindings'][0]['enabled'] is False


# -------------------------------------------------- group filter migration helper


@pytest.mark.asyncio
async def test_group_filter_migration_reads_and_updates_the_route_policy():
    at_required = {'trigger': {'group-respond-rules': {'enabled': True, 'at': True, 'prefix': ['ai']}}}
    stored = {
        'uuid': 'bot',
        'enable': False,
        'message_policy': schema.neutral_policy(),
        'event_bindings': [
            route('r-at', policy=at_required),
            route('r-plain'),
            route(
                'r-filtered',
                policy=at_required,
                filters=[
                    {'field': 'chat_type', 'operator': 'eq', 'value': 'group'},
                    {'field': 'is_at_bot', 'operator': 'eq', 'value': True},
                ],
            ),
        ],
    }
    service = make_service(stored_bot=stored)

    preview = await service.preview_group_filter_migration(WORKSPACE, 'bot')

    assert preview['needs_migration'] is True
    assert [item['binding_id'] for item in preview['bindings_to_update']] == ['r-at']
    assert preview['bindings_already_filtered'] == ['r-filtered']
    assert preview['pipeline_flags']['processor']['at_bot_enabled'] is True

    service.update_bot = AsyncMock()
    result = await service.apply_group_filter_migration(WORKSPACE, 'bot')

    assert result['applied'] is True and result['updated_bindings'] == ['r-at']
    saved = {item['id']: item for item in service.update_bot.await_args.args[2]['event_bindings']}
    assert {'field': 'is_at_bot', 'operator': 'eq', 'value': True} in saved['r-at']['filters']
    # The route filter does the check now; the policy rule is off for that route only.
    assert saved['r-at']['policy']['trigger']['group-respond-rules'] == {'enabled': True, 'at': False, 'prefix': ['ai']}
    assert saved['r-filtered']['policy'] == at_required
    assert 'policy' not in saved['r-plain']
