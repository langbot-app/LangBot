"""Real embedded storage behavior through the lazy manager; tenant checks have a separate suite."""

from types import SimpleNamespace
from unittest.mock import AsyncMock
import logging

import pytest

from langbot.pkg.core import app as _app  # noqa: F401 - Load Core before backend modules.
from langbot.pkg.vector.mgr import VectorDBManager
from langbot.pkg.vector.vdbs import chroma

pytestmark = pytest.mark.integration


@pytest.mark.asyncio
async def test_lazy_chroma_write_search_list_and_delete(tmp_path, monkeypatch):
    factory = chroma.ChromaVectorDatabase
    created = []

    def create(ap):
        backend = factory(ap, base_path=str(tmp_path / 'chroma'))
        created.append(backend)
        return backend

    monkeypatch.setattr(chroma, 'ChromaVectorDatabase', create)
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={'vdb': {'use': 'chroma'}}),
        logger=logging.getLogger(__name__),
    )
    manager = VectorDBManager(ap)
    monkeypatch.setattr(manager, '_resolve_physical_collection_name', AsyncMock(return_value='lazy-regression'))
    context = SimpleNamespace(instance_uuid='instance', workspace_uuid='workspace')
    assert manager.vector_db is None
    try:
        await manager.upsert(
            context,
            'kb',
            [[1.0, 0.0], [0.0, 1.0]],
            ['one', 'two'],
            [{'file_id': 'file-one', 'user_key': 'owner-a'}, {'file_id': 'file-two', 'user_key': 'owner-b'}],
            ['alpha sentinel', 'beta sentinel'],
        )
        assert len(created) == 1
        results = await manager.search(context, 'kb', [1.0, 0.0], 2, filter={'file_id': 'file-one'})
        assert [row['id'] for row in results] == ['one']
        results = await manager.search(context, 'kb', [0.0, 1.0], 2, filter={'user_key': 'owner-b'})
        assert [row['id'] for row in results] == ['two']
        results = await manager.search(context, 'kb', [], 2, search_type='full_text', query_text='alpha')
        assert [row['id'] for row in results] == ['one']
        results = await manager.search(context, 'kb', [1.0, 0.0], 2, search_type='hybrid', query_text='alpha')
        assert results[0]['id'] == 'one'
        items, total = await manager.list_by_filter(context, 'kb')
        assert total == 2 and {item['id'] for item in items} == {'one', 'two'}
        await manager.delete_by_file_id(context, 'kb', ['file-one'])
        items, total = await manager.list_by_filter(context, 'kb')
        assert total == 1 and items[0]['id'] == 'two'
        await manager.delete_by_filter(context, 'kb', {'file_id': 'file-two'})
        assert (await manager.list_by_filter(context, 'kb')) == ([], 0)
        await manager.delete_collection(context, 'kb')
        assert created[0].client.list_collections() == []
        assert len(created) == 1
    finally:
        await manager.shutdown()
    assert manager.vector_db is None
