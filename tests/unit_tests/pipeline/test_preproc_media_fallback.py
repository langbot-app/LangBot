from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.api.entities.builtin.platform import message as platform_message


def _conversation():
    prompt = Mock()
    prompt.messages = []
    prompt.copy = Mock(return_value=Mock(messages=[]))

    return SimpleNamespace(
        uuid='conversation-uuid',
        create_time=datetime.now(),
        update_time=datetime.now(),
        prompt=prompt,
        messages=[],
    )


def _prompt_preprocessing_context():
    ctx = Mock()
    ctx.event.default_prompt = []
    ctx.event.prompt = []
    return ctx


@pytest.mark.asyncio
async def test_preprocessor_keeps_image_placeholder_for_text_only_local_agent(mock_app, sample_query):
    model = Mock()
    model.model_entity.uuid = 'text-only-model'
    model.model_entity.abilities = []

    mock_app.model_mgr.get_model_by_uuid = AsyncMock(return_value=model)
    mock_app.sess_mgr.get_session = AsyncMock(
        return_value=SimpleNamespace(launcher_type=sample_query.launcher_type, launcher_id=sample_query.launcher_id)
    )
    mock_app.sess_mgr.get_conversation = AsyncMock(return_value=_conversation())
    mock_app.plugin_connector.emit_event = AsyncMock(return_value=_prompt_preprocessing_context())

    sample_query.pipeline_config = {
        'ai': {
            'runner': {'runner': 'local-agent'},
            'local-agent': {'model': {'primary': 'text-only-model', 'fallbacks': []}, 'prompt': []},
        },
        'trigger': {'misc': {'combine-quote-message': False}},
        'output': {'misc': {'exception-handling': 'show-hint'}},
    }
    sample_query.message_chain = platform_message.MessageChain(
        [platform_message.Image(base64='data:image/png;base64,AAAA')]
    )
    sample_query.messages = []
    sample_query.variables = {}

    from importlib import import_module

    import_module('langbot.pkg.pipeline.pipelinemgr')
    preproc_module = import_module('langbot.pkg.pipeline.preproc.preproc')
    result = await preproc_module.PreProcessor(mock_app).process(sample_query, 'PreProcessor')
    content = result.new_query.user_message.content

    assert len(content) == 1
    assert content[0].type == 'text'
    assert content[0].text == '[Image]'
    assert result.new_query.variables['user_message_text'] == '[Image]'
