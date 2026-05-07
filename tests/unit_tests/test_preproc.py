from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.api.entities.builtin.pipeline.query import Query
from langbot_plugin.api.entities.builtin.platform.entities import Friend
from langbot_plugin.api.entities.builtin.platform.events import FriendMessage
from langbot_plugin.api.entities.builtin.platform.message import MessageChain, Plain
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.provider.prompt import Prompt
from langbot_plugin.api.entities.builtin.provider.session import Conversation, LauncherTypes, Session


def _make_query() -> Query:
    message_chain = MessageChain([Plain(text='create a skill')])
    return Query(
        query_id=1,
        launcher_type=LauncherTypes.PERSON,
        launcher_id='launcher-1',
        sender_id='sender-1',
        message_event=FriendMessage(
            message_chain=message_chain,
            time=0,
            sender=Friend(id='sender-1', nickname='Tester', remark='Tester'),
        ),
        message_chain=message_chain,
        bot_uuid='bot-1',
        pipeline_uuid='pipe-1',
        pipeline_config={
            'ai': {
                'runner': {'runner': 'local-agent'},
                'local-agent': {
                    'model': {'primary': 'model-1', 'fallbacks': []},
                    'prompt': 'default',
                    'knowledge-bases': [],
                },
            },
            'trigger': {'misc': {}},
        },
        variables={},
    )


def _make_conversation() -> Conversation:
    return Conversation(
        prompt=Prompt(name='default', messages=[Message(role='system', content='system prompt')]),
        messages=[],
        pipeline_uuid='pipe-1',
        bot_uuid='bot-1',
        uuid='conv-1',
    )


def _make_app(*, skill_service) -> SimpleNamespace:
    session = Session(launcher_type=LauncherTypes.PERSON, launcher_id='launcher-1', sender_id='sender-1')
    conversation = _make_conversation()
    model = SimpleNamespace(model_entity=SimpleNamespace(uuid='model-1', abilities={'func_call'}))
    tool_mgr = SimpleNamespace(get_all_tools=AsyncMock(return_value=[]))

    return SimpleNamespace(
        sess_mgr=SimpleNamespace(
            get_session=AsyncMock(return_value=session),
            get_conversation=AsyncMock(return_value=conversation),
        ),
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
        tool_mgr=tool_mgr,
        plugin_connector=SimpleNamespace(
            emit_event=AsyncMock(
                return_value=SimpleNamespace(
                    event=SimpleNamespace(
                        default_prompt=conversation.prompt.messages.copy(),
                        prompt=conversation.messages.copy(),
                    )
                )
            )
        ),
        pipeline_service=SimpleNamespace(
            get_pipeline=AsyncMock(return_value={'extensions_preferences': {'enable_all_skills': True}})
        ),
        skill_mgr=SimpleNamespace(
            build_skill_aware_prompt_addition=Mock(return_value=''),
            skills={},
        ),
        skill_service=skill_service,
        logger=Mock(),
    )


def _import_preproc_modules():
    fake_app_module = types.ModuleType('langbot.pkg.core.app')
    fake_app_module.Application = object
    sys.modules['langbot.pkg.core.app'] = fake_app_module

    for module_name in (
        'langbot.pkg.pipeline.preproc.preproc',
        'langbot.pkg.pipeline.stage',
    ):
        sys.modules.pop(module_name, None)

    preproc_module = importlib.import_module('langbot.pkg.pipeline.preproc.preproc')
    entities_module = importlib.import_module('langbot.pkg.pipeline.entities')
    return preproc_module, entities_module


@pytest.mark.asyncio
async def test_preproc_enables_skill_authoring_tools_when_skill_service_available():
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())
    stage = preproc_module.PreProcessor(app)

    result = await stage.process(_make_query(), 'PreProcessor')

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.tool_mgr.get_all_tools.assert_awaited_once_with(None, None, include_skill_authoring=True)


@pytest.mark.asyncio
async def test_preproc_disables_skill_authoring_tools_when_skill_service_missing():
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=None)
    stage = preproc_module.PreProcessor(app)

    result = await stage.process(_make_query(), 'PreProcessor')

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.tool_mgr.get_all_tools.assert_awaited_once_with(None, None, include_skill_authoring=False)
