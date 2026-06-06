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


class _FakeRunnerDescriptor:
    config_schema = [
        {'name': 'model', 'type': 'model-fallback-selector'},
        {'name': 'prompt', 'type': 'prompt-editor', 'default': []},
        {'name': 'knowledge-bases', 'type': 'knowledge-base-multi-selector', 'default': []},
    ]
    permissions = {
        'models': ['list', 'invoke', 'stream'],
        'tools': ['list', 'detail', 'call'],
        'knowledge_bases': ['list', 'retrieve'],
    }
    capabilities = {
        'tool_calling': True,
        'knowledge_retrieval': True,
        'multimodal_input': True,
        'skill_authoring': True,
        'skill_injection': True,
    }

    def supports_tool_calling(self):
        return self.capabilities.get('tool_calling', False)

    def supports_knowledge_retrieval(self):
        return self.capabilities.get('knowledge_retrieval', False)


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
                'runner': {'id': 'plugin:langbot/local-agent/default'},
                'runner_config': {
                    'plugin:langbot/local-agent/default': {
                        'model': {'primary': 'model-1', 'fallbacks': []},
                        'prompt': [],
                        'knowledge-bases': [],
                    },
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


async def _passthrough_preproc_event(event, bound_plugins):
    return SimpleNamespace(
        event=SimpleNamespace(
            default_prompt=event.default_prompt,
            prompt=event.prompt,
        )
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
        agent_runner_registry=SimpleNamespace(get=AsyncMock(return_value=_FakeRunnerDescriptor())),
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
async def test_preproc_puts_host_skill_tools_into_query_scope():
    """AgentRunner resource authorization consumes the tools discovered by preproc."""
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())
    app.tool_mgr.get_all_tools = AsyncMock(
        return_value=[
            SimpleNamespace(name='activate'),
            SimpleNamespace(name='register_skill'),
        ]
    )
    query = _make_query()
    stage = preproc_module.PreProcessor(app)

    result = await stage.process(query, 'PreProcessor')

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.tool_mgr.get_all_tools.assert_awaited_once_with(None, None, include_skill_authoring=True)
    assert [tool.name for tool in query.use_funcs] == ['activate', 'register_skill']


@pytest.mark.asyncio
async def test_preproc_disables_skill_authoring_tools_when_skill_service_missing():
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=None)
    stage = preproc_module.PreProcessor(app)

    result = await stage.process(_make_query(), 'PreProcessor')

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.tool_mgr.get_all_tools.assert_awaited_once_with(None, None, include_skill_authoring=False)


@pytest.mark.asyncio
async def test_preproc_injects_skill_index_into_system_prompt():
    """The Tool Call activation pattern still needs the LLM to know which
    skills exist. PreProcessor must append the SkillManager's index
    addendum to the first system message."""
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())
    addendum = '\n\nAvailable Skills:\n- demo (demo): Demo skill.\n\nCall activate ...'
    app.skill_mgr.build_skill_aware_prompt_addition = Mock(return_value=addendum)

    query = _make_query()
    result = await stage_process_capture(preproc_module, app, query)

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.skill_mgr.build_skill_aware_prompt_addition.assert_called_once_with(bound_skills=None)
    head = query.prompt.messages[0]
    assert head.role == 'system'
    assert head.content.endswith(addendum)


@pytest.mark.asyncio
async def test_preproc_respects_pipeline_bound_skills_subset():
    """When ``enable_all_skills`` is false the bound list is passed through
    so the addendum only mentions skills allowed for this pipeline."""
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())
    app.pipeline_service.get_pipeline = AsyncMock(
        return_value={
            'extensions_preferences': {
                'enable_all_skills': False,
                'skills': ['only-this'],
            }
        }
    )
    app.skill_mgr.build_skill_aware_prompt_addition = Mock(return_value='')

    query = _make_query()
    result = await stage_process_capture(preproc_module, app, query)

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.skill_mgr.build_skill_aware_prompt_addition.assert_called_once_with(bound_skills=['only-this'])
    assert query.variables.get('_pipeline_bound_skills') == ['only-this']


@pytest.mark.asyncio
async def test_preproc_skips_injection_when_addendum_is_empty():
    """No visible skills → system prompt is left untouched (no
    ``Available Skills`` block appended)."""
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())
    app.skill_mgr.build_skill_aware_prompt_addition = Mock(return_value='')

    query = _make_query()
    result = await stage_process_capture(preproc_module, app, query)

    assert result.result_type == entities_module.ResultType.CONTINUE
    if query.prompt and query.prompt.messages:
        assert 'Available Skills' not in (query.prompt.messages[0].content or '')


@pytest.mark.asyncio
async def test_preproc_uses_transcript_history_view_when_available():
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())
    conversation = app.sess_mgr.get_conversation.return_value
    conversation.messages = [Message(role='user', content='legacy history')]
    app.plugin_connector.emit_event = AsyncMock(side_effect=_passthrough_preproc_event)

    transcript_messages = [
        Message(role='user', content='from transcript user'),
        Message(role='assistant', content='from transcript assistant'),
    ]

    stage = preproc_module.PreProcessor(app)
    stage._load_agent_runner_history_messages = AsyncMock(return_value=transcript_messages)

    query = _make_query()
    result = await stage.process(query, 'PreProcessor')

    assert result.result_type == entities_module.ResultType.CONTINUE
    assert query.messages == transcript_messages


@pytest.mark.asyncio
async def test_preproc_falls_back_to_conversation_messages_when_transcript_empty():
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())
    legacy_messages = [Message(role='user', content='legacy history')]
    app.sess_mgr.get_conversation.return_value.messages = legacy_messages
    app.plugin_connector.emit_event = AsyncMock(side_effect=_passthrough_preproc_event)

    stage = preproc_module.PreProcessor(app)
    stage._load_agent_runner_history_messages = AsyncMock(return_value=None)

    query = _make_query()
    result = await stage.process(query, 'PreProcessor')

    assert result.result_type == entities_module.ResultType.CONTINUE
    assert query.messages == legacy_messages


async def stage_process_capture(preproc_module, app, query):
    """Run PreProcessor.process and return the result while keeping ``query``
    accessible to the assertions (process mutates query in place)."""
    stage = preproc_module.PreProcessor(app)
    return await stage.process(query, 'PreProcessor')
