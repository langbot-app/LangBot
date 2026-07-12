"""Unit tests for LocalAgentRunner._inject_inbound_attachments.

Covers the user -> sandbox attachment path added for the Box attachment
round-trip:

* materialized descriptors are stashed on the query and described to the model
  via an appended text note (in-sandbox paths + outbox convention);
* non-image file parts (file_base64 / file_url) are stripped from the user
  message content because OpenAI-compatible chat models reject them, while
  image and text parts are kept for vision models;
* the helper is a no-op when the box service is unavailable or yields nothing,
  and never raises into the chat turn on materialization failure.
"""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.provider.message as provider_message

from langbot.pkg.provider.runners.localagent import LocalAgentRunner


def _make_runner(box_service) -> LocalAgentRunner:
    runner = LocalAgentRunner.__new__(LocalAgentRunner)
    runner.ap = SimpleNamespace(logger=Mock(), box_service=box_service)
    return runner


def _make_query():
    return SimpleNamespace(variables={}, query_id='q-123')


def _box_service(attachments):
    svc = SimpleNamespace(
        available=True,
        OUTBOX_MOUNT_DIR='/outbox',
        materialize_inbound_attachments=AsyncMock(return_value=attachments),
    )
    return svc


@pytest.mark.asyncio
async def test_inject_strips_file_parts_and_appends_note():
    box = _box_service([{'type': 'Voice', 'path': '/inbox/q-123/voice.wav', 'size': 176000}])
    runner = _make_runner(box)
    query = _make_query()
    user_message = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_text('transcribe this'),
            provider_message.ContentElement.from_file_base64('data:audio/wav;base64,AAAA', 'voice.wav'),
        ],
    )

    await runner._inject_inbound_attachments(query, user_message)

    types = [getattr(ce, 'type', None) for ce in user_message.content]
    # file_base64 dropped; text kept; sandbox-path note appended as text
    assert 'file_base64' not in types
    assert types.count('text') == 2
    note = user_message.content[-1].text
    assert '/inbox/q-123/voice.wav' in note
    assert '/outbox/q-123' in note
    # descriptors stashed for downstream stages
    assert query.variables['_sandbox_inbound_attachments'] == box.materialize_inbound_attachments.return_value


@pytest.mark.asyncio
async def test_inject_keeps_image_parts():
    box = _box_service([{'type': 'Image', 'path': '/inbox/q-123/pic.png', 'size': 1234}])
    runner = _make_runner(box)
    query = _make_query()
    user_message = provider_message.Message(
        role='user',
        content=[
            provider_message.ContentElement.from_text('what is this'),
            provider_message.ContentElement.from_image_base64('data:image/png;base64,iVBORw0K'),
        ],
    )

    await runner._inject_inbound_attachments(query, user_message)

    types = [getattr(ce, 'type', None) for ce in user_message.content]
    assert 'image_base64' in types  # vision part preserved
    assert types[-1] == 'text'  # note appended last


@pytest.mark.asyncio
async def test_inject_promotes_string_content_to_list_with_note():
    box = _box_service([{'type': 'File', 'path': '/inbox/q-123/data.csv', 'size': 42}])
    runner = _make_runner(box)
    query = _make_query()
    user_message = provider_message.Message(role='user', content='clean this csv')

    await runner._inject_inbound_attachments(query, user_message)

    assert isinstance(user_message.content, list)
    assert [getattr(ce, 'type', None) for ce in user_message.content] == ['text', 'text']
    assert user_message.content[0].text == 'clean this csv'
    assert '/inbox/q-123/data.csv' in user_message.content[1].text


@pytest.mark.asyncio
async def test_inject_noop_without_box_service():
    runner = _make_runner(box_service=None)
    query = _make_query()
    user_message = provider_message.Message(role='user', content='hello')

    await runner._inject_inbound_attachments(query, user_message)

    assert user_message.content == 'hello'
    assert '_sandbox_inbound_attachments' not in query.variables


@pytest.mark.asyncio
async def test_inject_noop_when_no_attachments():
    box = _box_service([])
    runner = _make_runner(box)
    query = _make_query()
    user_message = provider_message.Message(role='user', content='hello')

    await runner._inject_inbound_attachments(query, user_message)

    assert user_message.content == 'hello'
    assert '_sandbox_inbound_attachments' not in query.variables


@pytest.mark.asyncio
async def test_inject_swallows_materialization_error():
    box = SimpleNamespace(
        available=True,
        OUTBOX_MOUNT_DIR='/outbox',
        materialize_inbound_attachments=AsyncMock(side_effect=RuntimeError('disk full')),
    )
    runner = _make_runner(box)
    query = _make_query()
    user_message = provider_message.Message(role='user', content='hello')

    # must not raise
    await runner._inject_inbound_attachments(query, user_message)
    assert user_message.content == 'hello'
    runner.ap.logger.warning.assert_called_once()
