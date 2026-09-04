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

from langbot.pkg.agent.runner.host_models import AgentEventEnvelope
from langbot.pkg.agent.runner.platform_tools import (
    build_platform_tool_resources,
    execute_platform_tool,
    freeze_platform_context,
    resolve_agent_platform_tool_names,
)


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
