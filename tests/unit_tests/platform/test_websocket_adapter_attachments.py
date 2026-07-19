"""Unit tests for WebSocketAdapter._process_image_components.

The web debug client uploads Image / Voice / File components carrying a storage
key in ``path``. This helper resolves each to a base64 data URI (so multimodal
LLM input and the Box sandbox inbox have usable bytes), then deletes the
consumed storage object and clears ``path``. Covers mimetype selection per
type and fail-closed error handling.
"""

from __future__ import annotations

import base64
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.platform.sources.websocket_adapter import WebSocketAdapter


_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=1,
    pipeline_uuid='pipeline-a',
)
_UPLOAD_PREFIX = 'v1/instance-a/workspace-a/1/upload_image/'


def _make_connection():
    return SimpleNamespace(execution_context=_CONTEXT)


def _make_adapter(load_return=b'hello', load_side_effect=None):
    provider = Mock()
    provider.load = AsyncMock(return_value=load_return, side_effect=load_side_effect)
    storage_mgr = Mock()
    storage_mgr.storage_provider = provider
    storage_mgr.scoped_prefix.return_value = _UPLOAD_PREFIX
    storage_mgr.is_scoped_object_key.return_value = True
    storage_mgr.delete_scoped_object_key = AsyncMock()
    ap = Mock()
    ap.storage_mgr = storage_mgr
    logger = Mock()
    logger.error = AsyncMock()
    logger.warning = AsyncMock()
    # WebSocketAdapter is a pydantic model; bypass full __init__/validation.
    adapter = WebSocketAdapter.model_construct(ap=ap, logger=logger)
    return adapter, storage_mgr, provider


@pytest.mark.asyncio
async def test_image_jpeg_mimetype_and_cleanup():
    adapter, storage_mgr, _ = _make_adapter(load_return=b'\xff\xd8\xff')
    path = f'{_UPLOAD_PREFIX}photo.jpg'
    chain = [{'type': 'Image', 'path': path}]

    await adapter._process_image_components(_make_connection(), chain)

    expected_b64 = base64.b64encode(b'\xff\xd8\xff').decode('utf-8')
    assert chain[0]['base64'] == f'data:image/jpeg;base64,{expected_b64}'
    assert chain[0]['path'] == ''  # consumed
    storage_mgr.delete_scoped_object_key.assert_awaited_once_with(
        _CONTEXT,
        path,
        expected_owner_type='upload_image',
    )


@pytest.mark.asyncio
async def test_image_defaults_to_png():
    adapter, _, _ = _make_adapter()
    chain = [{'type': 'Image', 'path': f'{_UPLOAD_PREFIX}blob'}]
    await adapter._process_image_components(_make_connection(), chain)
    assert chain[0]['base64'].startswith('data:image/png;base64,')


@pytest.mark.asyncio
async def test_voice_uses_guessed_or_wav_mimetype():
    adapter, _, _ = _make_adapter()
    chain = [{'type': 'Voice', 'path': f'{_UPLOAD_PREFIX}clip.wav'}]
    await adapter._process_image_components(_make_connection(), chain)
    assert chain[0]['base64'].startswith('data:audio/')


@pytest.mark.asyncio
async def test_file_uses_octet_stream_fallback():
    adapter, _, _ = _make_adapter()
    chain = [{'type': 'File', 'path': f'{_UPLOAD_PREFIX}unknownblob'}]
    await adapter._process_image_components(_make_connection(), chain)
    assert chain[0]['base64'].startswith('data:application/octet-stream;base64,')


@pytest.mark.asyncio
async def test_skips_components_without_path_or_unknown_type():
    adapter, _, provider = _make_adapter()
    chain = [
        {'type': 'Image', 'path': ''},  # no path
        {'type': 'Plain', 'path': 'storage://abc/x'},  # not a file component
        {'type': 'At', 'target': '123'},  # no path key at all
    ]
    await adapter._process_image_components(_make_connection(), chain)
    provider.load.assert_not_awaited()
    assert 'base64' not in chain[0]
    assert 'base64' not in chain[1]


@pytest.mark.asyncio
async def test_load_failure_is_logged_and_aborts_processing():
    adapter, _, _ = _make_adapter(load_side_effect=RuntimeError('storage down'))
    chain = [{'type': 'File', 'path': f'{_UPLOAD_PREFIX}doc.pdf'}]

    with pytest.raises(RuntimeError, match='storage down'):
        await adapter._process_image_components(_make_connection(), chain)
    assert 'base64' not in chain[0]
    adapter.logger.error.assert_awaited_once()
