from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from langbot_plugin.api.entities.builtin.agent_runner import (
    ActorContext,
    AgentInput,
    DeliveryContext,
    RawEventRef,
    SubjectContext,
)
from langbot_plugin.api.entities.builtin.platform import message as platform_message
from langbot_plugin.api.entities.builtin.platform import entities as platform_entities
from langbot_plugin.api.entities.builtin.platform import events as platform_events

from langbot.pkg.agent.runner.host_models import AgentEventEnvelope
from langbot.pkg.agent.runner.platform_tools import (
    PLATFORM_TOOL_DEFINITIONS,
    build_platform_tool_resources,
    execute_platform_tool,
    freeze_platform_context,
    resolve_agent_platform_tool_names,
    validate_debug_mock_options,
)


@pytest.mark.asyncio
@pytest.mark.parametrize('definition', PLATFORM_TOOL_DEFINITIONS, ids=lambda tool: tool.name)
@pytest.mark.parametrize('failure', [False, True])
async def test_every_platform_tool_mock_preserves_validation_and_never_calls_bot(definition, failure):
    pattern = definition.event_patterns[0]
    event_type = 'group.member_joined' if pattern == '*' else pattern.replace('*', 'received')
    event = _event(event_type)
    event.delivery.surface = 'webui'
    event.delivery.platform_capabilities = {
        'debug_mock': True,
        'supported_apis': [definition.api],
        'mock_options': {'errors': {definition.name: 'E2E denied'}} if failure else {},
    }
    resources, capabilities = build_platform_tool_resources(event, [definition.name], ['call'])
    assert capabilities['unavailable_tools'] == []
    assert len(resources) == 1
    parameters = {}
    for name in definition.parameters.get('required', []):
        schema = definition.parameters['properties'][name]
        parameters[name] = schema.get(
            'enum', [False if schema['type'] == 'boolean' else 30 if schema['type'] == 'integer' else 'fixture-' + name]
        )[0]
    ap = SimpleNamespace(
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(side_effect=AssertionError('real adapter accessed')))
    )
    session = {'authorization': {'resources': {'tools': resources}, 'platform_context': freeze_platform_context(event)}}
    result = await execute_platform_tool(ap, object(), session, definition.name, parameters)
    assert result['mock'] is True
    assert result['ok'] is not failure
    assert result['api'] == definition.api
    if failure:
        assert result['error'] == 'E2E denied'
    else:
        schemas = {
            'get_user_info': platform_entities.User,
            'get_group_info': platform_entities.UserGroup,
            'get_group_member_info': platform_entities.UserGroupMember,
            'get_message': platform_events.MessageReceivedEvent,
            'get_friend_list': platform_entities.User,
            'get_group_list': platform_entities.UserGroup,
            'get_group_member_list': platform_entities.UserGroupMember,
        }
        if definition.api in schemas:
            items = result['result'] if isinstance(result['result'], list) else [result['result']]
            for item in items:
                schemas[definition.api].model_validate(item)
    ap.platform_mgr.get_bot_by_uuid.assert_not_awaited()
    with pytest.raises(ValueError):
        await execute_platform_tool(ap, object(), session, definition.name, {**parameters, 'forged_target': 'other'})


@pytest.mark.parametrize(
    'options',
    [
        None,
        [],
        {'unexpected': True},
        {'errors': []},
        {'errors': {'exec': 'oops'}},
        {'errors': {'event_reply': ''}},
        {'results': {'missing': {}}},
        {'errors': {'event_reply': 'oops'}, 'results': {'event_reply': {}}},
        {'unsupported_apis': 'send_message'},
        {'unsupported_apis': ['unknown']},
    ],
)
def test_invalid_mock_options_are_rejected(options):
    with pytest.raises(ValueError):
        validate_debug_mock_options(options)


@pytest.mark.asyncio
async def test_mock_fixture_does_not_mutate_options():
    event = _event()
    fixture = {'name': 'Fixture User', 'nested': {'value': 42}}
    event.delivery.surface = 'webui'
    event.delivery.platform_capabilities = {
        'debug_mock': True,
        'mock_options': {'results': {'event_get_actor': fixture}},
    }
    session = {'authorization': {'platform_context': freeze_platform_context(event)}}
    result = await execute_platform_tool(SimpleNamespace(), object(), session, 'event_get_actor', {})
    assert result['result'] == fixture
    result['result']['nested']['value'] = 100
    assert fixture['nested']['value'] == 42


def _event(event_type: str = 'friend.request_received') -> AgentEventEnvelope:
    return AgentEventEnvelope(
        event_id='event-1',
        event_type=event_type,
        source='platform',
        bot_id='bot-1',
        input=AgentInput(text='event'),
        actor=ActorContext(actor_type='user', actor_id='user-1'),
        subject=SubjectContext(subject_type='group', subject_id='group-1'),
        delivery=DeliveryContext(
            surface='platform',
            reply_target={
                'target_type': 'group',
                'target_id': 'group-1',
                'group_id': 'group-1',
                'message_id': 'message-1',
            },
            platform_capabilities={
                'adapter': 'FakeAdapter',
                'supported_apis': [
                    'send_message',
                    'approve_friend_request',
                    'get_group_info',
                ],
            },
        ),
        raw_ref=RawEventRef(ref_id='request-fallback'),
        data={'request_id': 'request-1'},
    )


def test_platform_resources_intersect_selection_adapter_and_event() -> None:
    resources, capabilities = build_platform_tool_resources(
        _event(),
        [
            'event_reply',
            'event_respond_friend_request',
            'event_kick_member',
            'platform_get_group_info',
            'unknown_tool',
        ],
        ['detail', 'call'],
    )

    assert {item['tool_name'] for item in resources} == {
        'event_reply',
        'event_respond_friend_request',
        'platform_get_group_info',
    }
    assert all(item['source'] == 'platform' for item in resources)
    assert capabilities['authorized_tools'] == [item['tool_name'] for item in resources]
    assert {item['reason'] for item in capabilities['unavailable_tools']} == {
        'adapter_api_unsupported',
        'unknown_tool',
    }


def test_platform_resources_require_runner_call_permission() -> None:
    resources, capabilities = build_platform_tool_resources(
        _event(),
        ['event_reply'],
        ['detail'],
    )

    assert resources == []
    assert capabilities['unavailable_tools'] == [{'name': 'event_reply', 'reason': 'runner_call_permission_missing'}]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('name', 'params', 'api'),
    [
        ('event_reply', {'text': 'Hello'}, 'send_message'),
        ('event_get_actor', {}, 'get_user_info'),
        ('event_get_group', {}, 'get_group_info'),
        ('event_respond_friend_request', {'approve': False}, 'approve_friend_request'),
        (
            'platform_send_message',
            {'target_type': 'group', 'target_id': 'explicit-group', 'text': 'Hi'},
            'send_message',
        ),
    ],
)
async def test_debug_mock_executes_without_accessing_a_real_adapter(name, params, api):
    event = _event()
    event.delivery.surface = 'webui'
    event.delivery.platform_capabilities['debug_mock'] = True
    ap = SimpleNamespace(platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock()))
    session = {'authorization': {'platform_context': freeze_platform_context(event)}}
    result = await execute_platform_tool(ap, object(), session, name, params)
    assert result['mock'] is True and result['ok'] is True
    assert result['delivery'] == 'simulated'
    assert result['api'] == api
    if name == 'event_reply':
        assert result['parameters'] == {'target_type': 'group', 'target_id': 'group-1', 'text': 'Hello'}
    if name == 'platform_send_message':
        assert result['parameters']['target_id'] == 'explicit-group'
    ap.platform_mgr.get_bot_by_uuid.assert_not_awaited()
    with pytest.raises(ValueError):
        await execute_platform_tool(ap, object(), session, name, {**params, 'unexpected': True})


def test_agent_platform_tools_are_resolved_for_the_current_event() -> None:
    selected = resolve_agent_platform_tool_names(
        {
            'allowed_platform_tools': ['platform_get_user_info', 'event_reply'],
            'event_tool_permissions': {
                'message.*': ['event_reply'],
                'group.member.joined': ['event_get_actor'],
                'group.*': ['event_get_group', 'unknown_tool'],
            },
        },
        'group.member.joined',
    )

    assert selected == [
        'platform_get_user_info',
        'event_reply',
        'event_get_actor',
        'event_get_group',
        'event_get_group_member',
    ]


def test_agent_event_tools_are_automatic_without_permission_configuration() -> None:
    assert resolve_agent_platform_tool_names(
        {'allowed_platform_tools': ['event_reply', 'platform_get_user_info']},
        'friend.request_received',
    ) == [
        'platform_get_user_info',
        'event_reply',
        'event_get_actor',
        'event_respond_friend_request',
    ]


def test_request_action_does_not_treat_host_event_ref_as_platform_request_id() -> None:
    event = _event()
    event.data = {}

    resources, capabilities = build_platform_tool_resources(
        event,
        ['event_respond_friend_request'],
        ['detail', 'call'],
    )

    assert resources == []
    assert capabilities['unavailable_tools'] == [
        {'name': 'event_respond_friend_request', 'reason': 'event_target_unavailable'}
    ]


@pytest.mark.asyncio
async def test_event_action_execution_uses_frozen_target_and_current_bot() -> None:
    adapter = SimpleNamespace(
        get_supported_apis=lambda: ['approve_friend_request'],
        approve_friend_request=AsyncMock(return_value=None),
    )
    platform_mgr = SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=SimpleNamespace(adapter=adapter)))
    ap = SimpleNamespace(platform_mgr=platform_mgr)
    event = _event()
    session = {
        'authorization': {
            'bot_id': 'bot-1',
            'platform_context': freeze_platform_context(event),
        }
    }
    execution_context = object()

    await execute_platform_tool(
        ap,
        execution_context,
        session,
        'event_respond_friend_request',
        {'approve': False, 'remark': 'not now'},
    )

    platform_mgr.get_bot_by_uuid.assert_awaited_once_with(execution_context, 'bot-1')
    adapter.approve_friend_request.assert_awaited_once_with(
        request_id='request-1',
        approve=False,
        remark='not now',
    )


@pytest.mark.asyncio
async def test_event_reply_builds_message_chain_for_the_frozen_target() -> None:
    adapter = SimpleNamespace(
        get_supported_apis=lambda: ['send_message'],
        send_message=AsyncMock(return_value=None),
    )
    ap = SimpleNamespace(
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=SimpleNamespace(adapter=adapter)))
    )
    session = {
        'authorization': {
            'bot_id': 'bot-1',
            'platform_context': freeze_platform_context(_event()),
        }
    }

    await execute_platform_tool(ap, object(), session, 'event_reply', {'text': 'hello'})

    call = adapter.send_message.await_args
    assert call.kwargs['target_type'] == 'group'
    assert call.kwargs['target_id'] == 'group-1'
    assert isinstance(call.kwargs['message'], platform_message.MessageChain)
    assert call.kwargs['message'][0].text == 'hello'


@pytest.mark.asyncio
async def test_platform_action_rejects_parameters_outside_the_declared_schema() -> None:
    adapter = SimpleNamespace(
        get_supported_apis=lambda: ['get_group_info'],
        get_group_info=AsyncMock(),
    )
    ap = SimpleNamespace(
        platform_mgr=SimpleNamespace(get_bot_by_uuid=AsyncMock(return_value=SimpleNamespace(adapter=adapter)))
    )
    session = {'authorization': {'bot_id': 'bot-1', 'platform_context': {}}}

    with pytest.raises(ValueError, match='Unexpected parameters'):
        await execute_platform_tool(
            ap,
            object(),
            session,
            'platform_get_group_info',
            {'group_id': 'group-1', 'raw_action': 'unsafe'},
        )

    adapter.get_group_info.assert_not_awaited()
