"""
GroupRespondRuleCheckStage unit tests

Tests the actual GroupRespondRuleCheckStage implementation from pkg.pipeline.resprule
"""

import pytest
from unittest.mock import AsyncMock, Mock
from importlib import import_module
import langbot_plugin.api.entities.builtin.provider.session as provider_session
import langbot_plugin.api.entities.builtin.platform.message as platform_message


def get_modules():
    """Lazy import to ensure proper initialization order"""
    # Import pipelinemgr first to trigger proper stage registration
    # pipelinemgr = import_module('langbot.pkg.pipeline.pipelinemgr')
    resprule = import_module('langbot.pkg.pipeline.resprule.resprule')
    entities = import_module('langbot.pkg.pipeline.entities')
    rule = import_module('langbot.pkg.pipeline.resprule.rule')
    rule_entities = import_module('langbot.pkg.pipeline.resprule.entities')
    return resprule, entities, rule, rule_entities


@pytest.mark.asyncio
async def test_person_message_skip(mock_app, sample_query):
    """Test person message skips rule check"""
    resprule, entities, rule, rule_entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.pipeline_config = {'trigger': {'group-respond-rules': {}}}

    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE
    assert result.new_query == sample_query


@pytest.mark.asyncio
async def test_group_message_no_match(mock_app, sample_query):
    """Test group message with no matching rules"""
    resprule, entities, rule, rule_entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {'trigger': {'group-respond-rules': {}}}

    # Create mock rule matcher that doesn't match
    mock_rule = Mock(spec=rule.GroupRespondRule)
    mock_rule.match = AsyncMock(
        return_value=rule_entities.RuleJudgeResult(matching=False, replacement=sample_query.message_chain)
    )

    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    stage.rule_matchers = [mock_rule]

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == entities.ResultType.INTERRUPT
    assert result.new_query == sample_query
    mock_rule.match.assert_called_once()


@pytest.mark.asyncio
async def test_random_response_draw_is_reused_across_queue_rechecks(sample_query, mock_app, monkeypatch):
    from langbot.pkg.pipeline.resprule.rules.random import RandomRespRule
    from unittest.mock import Mock

    draw = Mock(side_effect=[0.9, 0.1])
    monkeypatch.setattr('langbot.pkg.pipeline.resprule.rules.random.random.random', draw)
    matcher = RandomRespRule(mock_app)
    for _ in range(3):
        result = await matcher.match('hello', sample_query.message_chain, {'random': 0.5}, sample_query)
        assert result.matching is False
    draw.assert_called_once()


@pytest.mark.asyncio
async def test_group_message_match(mock_app, sample_query):
    """Test group message with matching rule"""
    resprule, entities, rule, rule_entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {'trigger': {'group-respond-rules': {}}}

    # Create new message chain after rule processing
    new_chain = platform_message.MessageChain([platform_message.Plain(text='Processed message')])

    # Create mock rule matcher that matches
    mock_rule = Mock(spec=rule.GroupRespondRule)
    mock_rule.match = AsyncMock(return_value=rule_entities.RuleJudgeResult(matching=True, replacement=new_chain))

    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    stage.rule_matchers = [mock_rule]

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE
    assert result.new_query == sample_query
    assert sample_query.message_chain == new_chain
    mock_rule.match.assert_called_once()


@pytest.mark.asyncio
async def test_atbot_rule_match(mock_app, sample_query):
    """Test AtBotRule removes At component"""
    resprule, entities, rule, rule_entities = get_modules()
    atbot_module = import_module('langbot.pkg.pipeline.resprule.rules.atbot')

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.adapter.bot_account_id = '999'

    # Create message chain with At component
    message_chain = platform_message.MessageChain(
        [platform_message.At(target='999'), platform_message.Plain(text='Hello bot')]
    )
    sample_query.message_chain = message_chain

    atbot_rule = atbot_module.AtBotRule(mock_app)
    await atbot_rule.initialize()

    result = await atbot_rule.match(str(message_chain), message_chain, {}, sample_query)

    assert result.matching is True
    # At component should be removed
    assert len(result.replacement.root) == 1
    assert isinstance(result.replacement.root[0], platform_message.Plain)


@pytest.mark.asyncio
async def test_atbot_rule_no_match(mock_app, sample_query):
    """Test AtBotRule when no At component present"""
    resprule, entities, rule, rule_entities = get_modules()
    atbot_module = import_module('langbot.pkg.pipeline.resprule.rules.atbot')

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.adapter.bot_account_id = '999'

    # Create message chain without At component
    message_chain = platform_message.MessageChain([platform_message.Plain(text='Hello')])
    sample_query.message_chain = message_chain

    atbot_rule = atbot_module.AtBotRule(mock_app)
    await atbot_rule.initialize()

    result = await atbot_rule.match(str(message_chain), message_chain, {}, sample_query)

    assert result.matching is False


@pytest.mark.asyncio
@pytest.mark.parametrize('routed', [False, True])
@pytest.mark.parametrize('kind', ['plain', 'mention', 'prefix'])
async def test_routed_group_messages_still_obey_response_rules(mock_app, sample_query, routed, kind):
    resprule, entities, _, _ = get_modules()
    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.adapter.bot_account_id = '999'
    sample_query.variables = {'_routed_by_rule': routed}
    sample_query.pipeline_config = {
        'trigger': {'group-respond-rules': {'at': True, 'prefix': ['!bot '], 'regexp': [], 'random': 0}}
    }
    parts = [platform_message.Plain(text='!bot hello' if kind == 'prefix' else 'hello')]
    if kind == 'mention':
        parts.insert(0, platform_message.At(target='999'))
    sample_query.message_chain = platform_message.MessageChain(parts)
    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    expected = entities.ResultType.INTERRUPT if kind == 'plain' else entities.ResultType.CONTINUE
    assert result.result_type == expected
    if kind != 'plain':
        assert str(sample_query.message_chain) == 'hello'


@pytest.mark.asyncio
@pytest.mark.parametrize('routed', [False, True])
@pytest.mark.parametrize(
    'overrides,text,mention,draw,matches,expected_text',
    [
        pytest.param({'regexp': ['^hello$']}, 'hello', False, 0.9, True, 'hello', id='regexp-match'),
        pytest.param({'regexp': ['^hello$']}, 'bye', False, 0.9, False, 'bye', id='regexp-miss'),
        pytest.param({'regexp': ['^bye$', '^hello$']}, 'hello', False, 0.9, True, 'hello', id='second-regexp'),
        pytest.param({'regexp': ['[']}, 'hello', False, 0.9, False, 'hello', id='invalid-regexp'),
        pytest.param({'random': 0}, 'hello', False, 0.0, False, 'hello', id='random-disabled'),
        pytest.param({'random': 1}, 'hello', False, 0.999, True, 'hello', id='random-always'),
        pytest.param({'random': 0.25}, 'hello', False, 0.249, True, 'hello', id='random-hit'),
        pytest.param({'random': 0.25}, 'hello', False, 0.25, False, 'hello', id='random-boundary'),
        pytest.param({}, 'hello', True, 0.0, False, 'hello', id='mention-disabled'),
        pytest.param({}, '!bot hello', False, 0.0, False, '!bot hello', id='prefix-disabled'),
        pytest.param({'prefix': ['!other ', '!bot ']}, '!bot hello', False, 0.9, True, 'hello', id='second-prefix'),
        pytest.param(
            {'at': True, 'prefix': ['!bot '], 'regexp': ['^hello$'], 'random': 0.25},
            'hello',
            False,
            0.9,
            True,
            'hello',
            id='combined-regexp-match',
        ),
        pytest.param(
            {'at': True, 'prefix': ['!bot '], 'regexp': ['^bye$'], 'random': 0.25},
            'hello',
            False,
            0.1,
            True,
            'hello',
            id='combined-random-fallback',
        ),
        pytest.param(
            {'at': True, 'prefix': ['!bot '], 'regexp': ['^bye$'], 'random': 0.25},
            'hello',
            False,
            0.9,
            False,
            'hello',
            id='combined-all-miss',
        ),
    ],
)
async def test_group_response_rule_configuration(
    mock_app, sample_query, monkeypatch, routed, overrides, text, mention, draw, matches, expected_text
):
    resprule, entities, _, _ = get_modules()
    random_rule = import_module('langbot.pkg.pipeline.resprule.rules.random')
    monkeypatch.setattr(random_rule.random, 'random', lambda: draw)
    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.adapter.bot_account_id = '999'
    sample_query.variables = {'_routed_by_rule': routed}
    sample_query.pipeline_config = {
        'trigger': {'group-respond-rules': {'at': False, 'prefix': [], 'regexp': [], 'random': 0, **overrides}}
    }
    parts = [platform_message.Plain(text=text)]
    if mention:
        parts.insert(0, platform_message.At(target='999'))
    sample_query.message_chain = platform_message.MessageChain(parts)
    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == (entities.ResultType.CONTINUE if matches else entities.ResultType.INTERRUPT)
    assert str(result.new_query.message_chain) == expected_text


@pytest.mark.asyncio
@pytest.mark.parametrize('callback_key', ['_interaction_submission', '_dify_form_action'])
async def test_interaction_callbacks_do_not_require_another_mention(mock_app, sample_query, callback_key):
    resprule, entities, _, _ = get_modules()
    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.adapter.bot_account_id = '999'
    submission = {'action_id': 'approve'}
    sample_query.variables = {'_routed_by_rule': True, callback_key: submission}
    sample_query.message_chain = platform_message.MessageChain([platform_message.Plain(text='[Form Action: Approve]')])
    sample_query.pipeline_config = {
        'trigger': {'group-respond-rules': {'at': True, 'prefix': ['!bot '], 'regexp': [], 'random': 0}}
    }
    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE
    assert str(result.new_query.message_chain) == '[Form Action: Approve]'
    assert result.new_query.variables[callback_key] == submission


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'variables',
    [
        {'_routed_by_rule': True, '_dify_form_action': None},
        {'_routed_by_rule': True, '_dify_form_action': {}},
        {'_routed_by_rule': False, '_dify_form_action': {'action_id': 'approve'}},
    ],
)
async def test_incomplete_form_callback_does_not_bypass_response_rules(mock_app, sample_query, variables):
    resprule, entities, _, _ = get_modules()
    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.adapter.bot_account_id = '999'
    sample_query.variables = variables
    sample_query.message_chain = platform_message.MessageChain([platform_message.Plain(text='[Form Action: Approve]')])
    sample_query.pipeline_config = {
        'trigger': {'group-respond-rules': {'at': True, 'prefix': ['!bot '], 'regexp': [], 'random': 0}}
    }
    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == entities.ResultType.INTERRUPT
