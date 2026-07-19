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

from langbot.pkg.api.http.context import ExecutionContext


_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=1,
    bot_uuid='bot-1',
    pipeline_uuid='pipe-1',
)


def _make_query() -> Query:
    message_chain = MessageChain([Plain(text='create a skill')])
    query = Query(
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
    object.__setattr__(query, '_execution_context', _CONTEXT)
    return query


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
            ensure_loaded=AsyncMock(),
            get_skills=Mock(return_value={}),
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
    app.tool_mgr.get_all_tools.assert_awaited_once_with(
        _CONTEXT,
        None,
        None,
        include_skill_authoring=True,
        include_mcp_resource_tools=True,
    )


@pytest.mark.asyncio
async def test_preproc_disables_skill_authoring_tools_when_skill_service_missing():
    preproc_module, entities_module = _import_preproc_modules()

    app = _make_app(skill_service=None)
    stage = preproc_module.PreProcessor(app)

    result = await stage.process(_make_query(), 'PreProcessor')

    assert result.result_type == entities_module.ResultType.CONTINUE
    app.tool_mgr.get_all_tools.assert_awaited_once_with(
        _CONTEXT,
        None,
        None,
        include_skill_authoring=False,
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
        _CONTEXT,
        None,
        None,
        include_skill_authoring=True,
        include_mcp_resource_tools=False,
    )


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
    app.skill_mgr.build_skill_aware_prompt_addition.assert_called_once_with(
        _CONTEXT,
        bound_skills=None,
    )
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
    app.skill_mgr.build_skill_aware_prompt_addition.assert_called_once_with(
        _CONTEXT,
        bound_skills=['only-this'],
    )
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


async def stage_process_capture(preproc_module, app, query):
    """Run PreProcessor.process and return the result while keeping ``query``
    accessible to the assertions (process mutates query in place)."""
    stage = preproc_module.PreProcessor(app)
    return await stage.process(query, 'PreProcessor')
