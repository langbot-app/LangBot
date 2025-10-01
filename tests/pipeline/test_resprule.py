"""
GroupRespondRuleCheckStage stage unit tests
"""

import pytest
from unittest.mock import AsyncMock, Mock
import langbot_plugin.api.entities.builtin.provider.session as provider_session

from pkg.pipeline.resprule.resprule import GroupRespondRuleCheckStage
from pkg.pipeline import entities as pipeline_entities


@pytest.mark.asyncio
async def test_resprule_person_message_skip(mock_app, sample_query):
    """Test person message skips rule check"""
    sample_query.launcher_type = provider_session.LauncherTypes.PERSON
    sample_query.pipeline_config['trigger'] = {'group-respond-rules': {}}

    stage = GroupRespondRuleCheckStage(mock_app)
    stage.rule_matchers = []
    await stage.initialize({})

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE


@pytest.mark.asyncio
async def test_resprule_group_message_no_match(mock_app, sample_query):
    """Test group message with no matching rules"""
    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.pipeline_config['trigger'] = {'group-respond-rules': {}}

    # Create mock rule matcher that doesn't match
    mock_matcher = Mock()
    mock_match_result = Mock()
    mock_match_result.matching = False
    mock_matcher.match = AsyncMock(return_value=mock_match_result)

    stage = GroupRespondRuleCheckStage(mock_app)
    stage.rule_matchers = [mock_matcher]
    await stage.initialize({})

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == pipeline_entities.ResultType.INTERRUPT


@pytest.mark.asyncio
async def test_resprule_group_message_match(mock_app, sample_query):
    """Test group message with matching rule"""
    sample_query.launcher_type = provider_session.LauncherTypes.GROUP
    sample_query.pipeline_config['trigger'] = {'group-respond-rules': {}}

    # Create mock rule matcher that matches
    mock_matcher = Mock()
    mock_match_result = Mock()
    mock_match_result.matching = True
    mock_match_result.replacement = sample_query.message_chain
    mock_matcher.match = AsyncMock(return_value=mock_match_result)

    stage = GroupRespondRuleCheckStage(mock_app)
    stage.rule_matchers = [mock_matcher]
    await stage.initialize({})

    result = await stage.process(sample_query, 'GroupRespondRuleCheckStage')

    assert result.result_type == pipeline_entities.ResultType.CONTINUE
