from __future__ import annotations

from types import SimpleNamespace

import pytest

from langbot.pkg.rag.service.runtime import RAGRuntimeService


class DummyStorageProvider:
    def __init__(self, content: bytes | None = b'data'):
        self.content = content
        self.loaded_paths: list[str] = []

    async def load(self, path: str):
        self.loaded_paths.append(path)
        return self.content


def make_service(storage_provider: DummyStorageProvider) -> RAGRuntimeService:
    return RAGRuntimeService(SimpleNamespace(storage_mgr=SimpleNamespace(storage_provider=storage_provider)))


@pytest.mark.asyncio
async def test_get_file_stream_normalizes_safe_path():
    storage_provider = DummyStorageProvider()
    service = make_service(storage_provider)

    content = await service.get_file_stream('safe/./nested/file.pdf')

    assert content == b'data'
    assert storage_provider.loaded_paths == ['safe/nested/file.pdf']


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'storage_path',
    [
        '',
        '../secret.txt',
        '/absolute/path.txt',
        '..\\secret.txt',
        'nested\\..\\secret.txt',
        '%2e%2e/secret.txt',
        'nested/%2e%2e/secret.txt',
        'C:\\secret.txt',
        'safe/\x00file.txt',
    ],
)
async def test_get_file_stream_rejects_unsafe_paths(storage_path: str):
    storage_provider = DummyStorageProvider()
    service = make_service(storage_provider)

    with pytest.raises(ValueError, match='Invalid storage path'):
        await service.get_file_stream(storage_path)

    assert storage_provider.loaded_paths == []


@pytest.mark.asyncio
async def test_get_file_stream_returns_empty_bytes_for_missing_content():
    storage_provider = DummyStorageProvider(content=None)
    service = make_service(storage_provider)

    content = await service.get_file_stream('safe/file.pdf')

    assert content == b''
    assert storage_provider.loaded_paths == ['safe/file.pdf']
