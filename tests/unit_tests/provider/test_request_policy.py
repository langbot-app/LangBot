import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import httpx
import litellm
import pytest

from langbot.pkg.provider.modelmgr.errors import RequesterError
from langbot.pkg.provider.modelmgr.request_policy import (
    CallState,
    RequestPolicy,
    current_call,
    error_metadata,
    opaque_conversation_id,
)
from langbot.pkg.provider.modelmgr.requesters.litellmchat import LiteLLMRequester
from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from tests.unit_tests.provider.conftest import TEST_EXECUTION_CONTEXT
from tests.unit_tests.provider.test_litellmchat import MockRuntimeModel


def test_policy_precedence_zero_and_no_mutation():
    model = {'num_retries': 3, 'request_policy': {'read_timeout': 42}}
    policy = RequestPolicy.resolve({'request_policy': {'retries': 2}}, model, {'num_retries': 0})
    assert policy.retries == 0
    assert policy.read_timeout == 42
    assert model['num_retries'] == 3


@pytest.mark.parametrize(
    'policy',
    [
        {'retries': True},
        {'retries': -1},
        {'retries': 6},
        {'read_timeout': 0},
        {'total_timeout': float('nan')},
        {'connect_timeout': float('inf')},
        {'attribution': 'false'},
        {'conversation_header': 'authorization'},
        {'typo': 1},
    ],
)
def test_invalid_policy(policy):
    with pytest.raises(RequesterError, match='Model request failed|模型请求失败'):
        RequestPolicy.resolve({'request_policy': policy})


def test_retry_metadata_does_not_include_upstream_secrets():
    response = httpx.Response(429, headers={'retry-after': '2', 'x-request-id': 'req-123'})
    meta = error_metadata(SimpleNamespace(status_code=429, response=response))
    assert meta == {'status_code': 429, 'retry_after': 2, 'request_id': 'req-123'}
    adapter = LiteLLMRequester(Mock(), {})
    exc = litellm.RateLimitError('secret-key-and-prompt', llm_provider='openai', model='test', response=response)
    with pytest.raises(RequesterError) as caught:
        adapter._handle_litellm_error(exc)
    assert caught.value.retryable
    assert caught.value.request_id == 'req-123'
    assert 'secret-key' not in str(caught.value)


def test_quota_is_not_retryable():
    adapter = LiteLLMRequester(Mock(), {})
    exc = litellm.RateLimitError('quota', llm_provider='openai', model='test')
    exc.body = {'error': {'code': 'insufficient_quota'}}
    with pytest.raises(RequesterError) as caught:
        adapter._handle_litellm_error(exc)
    assert caught.value.code == 'quota_exceeded'
    assert not caught.value.retryable


@pytest.mark.asyncio
async def test_headers_and_sdk_retry_ownership():
    adapter = LiteLLMRequester(Mock(), {'base_url': 'https://openrouter.ai/api/v1'})
    state = CallState(RequestPolicy(retries=2), 'lb-opaque')
    token = current_call.set(state)
    try:
        args = await adapter._build_completion_args(
            MockRuntimeModel(),
            [],
            extra_args={
                'request_policy': {'retries': 2},
                'num_retries': 2,
                'extra_headers': {'x-openrouter-title': 'Custom app', 'x-other': 'keep'},
            },
        )
    finally:
        current_call.reset(token)
    assert 'request_policy' not in args
    assert args['num_retries'] == args['max_retries'] == 0
    assert isinstance(args['timeout'], httpx.Timeout)
    assert args['extra_headers'] == {
        'x-openrouter-title': 'Custom app',
        'x-other': 'keep',
        'HTTP-Referer': 'https://langbot.app',
        'x-session-id': 'lb-opaque',
    }


@pytest.mark.asyncio
@pytest.mark.parametrize('url', ['https://gateway.example/v1', 'https://openrouter.ai.evil.example/v1'])
async def test_no_vendor_headers_on_unrelated_hosts(url):
    adapter = LiteLLMRequester(Mock(), {'base_url': url})
    args = await adapter._build_completion_args(MockRuntimeModel(), [])
    assert not args.get('extra_headers')
    assert args['num_retries'] == 0


def test_conversation_is_stable_and_scoped():
    query = SimpleNamespace(session=None, launcher_type='person', launcher_id='123', bot_uuid='bot', pipeline_uuid='p')
    first = opaque_conversation_id(query, TEST_EXECUTION_CONTEXT)
    assert first == opaque_conversation_id(query, TEST_EXECUTION_CONTEXT)
    query.bot_uuid = 'another-bot'
    assert first != opaque_conversation_id(query, TEST_EXECUTION_CONTEXT)
    assert opaque_conversation_id(None, TEST_EXECUTION_CONTEXT) is None


@pytest.mark.asyncio
async def test_runtime_retries_only_before_output(runtime_provider, runtime_llm_model):
    provider = runtime_provider
    attempts = 0
    closed = []

    async def stream(**kwargs):
        nonlocal attempts
        attempts += 1
        try:
            if attempts == 1:
                raise RequesterError('transient', retryable=True)
            yield MessageChunk(role='assistant', content='first')
            raise RequesterError('after output', retryable=True)
        finally:
            closed.append(attempts)

    provider.requester.invoke_llm_stream = stream
    result = []
    with pytest.raises(RequesterError, match='after output'):
        async for chunk in provider.invoke_llm_stream(
            None,
            runtime_llm_model,
            [],
            extra_args={'request_policy': {'retries': 3, 'backoff_base': 0.001}},
            execution_context=TEST_EXECUTION_CONTEXT,
        ):
            result.append(chunk.content)
    assert result == ['first']
    assert attempts == 2
    assert closed == [1, 2]
    assert current_call.get() is None


@pytest.mark.asyncio
async def test_runtime_deadline_and_close(runtime_provider, runtime_llm_model):
    closed = asyncio.Event()

    async def stream(**kwargs):
        try:
            await asyncio.Event().wait()
            yield MessageChunk(role='assistant', content='never')
        finally:
            closed.set()

    runtime_provider.requester.invoke_llm_stream = stream
    with pytest.raises(RequesterError) as caught:
        async for _ in runtime_provider.invoke_llm_stream(
            None,
            runtime_llm_model,
            [],
            extra_args={'request_policy': {'first_event_timeout': 0.02}},
            execution_context=TEST_EXECUTION_CONTEXT,
        ):
            pass
    assert caught.value.phase == 'first_event'
    assert closed.is_set()


@pytest.mark.asyncio
async def test_retry_after_cannot_extend_total_budget():
    state = CallState(RequestPolicy(retries=5, total_timeout=0.1))
    state.metrics['attempts'] = 1
    assert not await state.retry(RequesterError('busy', retryable=True, retry_after=30))


@pytest.mark.asyncio
async def test_cancellation_is_not_retried(runtime_provider, runtime_llm_model):
    invoke = AsyncMock(side_effect=asyncio.CancelledError)
    runtime_provider.requester.invoke_llm = invoke
    with pytest.raises(asyncio.CancelledError):
        await runtime_provider.invoke_llm(
            None,
            runtime_llm_model,
            [],
            extra_args={'request_policy': {'retries': 3}},
            execution_context=TEST_EXECUTION_CONTEXT,
        )
    assert invoke.await_count == 1


@pytest.mark.asyncio
async def test_complete_usage_and_timings_persist(runtime_provider, runtime_llm_model):
    from langbot_plugin.api.entities.builtin.pipeline.query import Query

    query = Query.model_construct(
        query_id=1, launcher_type='person', launcher_id=1, variables={}, bot_uuid='bot', pipeline_uuid='p', session=None
    )
    object.__setattr__(query, '_execution_context', TEST_EXECUTION_CONTEXT)
    usage = {
        'prompt_tokens': 20,
        'completion_tokens': 10,
        'total_tokens': 30,
        'prompt_tokens_details': {'cached_tokens': 15},
        'completion_tokens_details': {'reasoning_tokens': 8},
        'cost': 0.01,
    }
    runtime_provider.requester.invoke_llm = AsyncMock(return_value=(Message(role='assistant', content='ok'), usage))
    with patch(
        'langbot.pkg.pipeline.monitoring_helper.MonitoringHelper.record_llm_call', new_callable=AsyncMock
    ) as record:
        result = await runtime_provider.invoke_llm(query, runtime_llm_model, [])
    assert result.content == 'ok'
    details = record.call_args.kwargs['details']
    assert details['usage'] == usage
    assert details['timing']['attempts'] == 1
    assert details['timing']['total_ms'] >= details['timing']['response_completed_ms']
    assert query.variables['_llm_usage'] == usage


@pytest.mark.asyncio
async def test_hidden_reasoning_marks_raw_event_and_usage():
    state = CallState(RequestPolicy())
    adapter = LiteLLMRequester(Mock(), {})

    async def raw():
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(
                    delta=SimpleNamespace(model_dump=lambda: {'reasoning_content': 'hidden'}), finish_reason=None
                )
            ]
        )
        yield SimpleNamespace(choices=[], usage={'prompt_tokens': 3, 'completion_tokens': 2, 'total_tokens': 5})

    token = current_call.set(state)
    try:
        with patch(
            'langbot.pkg.provider.modelmgr.requesters.litellmchat.acompletion', new=AsyncMock(return_value=raw())
        ):
            chunks = [c async for c in adapter.invoke_llm_stream(None, MockRuntimeModel(), [], remove_think=True)]
    finally:
        current_call.reset(token)
    assert state.raw_started
    assert 'first_event_ms' in state.metrics and 'first_reasoning_ms' in state.metrics
    assert 'first_content_ms' not in state.metrics
    assert state.usage['total_tokens'] == 5
    assert not any(c.content for c in chunks)


@pytest.mark.asyncio
async def test_real_http_retry_count_and_request_body(runtime_provider, runtime_llm_model):
    """Exercise the pinned LiteLLM/OpenAI SDK against a local HTTP server."""
    from aiohttp import web

    received = []

    async def handler(request):
        received.append(await request.json())
        if len(received) == 1:
            return web.json_response({'error': {'message': 'busy', 'type': 'server_error'}}, status=503)
        return web.json_response(
            {
                'id': 'chatcmpl-local',
                'object': 'chat.completion',
                'created': 1,
                'model': 'gpt-4o',
                'choices': [{'index': 0, 'message': {'role': 'assistant', 'content': 'ok'}, 'finish_reason': 'stop'}],
                'usage': {'prompt_tokens': 4, 'completion_tokens': 1, 'total_tokens': 5},
            }
        )

    app = web.Application()
    app.router.add_post('/v1/chat/completions', handler)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, '127.0.0.1', 0)
    await site.start()
    port = site._server.sockets[0].getsockname()[1]
    runtime_provider.requester = LiteLLMRequester(
        Mock(),
        {
            'base_url': f'http://127.0.0.1:{port}/v1',
            'custom_llm_provider': 'openai',
        },
    )
    runtime_llm_model.model_entity.name = 'gpt-4o'
    runtime_llm_model.model_entity.extra_args = {}
    try:
        with pytest.raises(RequesterError):
            await runtime_provider.invoke_llm(
                None,
                runtime_llm_model,
                [Message(role='user', content='hello')],
                extra_args={'num_retries': 0},
                execution_context=TEST_EXECUTION_CONTEXT,
            )
        assert len(received) == 1
        received.clear()
        result = await runtime_provider.invoke_llm(
            None,
            runtime_llm_model,
            [Message(role='user', content='hello')],
            extra_args={'request_policy': {'retries': 1, 'backoff_base': 0.001}},
            execution_context=TEST_EXECUTION_CONTEXT,
        )
        assert result.content == 'ok'
        assert len(received) == 2
        assert all('request_policy' not in body and 'num_retries' not in body for body in received)
    finally:
        await runner.cleanup()


@pytest.mark.asyncio
async def test_stream_idle_timeout_after_output(runtime_provider, runtime_llm_model):
    async def stream(**kwargs):
        yield MessageChunk(role='assistant', content='first')
        await asyncio.Event().wait()

    runtime_provider.requester.invoke_llm_stream = stream
    with pytest.raises(RequesterError) as caught:
        async for _ in runtime_provider.invoke_llm_stream(
            None,
            runtime_llm_model,
            [],
            extra_args={'request_policy': {'stream_idle_timeout': 0.02}},
            execution_context=TEST_EXECUTION_CONTEXT,
        ):
            pass
    assert caught.value.phase == 'stream_idle'


def test_details_migration_preserves_existing_records_and_is_idempotent():
    import importlib
    import sqlalchemy as sa
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0038_llm_call_details')
    engine = sa.create_engine('sqlite://')
    try:
        with engine.begin() as connection:
            connection.exec_driver_sql('CREATE TABLE monitoring_llm_calls (id TEXT PRIMARY KEY)')
            connection.exec_driver_sql("INSERT INTO monitoring_llm_calls (id) VALUES ('old')")
            with Operations.context(MigrationContext.configure(connection)):
                migration.upgrade()
                migration.upgrade()
            assert connection.exec_driver_sql('SELECT id, details FROM monitoring_llm_calls').one() == ('old', None)
            table = sa.Table('monitoring_llm_calls', sa.MetaData(), autoload_with=connection)
            payload = {'usage': {'completion_tokens_details': {'reasoning_tokens': 8}}, 'timing': {'first_event_ms': 1}}
            connection.execute(table.insert().values(id='new', details=payload))
            assert connection.execute(sa.select(table.c.details).where(table.c.id == 'new')).scalar() == payload
    finally:
        engine.dispose()


@pytest.mark.asyncio
async def test_hidden_raw_events_reset_idle_not_first_visible_deadline(runtime_provider, runtime_llm_model):
    adapter = LiteLLMRequester(Mock(), {})
    runtime_provider.requester = adapter
    runtime_llm_model.model_entity.extra_args = {}

    async def raw():
        for _ in range(5):
            await asyncio.sleep(0.3)
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(delta=SimpleNamespace(model_dump=lambda: {'role': 'assistant'}), finish_reason=None)
                ]
            )
        yield SimpleNamespace(
            choices=[
                SimpleNamespace(delta=SimpleNamespace(model_dump=lambda: {'content': 'answer'}), finish_reason='stop')
            ]
        )

    with patch('langbot.pkg.provider.modelmgr.requesters.litellmchat.acompletion', new=AsyncMock(return_value=raw())):
        chunks = [
            chunk
            async for chunk in runtime_provider.invoke_llm_stream(
                None,
                runtime_llm_model,
                [],
                extra_args={'request_policy': {'first_event_timeout': 1, 'stream_idle_timeout': 2}},
                execution_context=TEST_EXECUTION_CONTEXT,
            )
        ]
    assert ''.join(chunk.content or '' for chunk in chunks) == 'answer'


@pytest.mark.asyncio
async def test_monitoring_service_persists_full_details():
    from langbot.pkg.api.http.service.monitoring import MonitoringService

    persistence = SimpleNamespace(execute_async=AsyncMock())
    service = MonitoringService(SimpleNamespace(persistence_mgr=persistence))
    details = {
        'usage': {
            'prompt_tokens': 4,
            'completion_tokens': 3,
            'total_tokens': 9,
            'cache_read_input_tokens': 2,
            'provider_extra': {'cost': 0.01},
        },
        'timing': {'attempts': 2},
        'error': None,
    }
    await service.record_llm_call(
        TEST_EXECUTION_CONTEXT,
        bot_id='b',
        bot_name='b',
        pipeline_id='p',
        pipeline_name='p',
        session_id='s',
        model_name='m',
        input_tokens=4,
        output_tokens=3,
        duration=10,
        details=details,
    )
    values = persistence.execute_async.call_args.args[0].compile().params
    assert values['details'] == details
    assert values['total_tokens'] == 9


def test_codex_usage_preserves_provider_fields():
    from langbot.pkg.provider.modelmgr.requesters.codex import _usage

    raw = {
        'input_tokens': 4,
        'output_tokens': 2,
        'cost': 0.02,
        'output_tokens_details': {'reasoning_tokens': 1},
        'future_counter': 7,
    }
    normalized = _usage({'usage': raw})
    assert all(normalized[key] == value for key, value in raw.items())
    assert normalized['total_tokens'] == 6


@pytest.mark.asyncio
async def test_nonstream_uses_response_budget_not_first_event():
    adapter = LiteLLMRequester(Mock(), {})
    state = CallState(RequestPolicy(first_event_timeout=0.001, total_timeout=1))

    async def completion(**kwargs):
        await asyncio.sleep(0.02)
        return 'complete'

    token = current_call.set(state)
    try:
        with patch('langbot.pkg.provider.modelmgr.requesters.litellmchat.acompletion', new=completion):
            assert await adapter._completion({'stream': False}) == 'complete'
    finally:
        current_call.reset(token)


@pytest.mark.asyncio
@pytest.mark.parametrize('cancel_read', [False, True])
async def test_litellm_stream_close_and_cancel_release_upstream(runtime_provider, runtime_llm_model, cancel_read):
    adapter = LiteLLMRequester(Mock(), {})
    runtime_provider.requester = adapter
    runtime_llm_model.model_entity.extra_args = {}
    closed = asyncio.Event()
    reading = asyncio.Event()

    async def raw():
        try:
            yield SimpleNamespace(
                choices=[
                    SimpleNamespace(delta=SimpleNamespace(model_dump=lambda: {'content': 'first'}), finish_reason=None)
                ]
            )
            reading.set()
            await asyncio.Event().wait()
        finally:
            closed.set()

    completion = AsyncMock(return_value=raw())
    with patch('langbot.pkg.provider.modelmgr.requesters.litellmchat.acompletion', new=completion):
        stream = runtime_provider.invoke_llm_stream(
            None,
            runtime_llm_model,
            [],
            extra_args={'request_policy': {'retries': 3}},
            execution_context=TEST_EXECUTION_CONTEXT,
        )
        assert (await anext(stream)).content == 'first'
        if cancel_read:
            task = asyncio.create_task(anext(stream))
            await reading.wait()
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
        else:
            await stream.aclose()
        assert closed.is_set()
        assert completion.await_count == 1
        assert current_call.get() is None


@pytest.mark.asyncio
async def test_cancel_during_backoff_does_not_start_another_attempt(runtime_provider, runtime_llm_model):
    runtime_provider.requester.invoke_llm = AsyncMock(side_effect=RequesterError('busy', retryable=True))
    sleeping = asyncio.Event()

    async def backoff(delay):
        sleeping.set()
        await asyncio.Event().wait()

    with patch('langbot.pkg.provider.modelmgr.request_policy.asyncio.sleep', new=backoff):
        task = asyncio.create_task(
            runtime_provider.invoke_llm(
                None,
                runtime_llm_model,
                [],
                extra_args={'request_policy': {'retries': 3}},
                execution_context=TEST_EXECUTION_CONTEXT,
            )
        )
        await sleeping.wait()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
    assert runtime_provider.requester.invoke_llm.await_count == 1


@pytest.mark.asyncio
async def test_legacy_none_chunk_is_ignored(runtime_provider, runtime_llm_model):
    async def stream(**kwargs):
        yield None
        yield MessageChunk(role='assistant', content='ok')

    runtime_provider.requester.invoke_llm_stream = stream
    chunks = [
        chunk
        async for chunk in runtime_provider.invoke_llm_stream(
            None, runtime_llm_model, [], execution_context=TEST_EXECUTION_CONTEXT
        )
    ]
    assert [chunk.content for chunk in chunks] == ['ok']
