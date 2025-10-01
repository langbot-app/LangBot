"""
SendResponseBackStage stage unit tests
"""

import pytest
from unittest.mock import AsyncMock, Mock
from importlib import import_module
import langbot_plugin.api.entities.builtin.platform.message as platform_message


def get_respback_module():
    return import_module('pkg.pipeline.respback.respback')


def get_entities_module():
    return import_module('pkg.pipeline.entities')


@pytest.mark.asyncio
async def test_respback_basic_send(mock_app, sample_query, mock_adapter):
    """Test basic response sending"""
    respback = get_respback_module()
    entities = get_entities_module()

    sample_query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='Test response')])
    ]
    sample_query.resp_messages = [Mock()]
    sample_query.pipeline_config['output'] = {
        'force-delay': {'min': 0, 'max': 0},
        'misc': {'at-sender': False, 'quote-origin': False},
    }

    stage = respback.SendResponseBackStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'SendResponseBackStage')

    assert result.result_type == entities.ResultType.CONTINUE
    mock_adapter.reply_message.assert_called_once()


@pytest.mark.asyncio
async def test_respback_with_quote(mock_app, sample_query, mock_adapter):
    """Test response with quote"""
    respback = get_respback_module()
    entities = get_entities_module()

    sample_query.resp_message_chain = [
        platform_message.MessageChain([platform_message.Plain(text='Test response')])
    ]
    sample_query.resp_messages = [Mock()]
    sample_query.pipeline_config['output'] = {
        'force-delay': {'min': 0, 'max': 0},
        'misc': {'at-sender': False, 'quote-origin': True},
    }

    stage = respback.SendResponseBackStage(mock_app)
    await stage.initialize({})

    result = await stage.process(sample_query, 'SendResponseBackStage')

    assert result.result_type == entities.ResultType.CONTINUE
    mock_adapter.reply_message.assert_called_once()
    # Verify quote_origin is True in call args
    call_args = mock_adapter.reply_message.call_args
    assert call_args.kwargs['quote_origin'] is True
