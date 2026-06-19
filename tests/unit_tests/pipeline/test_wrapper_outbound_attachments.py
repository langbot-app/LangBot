"""Unit tests for ResponseWrapper outbound-attachment helpers.

Covers the sandbox -> user attachment path added for the Box attachment
round-trip:

* ``_is_final_assistant_message`` — only the terminal, tool-call-free assistant
  message (or a final MessageChunk) should trigger collection.
* ``_append_outbound_attachments`` — collects sandbox outbox files exactly once
  per query and maps each descriptor to the right platform component, swallowing
  collection errors.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message
import langbot_plugin.api.entities.builtin.provider.message as provider_message

from langbot.pkg.pipeline.wrapper.wrapper import ResponseWrapper


def _make_wrapper(box_service) -> ResponseWrapper:
    app = SimpleNamespace(logger=Mock())
    wrapper = ResponseWrapper.__new__(ResponseWrapper)
    wrapper.ap = app
    return wrapper


def _make_query():
    return SimpleNamespace(variables={})


def test_is_final_assistant_message_plain_assistant():
    wrapper = _make_wrapper(box_service=None)
    msg = provider_message.Message(role='assistant', content='done')
    assert wrapper._is_final_assistant_message(msg) is True


def test_is_final_assistant_message_rejects_non_assistant():
    wrapper = _make_wrapper(box_service=None)
    msg = provider_message.Message(role='tool', content='{}')
    assert wrapper._is_final_assistant_message(msg) is False


def test_is_final_assistant_message_rejects_tool_call_round():
    wrapper = _make_wrapper(box_service=None)
    msg = provider_message.Message(
        role='assistant',
        content='calling',
        tool_calls=[
            provider_message.ToolCall(
                id='c1',
                type='function',
                function=provider_message.FunctionCall(name='exec', arguments='{}'),
            )
        ],
    )
    assert wrapper._is_final_assistant_message(msg) is False


def test_is_final_assistant_message_non_final_chunk():
    wrapper = _make_wrapper(box_service=None)
    chunk = provider_message.MessageChunk(role='assistant', content='partial', is_final=False)
    assert wrapper._is_final_assistant_message(chunk) is False

    final_chunk = provider_message.MessageChunk(role='assistant', content='partial', is_final=True)
    assert wrapper._is_final_assistant_message(final_chunk) is True


@pytest.mark.asyncio
async def test_append_outbound_attachments_maps_each_type():
    box_service = SimpleNamespace(
        available=True,
        collect_outbound_attachments=AsyncMock(
            return_value=[
                {'type': 'Image', 'base64': 'data:image/png;base64,iVBORw0K'},
                {'type': 'Voice', 'base64': 'data:audio/wav;base64,UklGRg=='},
                {'type': 'File', 'name': 'report.xlsx', 'base64': 'data:app;base64,UEsDBA=='},
            ]
        ),
    )
    wrapper = _make_wrapper(box_service)
    wrapper.ap.box_service = box_service
    query = _make_query()
    chain = platform_message.MessageChain([])

    await wrapper._append_outbound_attachments(query, chain)

    kinds = [type(c).__name__ for c in chain]
    assert kinds == ['Image', 'Voice', 'File']
    assert query.variables['_sandbox_outbound_collected'] is True
    # File keeps its name
    file_comp = chain[2]
    assert getattr(file_comp, 'name', None) == 'report.xlsx'


@pytest.mark.asyncio
async def test_append_outbound_attachments_runs_once_per_query():
    box_service = SimpleNamespace(
        available=True,
        collect_outbound_attachments=AsyncMock(return_value=[]),
    )
    wrapper = _make_wrapper(box_service)
    wrapper.ap.box_service = box_service
    query = _make_query()
    query.variables['_sandbox_outbound_collected'] = True
    chain = platform_message.MessageChain([])

    await wrapper._append_outbound_attachments(query, chain)

    box_service.collect_outbound_attachments.assert_not_awaited()
    assert len(chain) == 0


@pytest.mark.asyncio
async def test_append_outbound_attachments_noop_without_box_service():
    wrapper = _make_wrapper(box_service=None)
    wrapper.ap.box_service = None
    query = _make_query()
    chain = platform_message.MessageChain([])

    await wrapper._append_outbound_attachments(query, chain)
    assert len(chain) == 0
    # not marked collected, since service is unavailable
    assert '_sandbox_outbound_collected' not in query.variables


@pytest.mark.asyncio
async def test_append_outbound_attachments_swallows_collection_error():
    box_service = SimpleNamespace(
        available=True,
        collect_outbound_attachments=AsyncMock(side_effect=RuntimeError('boom')),
    )
    wrapper = _make_wrapper(box_service)
    wrapper.ap.box_service = box_service
    query = _make_query()
    chain = platform_message.MessageChain([])

    # must not raise
    await wrapper._append_outbound_attachments(query, chain)
    assert len(chain) == 0
    wrapper.ap.logger.warning.assert_called_once()
