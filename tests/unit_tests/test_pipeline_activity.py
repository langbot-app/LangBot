import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.pipeline import activity


def setup(monkeypatch, config):
    context = SimpleNamespace(workspace_uuid='workspace-a')
    monkeypatch.setattr(activity, 'get_query_execution_context', lambda query: context)
    language = AsyncMock(return_value='zh_Hans')
    monkeypatch.setattr(activity, 'get_workspace_language', language)
    ap = SimpleNamespace(logger=Mock())
    query = SimpleNamespace(
        pipeline_config={'output': {'misc': config}},
        adapter=SimpleNamespace(reply_message=AsyncMock()),
        message_event=object(),
    )
    return ap, query, language


@pytest.mark.asyncio
async def test_switch_language_custom_and_failure(monkeypatch):
    config = {}
    ap, query, language = setup(monkeypatch, config)
    await activity.notify_activity(ap, query, 'knowledge', 'docs')
    query.adapter.reply_message.assert_not_called()
    config['activity-enabled'] = True
    await activity.notify_activity(ap, query, 'knowledge', 'docs')
    language.assert_awaited_with(ap, 'workspace-a')
    args = query.adapter.reply_message.call_args.args
    assert args[0] is query.message_event
    assert '正在查询知识库：docs' in str(args[1])
    config['tool-call-hint'] = 'Custom {tools} {literal}'
    await activity.notify_activity(ap, query, 'tool', 'search')
    assert str(query.adapter.reply_message.call_args.args[1]) == 'Custom search {literal}'
    config['activity-tool'] = False
    query.adapter.reply_message.reset_mock()
    await activity.notify_activity(ap, query, 'tool', 'search')
    query.adapter.reply_message.assert_not_called()
    query.adapter.reply_message.side_effect = RuntimeError('offline')
    await activity.notify_activity(ap, query, 'knowledge', 'docs')
    ap.logger.debug.assert_called_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'source,label',
    [
        ('plugin', '插件'),
        ('mcp', 'MCP'),
        ('native', '内置'),
        ('skill', '技能'),
        ('platform', '平台'),
    ],
)
async def test_optional_source(monkeypatch, source, label):
    config = {'activity-enabled': True}
    ap, query, _ = setup(monkeypatch, config)
    await activity.notify_activity(ap, query, 'tool', 'search', source=source, source_name='Example')
    assert 'Example' not in str(query.adapter.reply_message.call_args.args[1])
    config['activity-show-source'] = True
    await activity.notify_activity(ap, query, 'tool', 'search', source=source, source_name='Example')
    text = str(query.adapter.reply_message.call_args.args[1])
    assert text == f'🛠️ Agent 正在调用工具：search · {label}: Example'
    assert '\n' not in text


@pytest.mark.asyncio
async def test_progress_does_not_use_final_reply(monkeypatch):
    ap, query, _ = setup(monkeypatch, {'activity-enabled': True})
    query.adapter.reply_progress = AsyncMock()
    await activity.notify_activity(ap, query, 'tool', 'exec')
    query.adapter.reply_progress.assert_awaited_once()
    query.adapter.reply_message.assert_not_called()


@pytest.mark.asyncio
async def test_repeated_operations_are_serialized_and_cancelled(monkeypatch):
    ap, query, _ = setup(monkeypatch, {'activity-enabled': True})
    sent = []
    active = 0

    async def send(event, chain, quote):
        nonlocal active
        active += 1
        assert active == 1
        await asyncio.sleep(0)
        sent.append(str(chain))
        active -= 1

    query.adapter.reply_message.side_effect = send
    await asyncio.gather(
        activity.notify_activity(ap, query, 'knowledge', 'docs'),
        activity.notify_activity(ap, query, 'tool', 'search'),
        activity.notify_activity(ap, query, 'knowledge', 'docs'),
    )
    assert len(sent) == 3
    assert sent[0] == sent[2]
    assert 'search' in sent[1]
    query.adapter.reply_message.side_effect = asyncio.CancelledError()
    with pytest.raises(asyncio.CancelledError):
        await activity.notify_activity(ap, query, 'tool', 'search')
    assert not query._activity_notice_lock.locked()


@pytest.mark.asyncio
@pytest.mark.parametrize('knowledge,tool', [(False, True), (True, False), (False, False), (True, True)])
async def test_category_switches(monkeypatch, knowledge, tool):
    ap, query, _ = setup(
        monkeypatch,
        {
            'activity-enabled': True,
            'activity-knowledge': knowledge,
            'activity-tool': tool,
        },
    )
    await activity.notify_activity(ap, query, 'knowledge', 'docs')
    await activity.notify_activity(ap, query, 'tool', 'search')
    assert query.adapter.reply_message.await_count == int(knowledge) + int(tool)


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'source,owner,action,expected',
    [
        ('plugin', 'langbot-team/AgenticRAG', 'query', 2),
        ('plugin', 'langbot-team/AgenticRAG', 'list', 1),
        ('plugin', 'other/AgenticRAG', 'list', 1),
        ('mcp', 'langbot-team/AgenticRAG', 'list', 1),
    ],
)
async def test_each_tool_and_retrieval_has_its_own_notice(monkeypatch, source, owner, action, expected):
    from langbot.pkg.provider.tools.toolmgr import ToolManager

    ap, query, _ = setup(monkeypatch, {'activity-enabled': True})
    manager = SimpleNamespace(ap=ap, _record_tool_call=AsyncMock(), _trace_tool_call=Mock())

    async def invoke():
        if action == 'query':
            await activity.notify_activity(ap, query, 'knowledge', 'docs')
        return 'result'

    result = await ToolManager._invoke_tool_with_monitoring(
        manager,
        source=source,
        source_id=owner,
        name='query_knowledge',
        parameters={'action': action},
        query=query,
        invoke=invoke,
    )
    assert result == 'result'
    assert query.adapter.reply_message.await_count == expected
    notices = [str(call.args[1]) for call in query.adapter.reply_message.await_args_list]
    assert notices[0] == '🛠️ Agent 正在调用工具：query_knowledge'
    if action == 'query':
        assert notices[1] == '🔍 Agent 正在查询知识库：docs'
    manager._record_tool_call.assert_awaited_once()
