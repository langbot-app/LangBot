"""Message events with large inline media must still reach plugins (LANG-741).

A message event carries the platform chain twice (``message_chain`` and
``message_event.message_chain``). A ~6 MiB Lark file therefore produced a
Runtime message above the SDK's 16 MiB frame limit and the whole message
failed before any plugin or Runner saw it.
"""

from __future__ import annotations

import json
from unittest.mock import AsyncMock, Mock

import pytest

import langbot_plugin.api.entities.builtin.platform.message as platform_message
from langbot_plugin.api.entities.builtin.provider import session as provider_session
from langbot_plugin.api.entities import context
from langbot_plugin.api.entities.events import PersonMessageReceived
from langbot_plugin.runtime.io.connection import MAX_MESSAGE_BYTES
from langbot_plugin.runtime.io.connections.stdio import StdioConnection

from langbot.pkg.plugin.connector import _restore_inline_media, _shed_oversized_inline_media
from tests.factories.message import _base_query, friend_message_event, mock_adapter
from tests.unit_tests.plugin.test_connector_methods import (
    TEST_INSTALLATION_BINDING,
    configure_handler,
    create_mock_connector,
)


def _data_url(size: int) -> str:
    return 'data:application/pdf;base64,' + 'A' * size


def _file_query(file_b64_size: int, image_b64_size: int = 1024):
    chain = platform_message.MessageChain(
        [
            platform_message.Plain(text='see attached'),
            platform_message.File(name='big.pdf', size=file_b64_size, base64=_data_url(file_b64_size)),
            platform_message.Image(base64='data:image/png;base64,' + 'B' * image_b64_size),
        ]
    )
    return _base_query(
        message_chain=chain,
        message_event=friend_message_event(chain, 12345),
        launcher_type=provider_session.LauncherTypes.PERSON,
        launcher_id=12345,
        sender_id=12345,
        adapter=mock_adapter(),
    )


def _event(query):
    return PersonMessageReceived(
        query=query,
        launcher_type=query.launcher_type.value,
        launcher_id=query.launcher_id,
        sender_id=query.sender_id,
        message_event=query.message_event,
        message_chain=query.message_chain,
    )


class _Sink:
    def __init__(self):
        self.data = bytearray()

    def write(self, data: bytes) -> None:
        self.data.extend(data)

    async def drain(self) -> None:
        return None


async def _runtime_send(event_context: dict) -> None:
    """Push the payload through the SDK's real frame-size check."""
    conn = StdioConnection(Mock(), _Sink(), chunk_size=MAX_MESSAGE_BYTES * 2)
    await conn.send(json.dumps({'action': 'emit_event', 'data': {'event_context': event_context}}))


async def _emit(query):
    connector = create_mock_connector()
    connector._operation_bindings = AsyncMock(return_value=[TEST_INSTALLATION_BINDING])
    sent: list[dict] = []

    async def emit_event(event_context, include_plugins=None):
        await _runtime_send(event_context)
        sent.append(json.loads(json.dumps(event_context)))
        # The Runtime answers with its own deserialized copy.
        return {'event_context': json.loads(json.dumps(event_context)), 'emitted_plugins': []}

    runtime_handler = configure_handler(connector, Mock())
    runtime_handler.emit_event = AsyncMock(side_effect=emit_event)
    returned = await connector.emit_event(_event(query))
    return connector, sent, returned


@pytest.mark.asyncio
async def test_real_frame_check_rejects_unshed_payload():
    """Baseline: the SDK rejects a 9 MiB (base64) file event as it did in production."""
    query = _file_query(9 * 1024 * 1024)
    payload = context.EventContext.from_event(_event(query)).model_dump(serialize_as_any=False)
    with pytest.raises(ValueError, match='Runtime message exceeds'):
        await _runtime_send(payload)


@pytest.mark.asyncio
async def test_large_file_event_reaches_runtime_and_keeps_bytes_for_pipeline():
    size = 9 * 1024 * 1024
    query = _file_query(size)
    original_file_b64 = query.message_chain[1].base64
    original_image_b64 = query.message_chain[2].base64

    connector, sent, returned = await _emit(query)

    assert len(sent) == 1
    chains = [sent[0]['event']['message_chain'], sent[0]['event']['message_event']['message_chain']]
    for chain in chains:
        file_component = next(c for c in chain if c['type'] == 'File')
        assert file_component['base64'] == ''
        assert file_component['name'] == 'big.pdf'
        assert file_component['size'] == size
        # Small media still travel inline.
        image_component = next(c for c in chain if c['type'] == 'Image')
        assert image_component['base64'] == original_image_b64
    connector.ap.logger.warning.assert_called_once()

    # pipelinemgr writes the returned chain back into the Query; the Runner
    # must still receive the file bytes the plugins did not see.
    assert returned.event.message_chain[1].base64 == original_file_b64
    assert returned.event.message_chain[2].base64 == original_image_b64


@pytest.mark.asyncio
async def test_small_media_event_is_untouched():
    query = _file_query(256 * 1024)
    original = query.message_chain[1].base64

    connector, sent, returned = await _emit(query)

    assert sent[0]['event']['message_chain'][1]['base64'] == original
    connector.ap.logger.warning.assert_not_called()
    assert returned.event.message_chain[1].base64 == original


def test_shed_clears_largest_first_and_restore_skips_plugin_edits():
    payload = {
        'a': [{'type': 'File', 'name': 'big', 'base64': 'x' * 100}, {'type': 'Image', 'base64': 'y' * 10}],
        'b': {'type': 'Voice', 'base64': 'z' * 50},
    }
    cleared = _shed_oversized_inline_media(payload, budget=70)

    assert payload['a'][0]['base64'] == ''
    assert payload['b']['base64'] == 'z' * 50
    assert payload['a'][1]['base64'] == 'y' * 10
    assert len(cleared) == 1

    returned = json.loads(json.dumps(payload))
    # A plugin replaced this component with a different file: do not refill it.
    returned['a'][0]['name'] = 'replaced-by-plugin'
    _restore_inline_media(returned, cleared)
    assert returned['a'][0]['base64'] == ''

    untouched = json.loads(json.dumps(payload))
    _restore_inline_media(untouched, cleared)
    assert untouched['a'][0]['base64'] == 'x' * 100
