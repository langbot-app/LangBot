import pytest

from langbot_plugin.api.entities.builtin.provider.message import Message, MessageChunk
from langbot_plugin.api.entities.builtin.platform.message import File, MessageChain
from langbot.pkg.pipeline.process.stream_results import coalesce_stream_results


async def source(*items):
    for item in items:
        yield item


@pytest.mark.asyncio
async def test_terminal_snapshot_is_delivered_once_with_attachments():
    text = '<think>reasoning</think>answer'
    completed = Message(role='assistant', content=text)
    completed.attachments = MessageChain([File(url='https://example.com/report.txt', name='report.txt')])
    results = [
        item
        async for item in coalesce_stream_results(
            source(
                MessageChunk(role='assistant', content='answer', all_content=text, is_final=True),
                completed,
            )
        )
    ]
    assert results == [completed]
    assert results[0].attachments is completed.attachments


@pytest.mark.asyncio
@pytest.mark.parametrize('with_snapshot', [False, True])
async def test_progressive_chunks_are_not_buffered(with_snapshot):
    first = MessageChunk(role='assistant', content='hel', all_content='hel')
    final = MessageChunk(role='assistant', content='lo', all_content='hello', is_final=True)
    completed = Message(role='assistant', content='hello')
    stream = coalesce_stream_results(source(first, final, *([completed] if with_snapshot else [])))
    assert await anext(stream) == first
    assert [item async for item in stream] == [completed if with_snapshot else final]


@pytest.mark.asyncio
async def test_completed_only_and_distinct_messages_are_preserved():
    final = MessageChunk(role='assistant', content='first', is_final=True)
    other = Message(role='assistant', content='second')
    results = [item async for item in coalesce_stream_results(source(final, other))]
    assert [item.content for item in results] == ['first', 'second']
    assert [item async for item in coalesce_stream_results(source(other))] == [other]


@pytest.mark.asyncio
async def test_blank_terminal_delta_uses_completed_snapshot():
    completed = Message(role='assistant', content='answer')
    results = [
        item
        async for item in coalesce_stream_results(
            source(
                MessageChunk(role='assistant', is_final=True),
                completed,
            )
        )
    ]
    assert results == [completed]


@pytest.mark.asyncio
async def test_failures_propagate_without_successful_final():
    async def failing():
        yield MessageChunk(role='assistant', content='partial')
        raise RuntimeError('provider failed')

    stream = coalesce_stream_results(failing())
    assert (await anext(stream)).content == 'partial'
    with pytest.raises(RuntimeError, match='provider failed'):
        await anext(stream)


@pytest.mark.asyncio
async def test_cumulative_stream_ends_with_last_snapshot_even_when_final_is_blank():
    results = [
        item
        async for item in coalesce_stream_results(
            source(
                MessageChunk(role='assistant', content='hel'),
                MessageChunk(role='assistant', content='hello'),
                MessageChunk(role='assistant', is_final=True),
            )
        )
    ]
    assert [item.all_content for item in results] == ['hel', 'hello', 'hello']
    assert results[-1].is_final
