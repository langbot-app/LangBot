"""Policy resolution and caching per bot and route."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.message_policy import manager as policy_manager
from langbot.pkg.message_policy import schema
from langbot.pkg.utils import constants
from tests.factories import FakeApp, text_query

CONTEXT = ExecutionContext(instance_uuid='instance', workspace_uuid='workspace', placement_generation=1)


def route(route_id, target='processor-a', *, policy=None, enabled=True, priority=0, target_type='pipeline'):
    binding = {
        'id': route_id,
        'event_pattern': 'message.received',
        'target_type': target_type,
        'target_uuid': target,
        'enabled': enabled,
        'priority': priority,
    }
    if policy is not None:
        binding['policy'] = policy
    return binding


def prefix_policy(prefix):
    return {'trigger': {'group-respond-rules': {'enabled': True, 'prefix': [prefix]}}}


def make_app(bots: dict[str, SimpleNamespace]):
    app = FakeApp()
    app.platform_mgr = SimpleNamespace(
        find_runtime_bot=lambda _context, bot_uuid: (
            SimpleNamespace(bot_entity=bots[bot_uuid]) if bot_uuid in bots else None
        )
    )
    app.message_policy_mgr = policy_manager.MessagePolicyManager(app)
    return app


def bot(bindings, policy=None):
    return SimpleNamespace(
        message_policy=policy if policy is not None else schema.neutral_policy(), event_bindings=bindings
    )


def prefixes(policy):
    return policy['trigger']['group-respond-rules']['prefix']


# ----------------------------------------------------------------- select_route


def test_the_matched_route_wins_over_other_routes_to_the_same_processor():
    bindings = [route('r1', policy=prefix_policy('a')), route('r2', policy=prefix_policy('b'))]

    assert policy_manager.select_route(bindings, route_id='r2', pipeline_uuid='processor-a')['id'] == 'r2'


def test_without_a_matched_route_the_first_enabled_route_to_the_processor_is_used():
    bindings = [
        route('agent', 'processor-a', target_type='agent'),
        route('disabled', enabled=False),
        route('other', 'processor-b'),
        route('low', priority=0),
        route('high', priority=5),
    ]

    assert policy_manager.select_route(bindings, pipeline_uuid='processor-a')['id'] == 'high'
    assert policy_manager.select_route(bindings, route_id='gone', pipeline_uuid='processor-b')['id'] == 'other'
    assert policy_manager.select_route(bindings, pipeline_uuid='processor-z') is None
    assert policy_manager.select_route(bindings) is None


def test_bindings_stored_as_text_or_garbage_are_tolerated():
    assert policy_manager.select_route('[{"id": "r1"}]', route_id='r1') == {'id': 'r1'}
    assert policy_manager.select_route('not json', route_id='r1') is None
    assert policy_manager.select_route(None, route_id='r1') is None
    assert policy_manager.select_route([None, 'x', {'id': 'r1'}], route_id='r1') == {'id': 'r1'}


# -------------------------------------------------------------- effective policy


def test_effective_policy_is_bot_default_plus_route_override():
    app = make_app(
        {
            'bot': bot(
                [route('r1', policy=prefix_policy('a')), route('r2', 'processor-b')],
                policy=schema.resolve_policy({'output': {'misc': {'at-sender': True}}}),
            )
        }
    )
    mgr = app.message_policy_mgr

    with_override = mgr.effective_policy(CONTEXT, 'bot', route_id='r1')
    without_override = mgr.effective_policy(CONTEXT, 'bot', route_id='r2')
    unrouted = mgr.effective_policy(CONTEXT, 'bot')

    assert prefixes(with_override) == ['a'] and with_override['output']['misc']['at-sender'] is True
    assert prefixes(without_override) == [] and without_override['output']['misc']['at-sender'] is True
    assert unrouted == without_override


@pytest.mark.parametrize('bot_uuid', [constants.WEBSOCKET_PROXY_BOT_UUID, 'unknown-bot', '', None])
def test_debug_chat_and_unknown_bots_get_the_neutral_policy(bot_uuid):
    app = make_app({'bot': bot([route('r1', policy=prefix_policy('a'))])})

    assert app.message_policy_mgr.effective_policy(CONTEXT, bot_uuid, route_id='r1') == schema.neutral_policy()


# ---------------------------------------------------------------------- runtimes


@pytest.mark.asyncio
async def test_runtimes_are_compiled_once_per_bot_and_route():
    app = make_app(
        {
            'bot-1': bot([route('r1', policy=prefix_policy('a')), route('r2', policy=prefix_policy('b'))]),
            'bot-2': bot([route('r1', policy=prefix_policy('c'))]),
        }
    )
    mgr = app.message_policy_mgr

    first = await mgr.get_runtime(CONTEXT, 'bot-1', route_id='r1')
    again = await mgr.get_runtime(CONTEXT, 'bot-1', route_id='r1')
    other_route = await mgr.get_runtime(CONTEXT, 'bot-1', route_id='r2')
    other_bot = await mgr.get_runtime(CONTEXT, 'bot-2', route_id='r1')
    default = await mgr.get_runtime(CONTEXT, 'bot-1')

    assert again is first
    assert prefixes(first.policy) == ['a'] and first.route_id == 'r1' and first.bot_uuid == 'bot-1'
    assert prefixes(other_route.policy) == ['b']
    assert prefixes(other_bot.policy) == ['c']
    assert default is not first and default.route_id is None and prefixes(default.policy) == []


@pytest.mark.asyncio
async def test_a_route_reached_without_its_id_shares_the_runtime_of_that_route():
    app = make_app({'bot': bot([route('r1', policy=prefix_policy('a'))])})
    mgr = app.message_policy_mgr

    by_id = await mgr.get_runtime(CONTEXT, 'bot', route_id='r1')
    by_processor = await mgr.get_runtime(CONTEXT, 'bot', pipeline_uuid='processor-a')

    assert by_processor is by_id


@pytest.mark.asyncio
async def test_saving_a_bot_invalidates_its_runtimes_only():
    bots = {
        'bot-1': bot([route('r1', policy=prefix_policy('a'))]),
        'bot-2': bot([route('r1', policy=prefix_policy('c'))]),
    }
    app = make_app(bots)
    mgr = app.message_policy_mgr
    stale = await mgr.get_runtime(CONTEXT, 'bot-1', route_id='r1')
    untouched = await mgr.get_runtime(CONTEXT, 'bot-2', route_id='r1')

    # An in-place policy edit is announced explicitly ...
    bots['bot-1'].event_bindings = [route('r1', policy=prefix_policy('edited'))]
    assert await mgr.get_runtime(CONTEXT, 'bot-1', route_id='r1') is stale
    mgr.invalidate_bot('workspace', 'bot-1')
    fresh = await mgr.get_runtime(CONTEXT, 'bot-1', route_id='r1')

    assert fresh is not stale and prefixes(fresh.policy) == ['edited']
    assert await mgr.get_runtime(CONTEXT, 'bot-2', route_id='r1') is untouched

    # ... and a reloaded bot (new entity object) is noticed even without it.
    bots['bot-1'] = bot([route('r1', policy=prefix_policy('reloaded'))])
    reloaded = await mgr.get_runtime(CONTEXT, 'bot-1', route_id='r1')
    assert prefixes(reloaded.policy) == ['reloaded']


@pytest.mark.asyncio
async def test_all_runtimes_share_one_rate_limiter_so_counters_survive_policy_edits():
    app = make_app({'bot': bot([route('r1', policy=prefix_policy('a'))])})
    mgr = app.message_policy_mgr

    first = await mgr.get_runtime(CONTEXT, 'bot', route_id='r1')
    mgr.invalidate_bot('workspace', 'bot')
    second = await mgr.get_runtime(CONTEXT, 'bot', route_id='r1')
    neutral = await mgr.neutral_runtime()

    assert second is not first
    assert first.rate_limiter is second.rate_limiter is neutral.rate_limiter


# ------------------------------------------------------------------------ queries


def routed_query(bot_uuid='bot', route_id=None, pipeline_uuid='processor-a'):
    query = text_query('hello')
    query.bot_uuid = bot_uuid
    query.pipeline_uuid = pipeline_uuid
    query.variables = {}
    if route_id:
        query.variables[policy_manager.ROUTE_VARIABLE] = route_id
    object.__setattr__(query, '_execution_context', CONTEXT)
    return query


@pytest.mark.asyncio
async def test_binding_a_query_lays_its_route_policy_over_the_processor_config():
    app = make_app({'bot': bot([route('r1', policy=prefix_policy('a')), route('r2', policy=prefix_policy('b'))])})
    mgr = app.message_policy_mgr
    config = {'ai': {'runner': {'id': 'x'}}, 'output': {'misc': {'remove-think': True}}}
    query = routed_query(route_id='r2')

    bound = await mgr.bind_query(query, config)

    assert policy_manager.get_query_policy(query) is bound
    assert await mgr.for_query(query) is bound
    assert prefixes(query.pipeline_config) == ['b']
    assert query.pipeline_config['ai'] is config['ai']
    assert query.pipeline_config['output']['misc']['remove-think'] is True
    assert query.pipeline_config['output']['misc']['at-sender'] is False
    assert config == {'ai': {'runner': {'id': 'x'}}, 'output': {'misc': {'remove-think': True}}}


@pytest.mark.asyncio
async def test_a_debug_chat_query_is_bound_to_the_neutral_policy():
    app = make_app({'bot': bot([route('r1', policy=prefix_policy('a'))])})
    query = routed_query(bot_uuid=constants.WEBSOCKET_PROXY_BOT_UUID)

    bound = await app.message_policy_mgr.bind_query(query, {'ai': {}})

    assert bound is await app.message_policy_mgr.neutral_runtime()
    assert query.pipeline_config['trigger'] == schema.neutral_policy()['trigger']
    assert query.pipeline_config['safety'] == schema.neutral_policy()['safety']
