from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, MagicMock

import pytest
from langbot_plugin.api.entities.builtin.provider.message import Message

from langbot.pkg.command import builtin


@pytest.mark.parametrize(
    'name,expected',
    [
        ('help', '/new'),
        ('new', 'New conversation started'),
        ('stop', 'Reply stopped'),
        ('retry', 'Regenerate the last reply'),
        ('undo', 'Remove the last turn'),
        ('whoami', 'person_alice'),
        ('status', 'QA Chat'),
        ('usage', 'Tokens: 42'),
        ('model', 'Test Model'),
        ('tools', 'draw'),
        ('plugins', 'qa/tools'),
        ('version', 'LangBot'),
    ],
)
async def test_builtin_command(name, expected, monkeypatch):
    config = {'ai': {'runner': {'id': 'defaultrunner'}, 'runner_config': {'defaultrunner': {'tools': ['draw']}}}}
    pipeline = NS(
        pipeline_entity=NS(name='QA Chat', config=config),
        bound_plugins=[],
        bound_mcp_servers=[],
        workspace_operations=[],
    )
    session = NS(using_conversation=None, _command_model_uuid='model-1')
    query = NS(
        launcher_type=NS(value='person'),
        launcher_id='alice',
        sender_id='alice',
        bot_uuid='bot',
        variables={},
        pipeline_config=config,
        message_event=MagicMock(),
        _listener_plugins=['qa/tools'],
    )
    descriptor = NS(id='defaultrunner', config_schema=[])
    connector = NS(
        list_plugins=AsyncMock(
            return_value=[{'manifest': {'manifest': {'metadata': {'author': 'qa', 'name': 'tools'}}}}]
        )
    )
    engine = MagicMock()
    engine.connect.return_value.__aenter__.return_value.scalar = AsyncMock(side_effect=[2, 42])
    app = NS(
        pipeline_mgr=NS(get_pipeline_by_uuid=AsyncMock(return_value=pipeline)),
        message_policy_mgr=NS(bind_query=AsyncMock()),
        sess_mgr=NS(get_session=AsyncMock(return_value=session)),
        agent_run_orchestrator=NS(cancel_active_from_query=AsyncMock(return_value='run')),
        model_mgr=NS(runtime_llm_models_for_workspace=lambda ws: {'model-1': NS(model_entity=NS(name='Test Model'))}),
        persistence_mgr=NS(get_db_engine=lambda: engine),
        runner_registry=NS(get=AsyncMock(return_value=descriptor)),
        plugin_connector=connector,
        tool_mgr=NS(get_resolved_tool_catalog=AsyncMock(return_value=[{'name': 'draw'}])),
        query_pool=NS(add_query=AsyncMock()),
    )
    bot = NS(
        ap=app,
        execution_context=NS(workspace_uuid='ws'),
        bot_entity=NS(name='QA', command_settings={}),
        _effective_plugin_commands=AsyncMock(return_value=[]),
    )
    event = NS(sender=NS(id='alice'), _selected_route={'id': 'route', 'target_type': 'pipeline', 'target_uuid': 'chat'})
    reset = AsyncMock()
    monkeypatch.setattr(builtin, 'reset_conversation', reset)
    history = AsyncMock(return_value=Message(role='user', content='hello'))
    monkeypatch.setattr(builtin.TranscriptStore, 'pop_last_turn', history)
    result = await builtin.execute_builtin(bot, event, None, name, name, query, session)
    assert expected in result
    if name == 'new':
        reset.assert_awaited_once_with(app, query, None)
    if name == 'retry':
        assert str(app.query_pool.add_query.await_args.kwargs['message_chain']) == 'hello'
    if name == 'undo':
        history.assert_awaited_once()


@pytest.mark.parametrize('name', ['new', 'stop', 'retry', 'undo', 'tools', 'model'])
async def test_processor_commands_without_route(name):
    query = NS(launcher_type=NS(value='person'), launcher_id='1')
    bot = NS(bot_entity=NS(command_settings={}), execution_context=None, ap=None)
    assert (
        await builtin.execute_builtin(bot, NS(), None, name, name, query, None) == 'No processor handles this message'
    )
