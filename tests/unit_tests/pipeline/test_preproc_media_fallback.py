from __future__ import annotations

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.api.entities.builtin.platform import message as platform_message


RUNNER_ID = 'plugin:langbot-team/LocalAgent/default'


def _attach_agent_runner_descriptor(app):
    from langbot.pkg.agent.runner.descriptor import AgentRunnerDescriptor

    descriptor = AgentRunnerDescriptor(
        id=RUNNER_ID,
        source='plugin',
        label={'en_US': 'Local Agent'},
        plugin_author='langbot-team',
        plugin_name='LocalAgent',
        runner_name='default',
        config_schema=[
            {'name': 'model', 'type': 'model-fallback-selector'},
            {'name': 'prompt', 'type': 'prompt-editor', 'default': []},
        ],
        capabilities={'tool_calling': True, 'multimodal_input': True},
    )
    app.agent_runner_registry = Mock()
    app.agent_runner_registry.get = AsyncMock(return_value=descriptor)


def _pipeline_config(model_config):
    return {
        'ai': {
            'runner': {'id': RUNNER_ID},
            'runner_config': {RUNNER_ID: {'model': model_config, 'prompt': []}},
        },
        'trigger': {'misc': {'combine-quote-message': False}},
        'output': {'misc': {'exception-handling': 'show-hint'}},
    }


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
    _attach_agent_runner_descriptor(mock_app)
    mock_app.sess_mgr.get_session = AsyncMock(
        return_value=SimpleNamespace(launcher_type=sample_query.launcher_type, launcher_id=sample_query.launcher_id)
    )
    mock_app.sess_mgr.get_conversation = AsyncMock(return_value=_conversation())
    mock_app.plugin_connector.emit_event = AsyncMock(return_value=_prompt_preprocessing_context())

    sample_query.pipeline_config = _pipeline_config({'primary': 'text-only-model', 'fallbacks': []})
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
