from __future__ import annotations

import importlib
import sys
import types
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.api.entities.builtin.agent_runner.manifest import (
    AgentRunnerCapabilities,
    AgentRunnerPermissions,
)
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
        'models': ['invoke', 'stream'],
        'tools': ['detail', 'call'],
        'knowledge_bases': ['list', 'retrieve'],
    }
    permissions = AgentRunnerPermissions.model_validate(permissions)
    capabilities = AgentRunnerCapabilities(
        tool_calling=True,
        knowledge_retrieval=True,
        multimodal_input=True,
        skill_authoring=True,
    )

    def supports_tool_calling(self):
        return self.capabilities.tool_calling

    def supports_knowledge_retrieval(self):
        return self.capabilities.knowledge_retrieval


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
                'runner': {'id': 'plugin:langbot-team/LocalAgent/default'},
                'runner_config': {
                    'plugin:langbot-team/LocalAgent/default': {
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
async def test_preproc_loads_host_tools_for_runner():
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())
    stage = preproc_module.PreProcessor(app)

    result = await stage.process(_make_query(), 'PreProcessor')

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.tool_mgr.get_all_tools.assert_awaited_once_with(
        None,
        None,
        include_mcp_resource_tools=True,
    )


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
    app.tool_mgr.get_all_tools.assert_awaited_once_with(
        None,
        None,
        include_mcp_resource_tools=True,
    )
    assert [tool.name for tool in query.use_funcs] == ['activate', 'register_skill']


@pytest.mark.asyncio
async def test_preproc_loads_host_tools_regardless_of_skill_service():
    """Skill tooling no longer gates on skill_service at the preproc layer."""
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=None)
    stage = preproc_module.PreProcessor(app)

    result = await stage.process(_make_query(), 'PreProcessor')

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.tool_mgr.get_all_tools.assert_awaited_once_with(
        None,
        None,
        include_mcp_resource_tools=True,
    )


@pytest.mark.asyncio
async def test_preproc_disables_mcp_resource_tools_when_agent_reading_is_disabled():
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())
    stage = preproc_module.PreProcessor(app)
    query = _make_query()
    query.variables['_pipeline_mcp_resource_agent_read_enabled'] = False

    result = await stage.process(query, 'PreProcessor')

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.tool_mgr.get_all_tools.assert_awaited_once_with(
        None,
        None,
        include_mcp_resource_tools=False,
    )


@pytest.mark.asyncio
async def test_preproc_records_all_visible_skills_without_prompt_injection():
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())

    query = _make_query()
    result = await stage_process_capture(preproc_module, app, query)

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.pipeline_service.get_pipeline.assert_awaited_once_with('pipe-1')
    assert query.variables.get('_pipeline_bound_skills') is None
    head = query.prompt.messages[0]
    assert head.role == 'system'
    assert head.content == 'system prompt'


@pytest.mark.asyncio
async def test_preproc_respects_pipeline_bound_skills_subset():
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

    query = _make_query()
    result = await stage_process_capture(preproc_module, app, query)

    assert result.result_type == entities_module.ResultType.CONTINUE
    assert query.variables.get('_pipeline_bound_skills') == ['only-this']
    assert query.prompt.messages[0].content == 'system prompt'


@pytest.mark.asyncio
async def test_preproc_does_not_load_skill_preferences_without_skill_mgr():
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=SimpleNamespace())
    app.skill_mgr = None  # no skill manager -> skill tooling unavailable

    query = _make_query()
    result = await stage_process_capture(preproc_module, app, query)

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.pipeline_service.get_pipeline.assert_not_awaited()
    assert '_pipeline_bound_skills' not in query.variables
    assert query.prompt.messages[0].content == 'system prompt'


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
    stage._load_agent_runner_history_messages.assert_awaited_once_with(
        'plugin:langbot-team/LocalAgent/default',
        'conv-1',
        bot_id='bot-1',
        workspace_id=None,
        thread_id=None,
    )


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
