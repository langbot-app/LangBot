"""B1 admission regressions: real SDK/strategies, explicit local Host fixtures.

No live model, vector service, production Host, or RPC transport is exercised.
Large chunk settings keep the real chunkers deterministic and inexpensive.
"""
import sys
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.rag import ParseResult, TextSection

from test_langrag_mutations import context
from test_shared_state import StorageFixture, bind, load_plugin


LIMIT = 4 * 1024 * 1024
STRATEGIES = ['chunk', 'parent_child', 'qa']


def sized_text(size, character):
    width = len(character.encode('utf-8'))
    text = character * (size // width) + 'x' * (size % width)
    assert len(text.encode('utf-8')) == size
    return text


async def engine_fixture(monkeypatch, strategy):
    pc, ec = load_plugin('LangRAG')
    plugin = bind(pc, StorageFixture())
    await plugin.initialize()
    plugin.invoke_embedding = AsyncMock(side_effect=lambda model, texts: [[1.0] for _ in texts])
    plugin.vector_upsert = AsyncMock()
    plugin.invoke_llm = AsyncMock(return_value=Message(
        role='assistant', content='[{"q": "fixture question", "a": "fixture answer"}]'))
    # Spy on the actual offloader; accepted requests still run real chunkers.
    plugin.offload.run = AsyncMock(wraps=plugin.offload.run)
    plugin.get_knowledge_file_stream = AsyncMock(return_value=b'fixture file')
    engine = ec()
    engine.plugin = plugin
    module = sys.modules[ec.__module__]
    select_strategy = Mock(wraps=module.get_strategy)
    monkeypatch.setattr(module, 'get_strategy', select_strategy)
    ctx = context()
    ctx.creation_settings.update({
        'index_type': strategy,
        'chunk_size': LIMIT + 16,
        'parent_chunk_size': LIMIT + 16,
        'child_chunk_size': LIMIT + 16,
        'qa_llm_model_uuid': 'fixture-llm',
    })
    return engine, ctx, select_strategy, module


def assert_rejected(result, plugin, select_strategy):
    assert result.status.value == 'failed'
    assert '4 MiB' in result.error_message
    assert 'UTF-8' in result.error_message
    assert result.chunks_created == 0
    select_strategy.assert_not_called()
    plugin.offload.run.assert_not_called()
    plugin.invoke_embedding.assert_not_called()
    plugin.vector_upsert.assert_not_called()
    plugin.invoke_llm.assert_not_called()


def assert_accepted(result, plugin, select_strategy, strategy, expected_texts):
    assert result.status.value == 'completed', result.error_message
    assert result.chunks_created == len(expected_texts)
    select_strategy.assert_called_once_with(strategy)
    assert plugin.offload.run.await_count > 0
    plugin.invoke_embedding.assert_awaited_once()
    plugin.vector_upsert.assert_awaited_once()
    stored = plugin.vector_upsert.call_args.kwargs
    assert len(stored['ids']) == len(expected_texts)
    if strategy == 'qa':
        assert plugin.invoke_llm.await_count == len(expected_texts)
        assert [m['source_chunk'] for m in stored['metadata']] == expected_texts
    else:
        plugin.invoke_llm.assert_not_called()
        assert stored['documents'] == expected_texts


@pytest.mark.asyncio
@pytest.mark.parametrize('strategy', STRATEGIES)
@pytest.mark.parametrize('character', ['x', '界'], ids=['ascii', 'utf8'])
@pytest.mark.parametrize('shape', ['flat', 'single_section', 'aggregate_sections'])
@pytest.mark.parametrize('delta', [-1, 0, 1], ids=['below', 'boundary', 'over'])
async def test_parsed_utf8_budget(monkeypatch, strategy, character, shape, delta):
    engine, ctx, select_strategy, _ = await engine_fixture(monkeypatch, strategy)
    payload = sized_text(LIMIT + delta, character)
    if shape == 'flat':
        ctx.parsed_content = ParseResult(text=payload)
        expected = [payload]
    else:
        expected = ([payload] if shape == 'single_section' else
                    [payload[:len(payload) // 2], payload[len(payload) // 2:]])
        if shape == 'aggregate_sections':
            assert all(len(part.encode('utf-8')) < LIMIT for part in expected)
        ctx.parsed_content = ParseResult(
            text='summary', sections=[TextSection(content=part) for part in expected])

    result = await engine.ingest(ctx)

    if delta > 0:
        assert_rejected(result, engine.plugin, select_strategy)
    else:
        assert_accepted(result, engine.plugin, select_strategy, strategy, expected)
    engine.plugin.get_knowledge_file_stream.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('strategy', STRATEGIES)
@pytest.mark.parametrize('delta', [0, 1], ids=['boundary', 'over'])
async def test_flat_budget_still_applies_with_sections(monkeypatch, strategy, delta):
    engine, ctx, select_strategy, _ = await engine_fixture(monkeypatch, strategy)
    # Flat text and section content are alternative representations, not additive.
    # Still bound the flat text even when the strategy consumes small sections.
    ctx.parsed_content = ParseResult(
        text=sized_text(LIMIT + delta, '界'),
        sections=[TextSection(content='small section')])

    result = await engine.ingest(ctx)

    if delta > 0:
        assert_rejected(result, engine.plugin, select_strategy)
    else:
        assert_accepted(result, engine.plugin, select_strategy, strategy, ['small section'])


@pytest.mark.asyncio
@pytest.mark.parametrize('strategy', STRATEGIES)
@pytest.mark.parametrize('delta', [-1, 0, 1], ids=['below', 'boundary', 'over'])
async def test_internal_parser_output_uses_same_utf8_budget(monkeypatch, strategy, delta):
    engine, ctx, select_strategy, module = await engine_fixture(monkeypatch, strategy)
    payload = sized_text(LIMIT + delta, '界')
    ctx.parsed_content = None
    # Explicit parser-output fixture: parsing itself necessarily precedes admission.
    parse = AsyncMock(return_value=payload)
    monkeypatch.setattr(module.FileParser, 'parse', parse)

    result = await engine.ingest(ctx)

    parse.assert_awaited_once_with(b'fixture file', 'file.txt')
    engine.plugin.get_knowledge_file_stream.assert_awaited_once_with('unused')
    if delta > 0:
        assert_rejected(result, engine.plugin, select_strategy)
    else:
        assert_accepted(result, engine.plugin, select_strategy, strategy, [payload])
