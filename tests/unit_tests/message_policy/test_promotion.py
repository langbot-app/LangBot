import pytest

from langbot.pkg.message_policy.promotion import policy_promotion


GROUP = {'trigger': {'group-respond-rules': {'enabled': True, 'at': True}}}


@pytest.mark.parametrize('target', ['pipeline', 'agent', 'event_processor', 'discard'])
@pytest.mark.parametrize('pattern', ['message.received', 'message.*', '*'])
def test_inherited_policy_on_disabled_message_route_prevents_promotion(target, pattern):
    bindings = [
        {'id': 'chat', 'event_pattern': 'message.received', 'policy': GROUP},
        {'id': 'other', 'event_pattern': pattern, 'target_type': target, 'enabled': False},
    ]
    assert policy_promotion('bot', {}, bindings) is None


def test_equivalent_partial_overrides_and_unrelated_events():
    bindings = [
        {'id': 'chat', 'event_pattern': '*', 'policy': GROUP},
        {
            'id': 'agent',
            'event_pattern': 'message.received',
            'policy': {'trigger': {'group-respond-rules': {'at': True}}},
        },
        {'id': 'joined', 'event_pattern': 'group.member.joined'},
    ]
    params = policy_promotion('bot', {'trigger': {'group-respond-rules': {'enabled': True}}}, bindings)
    assert params['route_ids'] == ['chat', 'agent']
    assert params['changes_unrouted_commands']
    assert params['message_policy']['trigger']['group-respond-rules']['enabled']
    bindings[1]['policy']['plugins'] = {'enable_all': False, 'plugins': []}
    assert policy_promotion('bot', GROUP, bindings) is None


def test_aggregation_is_not_used_by_commands():
    params = policy_promotion(
        'bot',
        {},
        [{'id': 'chat', 'event_pattern': '*', 'policy': {'trigger': {'message-aggregation': {'enabled': True}}}}],
    )
    assert not params['changes_unrouted_commands']
