"""
GroupRespondRuleCheckStage stage unit tests
"""

import pytest
from unittest.mock import AsyncMock, Mock
from importlib import import_module
import langbot_plugin.api.entities.builtin.provider.session as provider_session


def get_resprule_module():
    return import_module('pkg.pipeline.resprule.resprule')


def get_entities_module():
    return import_module('pkg.pipeline.entities')


@pytest.mark.asyncio
async def test_resprule_person_message_skip(mock_app, sample_query):
    """Test person message skips rule check"""
    resprule = get_resprule_module()
    entities = get_entities_module()

    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.pipeline_config['trigger'] = {'group-respond-rules': {}}

    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    stage.rule_matchers = []
    await stage.initialize({})

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_resprule_group_message_no_match(mock_app, sample_query):
    """Test group message with no matching rules"""
    resprule = get_resprule_module()
    entities = get_entities_module()

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.pipeline_config['trigger'] = {'group-respond-rules': {}}

    # Create mock rule matcher that doesn't match
    mock_matcher = Mock()
    mock_match_result = Mock()
    mock_match_result.matching = False
    mock_matcher.match = AsyncMock(return_value=mock_match_result)

    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    stage.rule_matchers = [mock_matcher]
    await stage.initialize({})

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == entities.ResultType.INTERRUPT


@pytest.mark.asyncio
async def test_resprule_group_message_match(mock_app, sample_query):
    """Test group message with matching rule"""
    resprule = get_resprule_module()
    entities = get_entities_module()

    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.pipeline_config['trigger'] = {'group-respond-rules': {}}

    # Create mock rule matcher that matches
    mock_matcher = Mock()
    mock_match_result = Mock()
    mock_match_result.matching = True
    mock_match_result.replacement = sample_query.message_chain
    mock_matcher.match = AsyncMock(return_value=mock_match_result)

    stage = resprule.GroupRespondRuleCheckStage(mock_app)
    stage.rule_matchers = [mock_matcher]
    await stage.initialize({})

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == entities.ResultType.CONTINUE
