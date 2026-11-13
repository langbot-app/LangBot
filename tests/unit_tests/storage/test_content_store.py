"""Real database transactions for persistent content and scoped aliases."""

import asyncio
import hashlib
import logging
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence.content import ContentAlias, ContentObject
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import TenantScopeRequiredError
from langbot.pkg.storage.mgr import StorageMgr


WORKSPACE = '00000000-0000-0000-0000-000000000001'
OTHER = '00000000-0000-0000-0000-000000000002'


def context(workspace=WORKSPACE):
    return ExecutionContext(instance_uuid='instance', workspace_uuid=workspace, placement_generation=1)


@pytest.fixture
async def storage(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "content.db"}')

    @sa.event.listens_for(engine.sync_engine, 'connect')
    def foreign_keys(connection, _record):
        cursor = connection.cursor()
        cursor.execute('PRAGMA foreign_keys=ON')
        cursor.close()

    async def binding(workspace, expected_generation=None):
        assert expected_generation == 1
        return SimpleNamespace(instance_uuid='instance', workspace_uuid=workspace, placement_generation=1)

    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={'storage': {'use': 'persistent'}}),
        workspace_service=SimpleNamespace(instance_uuid='instance', get_execution_binding=binding),
        logger=logging.getLogger(__name__),
    )
    ap.persistence_mgr = PersistenceManager(ap, mode=PersistenceMode.CLOUD_RUNTIME)
    ap.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
    async with engine.begin() as connection:
        workspaces = sa.Table('workspaces', sa.MetaData(), sa.Column('uuid', sa.String(36), primary_key=True))
        await connection.run_sync(lambda sync: workspaces.create(sync))
        await connection.execute(sa.insert(workspaces).values([{'uuid': WORKSPACE}, {'uuid': OTHER}]))
        await connection.run_sync(lambda sync: ContentObject.__table__.create(sync))
        await connection.run_sync(lambda sync: ContentAlias.__table__.create(sync))
    manager = StorageMgr(ap)
    try:
        yield manager
    finally:
        await manager.content_store.shutdown()
        await engine.dispose()


@pytest.mark.asyncio
async def test_content_joins_caller_transaction_and_is_workspace_scoped(storage):
    store = storage.content_store
    with pytest.raises(RuntimeError, match='abort publication'):
        async with storage.ap.persistence_mgr.tenant_uow(WORKSPACE):
            discarded = await store.put(context(), owner_type='skill', owner='one', key='rev1', value=b'failed')
            assert await store.get(context(), discarded) == b'failed'
            raise RuntimeError('abort publication')
    with pytest.raises(FileNotFoundError):
        await store.get(context(), discarded)
    ref = await store.put(context(), owner_type='skill', owner='one', key='rev1', value=b'committed')
    assert ref == await store.put(context(), owner_type='skill', owner='one', key='rev1', value=b'committed')
    assert await store.get(context(), ref) == b'committed'
    with pytest.raises(FileNotFoundError):
        await store.get(context(OTHER), ref)
    with pytest.raises(FileNotFoundError):
        await store.delete(context(OTHER), ref)
    assert await store.get(context(), ref) == b'committed'


@pytest.mark.asyncio
async def test_content_checks_read_limits_and_digest(storage):
    store = storage.content_store
    ref = await store.put(context(), owner_type='skill', owner='one', key='rev1', value=b'payload')
    with pytest.raises(ValueError, match='size limit'):
        await store.get(context(), ref, max_bytes=2)
    async with storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
        await uow.execute(sa.update(ContentObject).where(ContentObject.ref == ref).values(value=b'changed'))
    with pytest.raises(ValueError, match='digest'):
        await store.get(context(), ref)


@pytest.mark.asyncio
async def test_scoped_alias_replaces_content_without_mutating_previous_ref(storage):
    kwargs = dict(owner_type='upload_image', owner='account', key='same.png')
    key = await storage.save_scoped(context(), **kwargs, value=b'first')
    old_ref = await storage.content_store.alias_ref(context(), key)
    assert await storage.save_scoped(context(), **kwargs, value=b'second') == key
    assert await storage.load_scoped(context(), **kwargs) == b'second'
    assert await storage.content_store.get(context(), old_ref) == b'first'
    current_ref = await storage.content_store.alias_ref(context(), key)
    with pytest.raises(sa.exc.IntegrityError):
        await storage.content_store.delete(context(), current_ref)
    assert await storage.resolve_public_object(key, expected_owner_type='upload_image') == b'second'
    await storage.delete_scoped(context(), **kwargs)
    with pytest.raises(FileNotFoundError):
        await storage.load_scoped(context(), **kwargs)


@pytest.mark.asyncio
async def test_public_media_requires_trusted_write_scope_and_cannot_read_private_content(storage):
    store = storage.content_store
    key = 'media_cache/' + hashlib.sha256(b'image').hexdigest() + '.png'
    with pytest.raises(TenantScopeRequiredError):
        await store.save_public_media(key, b'image')
    private = await store.put(context(), owner_type='skill', owner='one', key=key, value=b'secret')
    assert await store.get_public_media(key) is None
    with pytest.raises(ValueError):
        await store.get_public_media(private)
    async with storage.ap.persistence_mgr.tenant_uow(WORKSPACE):
        await store.save_public_media(key, b'image')
    assert await store.get_public_media(key) == b'image'


@pytest.mark.asyncio
async def test_s3_rollback_removes_only_this_attempt_and_history_uses_saved_backend(storage, monkeypatch):
    store = storage.content_store
    objects = {}

    class ObjectProvider:
        async def save(self, key, value):
            objects[key] = value

        async def delete(self, key):
            objects.pop(key, None)

        async def load_bounded(self, key, *, max_bytes):
            assert len(objects[key]) <= max_bytes
            return objects[key]

    provider = ObjectProvider()
    observed = []

    async def backend(name, locator=None):
        observed.append(name)
        assert name == 'archive'
        return provider, {'endpoint_url': 'https://archive.invalid', 'bucket': 'old', 'region': 'one'}

    monkeypatch.setattr(store, '_s3', backend)
    storage.ap.instance_config.data['storage']['content'] = {'backend': 'archive'}
    kept = await store.put(context(), owner_type='skill', owner='one', key='kept', value=b'keep')
    with pytest.raises(RuntimeError):
        async with storage.ap.persistence_mgr.tenant_uow(WORKSPACE):
            await store.put(context(), owner_type='skill', owner='one', key='failed', value=b'rollback')
            raise RuntimeError('rollback')
    await asyncio.sleep(0)
    await asyncio.sleep(0)
    if store._cleanup_tasks:
        await asyncio.gather(*store._cleanup_tasks)
    assert list(objects.values()) == [b'keep']
    storage.ap.instance_config.data['storage']['content']['backend'] = 'database'
    assert await store.get(context(), kept) == b'keep'
    assert observed[-1] == 'archive'
