from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.workflow.graph import render, validate
from langbot.pkg.workflow.tree import execute_tree


def node(kind, **config):
    return dict(id=kind, name=kind, type=kind, config=config)


def path(*nodes):
    return {'nodes': list(nodes), 'edges': [{'from': a['id'], 'to': b['id']} for a, b in zip(nodes, nodes[1:])]}


def test_templates():
    assert render(
        ['{{start.x}}/{{memory.y}}/{{missing}}', {'a': '{{start.z}}'}],
        {'start': {'x': False, 'z': '{{memory.y}}'}},
        {'y': [1]},
    ) == ['false/[1]/', {'a': '{{memory.y}}'}]


@pytest.mark.parametrize(
    ('graph', 'code'),
    [
        (path(), 'start_missing'),
        (path(node('start'), node('start')), 'not_tree'),
        (
            path(node('start'), node('handoff', target_type='chat', target_uuid='p'), node('reply', text='ok')),
            'handoff_has_next',
        ),
        (path(node('start'), node('classify', categories=[], model_uuid='m')), 'empty_category'),
        (path(node('start'), node('reply', text='{{other.text}}')), 'ref_not_upstream'),
        (path(node('start'), node('reply', text='{{start.other}}')), 'ref_unknown_key'),
        (path(node('start'), node('http')), 'required_missing'),
        (path(node('start'), node('llm', model_uuid='m', prompt='hi')), 'model_not_found'),
        (path(node('start'), node('handoff', target_type='agent', target_uuid='a')), 'target_not_found'),
        ({'nodes': [node('start'), node('reply', text='x')], 'edges': []}, 'unreachable'),
        (
            {
                'nodes': [node('start'), node('reply', text='x')],
                'edges': [{'from': 'start', 'to': 'reply', 'branch': 'else'}],
            },
            'branch_unknown',
        ),
    ],
)
def test_issue_codes(graph, code):
    assert code in {issue['code'] for issue in validate(graph, models=set(), targets=set())}


@pytest.mark.asyncio
async def test_memory_and_branch():
    graph = path(
        node('start'),
        node('remember', items=[{'key': 'last', 'value': '{{start.text}}'}], scope='run'),
        node(
            'condition',
            cases=[dict(id='yes', match='all', rules=[dict(left='{{memory.run.last}}', op='equals', right='hi')])],
        ),
        node('reply', text='{{remember.value.last}}'),
    )
    graph['edges'][-1]['branch'] = 'yes'
    from langbot.pkg.workflow.memory import RunMemory

    store = RunMemory(None, 'workspace', 'workflow', 'user', None)
    runtime = SimpleNamespace(reply=AsyncMock(return_value=None))
    steps, error = await execute_tree(
        graph,
        {'text': 'hi'},
        ap=None,
        runtime=runtime,
        memory=store.values,
        save_memory=store.write,
        history=[],
        models=set(),
        targets=set(),
    )
    assert error is None
    assert [step['node_id'] for step in steps] == ['start', 'remember', 'condition', 'reply']
    assert steps[2]['branch'] == 'yes'
    assert steps[-1]['inputs']['text'] == 'hi'
    assert store.values['run'] == {'last': 'hi'}


@pytest.mark.asyncio
async def test_invalid_graph_never_starts():
    steps, error = await execute_tree(
        path(node('start'), node('reply')),
        {},
        ap=None,
        runtime=None,
        memory={},
        save_memory=None,
        history=[],
        models=set(),
        targets=set(),
    )
    assert not steps and 'required_missing' in error


@pytest.mark.asyncio
@pytest.mark.parametrize('answer,branch', [('c1', 'c1'), ('other', 'else')])
async def test_classification(answer, branch):
    from langbot.pkg.workflow.steps import run_step

    model = SimpleNamespace(
        provider=SimpleNamespace(invoke_llm=AsyncMock(return_value=SimpleNamespace(content=answer)))
    )
    app = SimpleNamespace(model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)))
    output, selected = await run_step(
        'classify',
        {'model_uuid': 'm', 'categories': [{'id': 'c1', 'label': 'Refund'}]},
        {'text': 'message'},
        ap=app,
        runtime=SimpleNamespace(execution_context=object()),
        memory={},
        save_memory=None,
        history=[],
    )
    assert selected == branch
    assert output == {'category': 'Refund' if branch == 'c1' else 'else'}


@pytest.mark.asyncio
@pytest.mark.parametrize('policy', ['stop', 'continue'])
async def test_model_failure(policy):
    app = SimpleNamespace(
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(side_effect=ValueError('Model unavailable')))
    )
    graph = path(
        node('start'),
        node('llm', model_uuid='m', prompt='hello', on_error=policy),
        node('reply', text='result:{{llm.text}}'),
    )
    runtime = SimpleNamespace(reply=AsyncMock(return_value=None), execution_context=object())
    steps, error = await execute_tree(
        graph,
        {'text': 'hello'},
        ap=app,
        runtime=runtime,
        memory={},
        save_memory=None,
        history=[],
        models={'m'},
        targets=set(),
    )
    if policy == 'stop':
        assert error == 'llm: Model unavailable'
        runtime.reply.assert_not_awaited()
    else:
        assert error is None
        assert steps[1]['outputs'] == {'text': '', 'error': 'Model unavailable'}
        assert steps[-1]['inputs']['text'] == 'result:'


@pytest.mark.asyncio
async def test_http_keeps_outbound_policy():
    from langbot.pkg.workflow.steps import request
    from langbot.pkg.utils.outbound_url import UnsafeOutboundUrlError

    with pytest.raises(UnsafeOutboundUrlError):
        await request({'url': 'http://127.0.0.1/'})


@pytest.mark.parametrize('use_images', [True, False])
async def test_llm_passes_images_only_when_enabled(use_images):
    from langbot.pkg.workflow.steps import run_step

    invoke = AsyncMock(return_value=SimpleNamespace(content='done'))
    model = SimpleNamespace(provider=SimpleNamespace(invoke_llm=invoke))
    media = SimpleNamespace(get_media=AsyncMock(return_value=(b'png', 'image/png')))
    app = SimpleNamespace(
        model_mgr=SimpleNamespace(get_model_by_uuid=AsyncMock(return_value=model)),
        storage_mgr=SimpleNamespace(media_cache=media),
    )
    await run_step(
        'llm',
        {'model_uuid': 'm', 'use_images': use_images, 'prompt': 'describe'},
        {'images': ['/api/v1/files/media/cached.png']},
        ap=app,
        runtime=SimpleNamespace(execution_context=object()),
        memory={},
        save_memory=None,
        history=[],
    )
    content = invoke.await_args.kwargs['messages'][-1].content
    if use_images:
        assert content[0].text == 'describe'
        assert content[1].image_url.url == 'data:image/png;base64,cG5n'
        media.get_media.assert_awaited_once_with('cached.png')
    else:
        assert content == 'describe'
        media.get_media.assert_not_awaited()
