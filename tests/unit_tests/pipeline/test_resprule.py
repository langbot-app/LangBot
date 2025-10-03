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
    pipelinemgr = import_module('pkg.pipeline.pipelinemgr')
    resprule = import_module('pkg.pipeline.resprule.resprule')
    entities = import_module('pkg.pipeline.entities')
    rule = import_module('pkg.pipeline.resprule.rule')
    rule_entities = import_module('pkg.pipeline.resprule.entities')
    return resprule, entities, rule, rule_entities


@pytest.mark.asyncio
async def test_person_message_skip(mock_app, sample_query):
    """Test person message skips rule check"""
    resprule, entities, rule, rule_entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.pipeline_config = {
        'trigger': {
            'group-respond-rules': {}
        }
    }

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
    sample_query.pipeline_config = {
        'trigger': {
            'group-respond-rules': {}
        }
    }

    # Create mock rule matcher that doesn't match
    mock_rule = Mock(spec=rule.GroupRespondRule)
    mock_rule.match = AsyncMock(return_value=rule_entities.RuleJudgeResult(
        matching=False,
        replacement=sample_query.message_chain
    ))

    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    await stage.initialize(sample_query.pipeline_config)
    stage.rule_matchers = [mock_rule]

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == entities.ResultType.INTERRUPT
    assert result.new_query == sample_query
    mock_rule.match.assert_called_once()


@pytest.mark.asyncio
async def test_group_message_match(mock_app, sample_query):
    """Test group message with matching rule"""
    resprule, entities, rule, rule_entities = get_modules()

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.launcher_id = '12345'
    sample_query.pipeline_config = {
        'trigger': {
            'group-respond-rules': {}
        }
    }

    # Create new message chain after rule processing
    new_chain = platform_message.MessageChain([
        platform_message.Plain(text='Processed message')
    ])

    # Create mock rule matcher that matches
    mock_rule = Mock(spec=rule.GroupRespondRule)
    mock_rule.match = AsyncMock(return_value=rule_entities.RuleJudgeResult(
        matching=True,
        replacement=new_chain
    ))

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
    atbot_module = import_module('pkg.pipeline.resprule.rules.atbot')

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.adapter.bot_account_id = '999'

    # Create message chain with At component
    message_chain = platform_message.MessageChain([
        platform_message.At(target='999'),
        platform_message.Plain(text='Hello bot')
    ])
    sample_query.message_chain = message_chain

    atbot_rule = atbot_module.AtBotRule(mock_app)
    await atbot_rule.initialize()

    result = await atbot_rule.match(
        str(message_chain),
        message_chain,
        {},
        sample_query
    )

    assert result.matching is True
    # At component should be removed
    assert len(result.replacement.root) == 1
    assert isinstance(result.replacement.root[0], platform_message.Plain)


@pytest.mark.asyncio
async def test_atbot_rule_no_match(mock_app, sample_query):
    """Test AtBotRule when no At component present"""
    resprule, entities, rule, rule_entities = get_modules()
    atbot_module = import_module('pkg.pipeline.resprule.rules.atbot')

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.adapter.bot_account_id = '999'

    # Create message chain without At component
    message_chain = platform_message.MessageChain([
        platform_message.Plain(text='Hello')
    ])
    sample_query.message_chain = message_chain

    atbot_rule = atbot_module.AtBotRule(mock_app)
    await atbot_rule.initialize()

    result = await atbot_rule.match(
        str(message_chain),
        message_chain,
        {},
        sample_query
    )

    assert result.matching is False
