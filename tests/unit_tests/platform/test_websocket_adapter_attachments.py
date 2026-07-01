"""Unit tests for WebSocketAdapter._process_image_components.

The web debug client uploads Image / Voice / File components carrying a storage
key in ``path``. This helper resolves each to a base64 data URI (so multimodal
LLM input and the Box sandbox inbox have usable bytes), then deletes the
consumed storage object and clears ``path``. Covers mimetype selection per
type and graceful error handling.
"""

from __future__ import annotations

import base64
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.platform.sources.websocket_adapter import WebSocketAdapter


def _make_adapter(load_return=b'hello', load_side_effect=None):
    provider = Mock()
    provider.load = AsyncMock(return_value=load_return, side_effect=load_side_effect)
    provider.delete = AsyncMock()
    ap = Mock()
    ap.storage_mgr.storage_provider = provider
    logger = Mock()
    logger.error = AsyncMock()
    # WebSocketAdapter is a pydantic model; bypass full __init__/validation.
    adapter = WebSocketAdapter.model_construct(ap=ap, logger=logger)
    return adapter, provider


@pytest.mark.asyncio
async def test_image_jpeg_mimetype_and_cleanup():
    adapter, provider = _make_adapter(load_return=b'\xff\xd8\xff')
    chain = [{'type': 'Image', 'path': 'storage://abc/photo.jpg'}]

    await adapter._process_image_components(chain)

    expected_b64 = base64.b64encode(b'\xff\xd8\xff').decode('utf-8')
    assert chain[0]['base64'] == f'data:image/jpeg;base64,{expected_b64}'
    assert chain[0]['path'] == ''  # consumed
    provider.delete.assert_awaited_once_with('storage://abc/photo.jpg')


@pytest.mark.asyncio
async def test_image_defaults_to_png():
    adapter, _ = _make_adapter()
    chain = [{'type': 'Image', 'path': 'storage://abc/blob'}]
    await adapter._process_image_components(chain)
    assert chain[0]['base64'].startswith('data:image/png;base64,')


@pytest.mark.asyncio
async def test_voice_uses_guessed_or_wav_mimetype():
    adapter, _ = _make_adapter()
    chain = [{'type': 'Voice', 'path': 'storage://abc/clip.wav'}]
    await adapter._process_image_components(chain)
    assert chain[0]['base64'].startswith('data:audio/')


@pytest.mark.asyncio
async def test_file_uses_octet_stream_fallback():
    adapter, _ = _make_adapter()
    chain = [{'type': 'File', 'path': 'storage://abc/unknownblob'}]
    await adapter._process_image_components(chain)
    assert chain[0]['base64'].startswith('data:application/octet-stream;base64,')


@pytest.mark.asyncio
async def test_skips_components_without_path_or_unknown_type():
    adapter, provider = _make_adapter()
    chain = [
        {'type': 'Image', 'path': ''},  # no path
        {'type': 'Plain', 'path': 'storage://abc/x'},  # not a file component
        {'type': 'At', 'target': '123'},  # no path key at all
    ]
    await adapter._process_image_components(chain)
    provider.load.assert_not_awaited()
    assert 'base64' not in chain[0]
    assert 'base64' not in chain[1]


@pytest.mark.asyncio
async def test_load_failure_is_logged_not_raised():
    adapter, _ = _make_adapter(load_side_effect=RuntimeError('storage down'))
    chain = [{'type': 'File', 'path': 'storage://abc/doc.pdf'}]

    # must not raise
    await adapter._process_image_components(chain)
    assert 'base64' not in chain[0]
    adapter.logger.error.assert_awaited_once()
