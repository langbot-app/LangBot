"""Real database transactions for persistent content and scoped aliases."""

import asyncio
from dataclasses import replace
import hashlib
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.entity.persistence.content import ContentAlias, ContentObject
from langbot.pkg.entity.persistence.artifact import Artifact, ArtifactReference
from langbot.pkg.entity.persistence.skill import SkillVersion
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode
from langbot.pkg.persistence.tenant_uow import TenantScopeRequiredError
from langbot.pkg.storage.mgr import StorageMgr
from langbot.pkg.api.http.authz import WorkspaceRequiredError


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
    assert await store.get(context(), ref, max_bytes=7) == b'payload'
    with pytest.raises(ValueError, match='size limit'):
        await store.get(context(), ref, max_bytes=2)
    async with storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
        await uow.execute(sa.update(ContentObject).where(ContentObject.ref == ref).values(value=b'changed'))
    with pytest.raises(ValueError, match='digest'):
        await store.get(context(), ref)


@pytest.mark.asyncio
async def test_content_metadata_is_scoped_and_does_not_load_the_body(storage, monkeypatch):
    store = storage.content_store
    body = b'x' * (2 * 1024 * 1024)
    ref = await store.put(context(), owner_type='skill', owner='packet', key='revision', value=body)
    monkeypatch.setattr(store, '_read', AsyncMock(side_effect=AssertionError('metadata loaded the content body')))
    assert await store.metadata(context(), ref) == {'size': len(body), 'digest': hashlib.sha256(body).hexdigest()}
    assert await store.size(context(), ref) == len(body)
    with pytest.raises(FileNotFoundError):
        await store.metadata(context(OTHER), ref)
    with pytest.raises(FileNotFoundError):
        await store.metadata(context(), 'invalid-ref')
    with pytest.raises(WorkspaceRequiredError):
        await store.metadata(replace(context(), placement_generation=2), ref)
    store._read.assert_not_awaited()


@pytest.mark.asyncio
async def test_s3_metadata_does_not_contact_the_source_backend(storage, monkeypatch):
    store = storage.content_store
    provider = SimpleNamespace(save=AsyncMock(), delete=AsyncMock())
    monkeypatch.setattr(store, '_s3', AsyncMock(return_value=(provider, {'key': 'archive-location'})))
    storage.ap.instance_config.data['storage']['content'] = {'backend': 'archive'}
    ref = await store.put(context(), owner_type='skill', owner='packet', key='revision', value=b'archive')
    store._s3.reset_mock()
    store._s3.side_effect = RuntimeError('source backend unavailable')
    assert await store.metadata(context(), ref) == {'size': 7, 'digest': hashlib.sha256(b'archive').hexdigest()}
    store._s3.assert_not_awaited()
    with pytest.raises(RuntimeError, match='source backend unavailable'):
        await store.get(context(), ref)


@pytest.mark.asyncio
async def test_database_package_metadata_retains_revision_scope_without_archive_io(storage, tmp_path, monkeypatch):
    from langbot.pkg.entity.persistence.skill import SkillVersion
    from langbot.pkg.skill.repository import SkillRepository

    storage.ap.storage_mgr = storage
    engine = storage.ap.persistence_mgr.get_db_engine()
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: SkillVersion.__table__.create(sync))
    body = b'x' * (2 * 1024 * 1024)
    manifest = {'algorithm': 'sha256-tree-v1', 'files': [], 'total_bytes': 0}
    revision = (
        'sha256:' + hashlib.sha256(json.dumps(manifest, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    )
    ref = await storage.content_store.put(context(), owner_type='skill', owner='packet', key=revision, value=body)
    async with storage.ap.persistence_mgr.tenant_uow(WORKSPACE) as uow:
        await uow.execute(
            sa.insert(SkillVersion).values(
                uuid='version-one',
                workspace_uuid=WORKSPACE,
                instance_uuid='instance',
                name='packet',
                revision=revision,
                manifest_json=manifest,
                skill_json={'name': 'packet', 'revision': revision},
                content_ref=ref,
            )
        )
    archive_read = AsyncMock(wraps=storage.content_store.get)
    monkeypatch.setattr(storage.content_store, 'get', archive_read)
    manager = storage.ap.persistence_mgr
    bindings, begins, content_columns = [], [], []
    generation = [1]
    workspaces = sa.Table('workspaces', sa.MetaData(), sa.Column('uuid', sa.String(36)))

    async def binding(workspace, *, expected_generation):
        bindings.append((workspace, expected_generation))
        async with manager.tenant_uow(workspace) as uow:
            await uow.execute(sa.select(workspaces.c.uuid).where(workspaces.c.uuid == workspace))
        return SimpleNamespace(instance_uuid='instance', workspace_uuid=workspace, placement_generation=generation[0])

    def began(connection):
        begins.append(connection)

    def selected(connection, cursor, statement, parameters, execution_context, executemany):
        compiled = execution_context.compiled
        if compiled is not None and isinstance(compiled.statement, sa.sql.Select):
            columns = compiled.statement.selected_columns
            fields = [column.name for column in columns if getattr(column.table, 'name', None) == 'content_objects']
            if fields:
                content_columns.append(fields)

    storage.ap.workspace_service.get_execution_binding = binding
    storage.ap.instance_config.data['skills'] = {'persistence': 'database', 'root': str(tmp_path / 'cache')}
    skills = SkillRepository(storage.ap)
    repository = skills._database
    sa.event.listen(engine.sync_engine, 'begin', began)
    sa.event.listen(engine.sync_engine, 'before_cursor_execute', selected)
    try:
        package = await skills.get_skill_package(context(), 'packet', revision, metadata_only=True)
    finally:
        sa.event.remove(engine.sync_engine, 'begin', began)
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', selected)
    assert len(begins) == 2
    assert bindings == [(WORKSPACE, 1), (WORKSPACE, 1)]
    assert content_columns and all(
        {'size', 'digest'} <= set(fields) and 'value' not in fields for fields in content_columns
    )
    assert package == {
        'revision': revision,
        'manifest': manifest,
        'size': len(body),
        'sha256': hashlib.sha256(body).hexdigest(),
        'filename': 'packet.zip',
    }
    archive_read.assert_not_awaited()
    for foreign in (context(OTHER), replace(context(), instance_uuid='other-instance')):
        with pytest.raises(ValueError, match='pinned revision'):
            await repository.get_package(foreign, 'packet', revision, metadata_only=True)
    full = await repository.get_package(context(), 'packet', revision)
    assert full == {**package, 'content': body}
    archive_read.assert_awaited_once()
    original_record = repository._record

    async def record_then_cutover(*args, **kwargs):
        result = await original_record(*args, **kwargs)
        generation[0] = 2
        return result

    monkeypatch.setattr(repository, '_record', record_then_cutover)
    with pytest.raises(WorkspaceRequiredError):
        await skills.get_skill_package(context(), 'packet', revision, metadata_only=True)
    assert manager.current_session() is None


@pytest.mark.asyncio
@pytest.mark.parametrize('operation', ['list_skill_resources', 'read_skill_resource'])
async def test_network_resource_reads_share_short_transactions_and_keep_validation(
    storage, tmp_path, monkeypatch, operation
):
    from langbot_plugin.skill_store import SkillStore

    from langbot.pkg.entity.persistence.skill import SkillVersion
    from langbot.pkg.skill.repository import SkillRepository

    if not callable(getattr(SkillStore, 'list_publication_manifest_resources', None)):
        pytest.skip('requires publication resource SDK')
    published = SkillStore(str(tmp_path / 'published'))
    skill = published.create_skill({'name': 'packet', 'description': 'Read guide', 'instructions': 'Use resources.'})
    skill = published.write_skill_file(
        'packet', 'references/guide.md', 'verified guide', base_revision=skill['revision']
    )
    publication = published.export_skill_publication('packet', skill['revision'])
    store = storage.content_store
    manager = storage.ap.persistence_mgr
    engine = manager.get_db_engine()
    async with engine.begin() as connection:
        await connection.run_sync(lambda sync: SkillVersion.__table__.create(sync))
    objects = {}
    loads = []

    async def save(key, value):
        objects[key] = value

    async def load(key, *, max_bytes):
        assert manager.current_session() is None, 'Object storage IO retained a database transaction'
        loads.append(key)
        assert len(objects[key]) <= max_bytes
        return objects[key]

    provider = SimpleNamespace(save=save, delete=AsyncMock(), load_bounded=load)
    monkeypatch.setattr(store, '_s3', AsyncMock(return_value=(provider, {})))
    storage.ap.instance_config.data['storage']['content'] = {'backend': 'archive'}
    ref = await store.put(
        context(), owner_type='skill', owner='packet', key=skill['revision'], value=publication['file_bytes']
    )
    async with manager.tenant_uow(WORKSPACE) as uow:
        await uow.execute(
            sa.insert(SkillVersion).values(
                uuid='version-one',
                workspace_uuid=WORKSPACE,
                instance_uuid='instance',
                name='packet',
                revision=skill['revision'],
                manifest_json=publication['manifest'],
                skill_json=publication['skill'],
                content_ref=ref,
            )
        )
    storage.ap.storage_mgr = storage
    storage.ap.box_service = SimpleNamespace(file_transfer_mode='network')
    storage.ap.instance_config.data['skills'] = {'persistence': 'database', 'root': str(tmp_path / 'cache')}
    bindings = []
    generation = [1]
    workspaces = sa.Table('workspaces', sa.MetaData(), sa.Column('uuid', sa.String(36)))

    async def binding(workspace, *, expected_generation):
        bindings.append((workspace, expected_generation))
        async with manager.tenant_uow(workspace) as uow:
            await uow.execute(sa.select(workspaces.c.uuid).where(workspaces.c.uuid == workspace))
        return SimpleNamespace(instance_uuid='instance', workspace_uuid=workspace, placement_generation=generation[0])

    storage.ap.workspace_service.get_execution_binding = binding
    repository = SkillRepository(storage.ap)
    begins, content_queries = [], []

    def began(connection):
        begins.append(connection)

    def selected(connection, cursor, statement, parameters, execution_context, executemany):
        compiled = execution_context.compiled
        if compiled is not None and isinstance(compiled.statement, sa.sql.Select):
            if any(
                getattr(column.table, 'name', None) == 'content_objects'
                for column in compiled.statement.selected_columns
            ):
                content_queries.append([column.name for column in compiled.statement.selected_columns])

    path = 'references' if operation == 'list_skill_resources' else 'references/guide.md'
    read = getattr(repository, operation)
    sa.event.listen(engine.sync_engine, 'begin', began)
    sa.event.listen(engine.sync_engine, 'before_cursor_execute', selected)
    try:
        result = await read(context(), 'packet', path, expected_revision=skill['revision'])
    finally:
        sa.event.remove(engine.sync_engine, 'begin', began)
        sa.event.remove(engine.sync_engine, 'before_cursor_execute', selected)
    assert len(begins) == 1
    assert bindings == [(WORKSPACE, 1), (WORKSPACE, 1)]
    assert result['revision'] == skill['revision']
    if operation == 'list_skill_resources':
        assert [entry['name'] for entry in result['entries']] == ['guide.md']
        assert not content_queries and not loads
    else:
        assert result['content'] == 'verified guide'
        assert content_queries and len(loads) == 1
        content_queries.clear()
        sa.event.listen(engine.sync_engine, 'before_cursor_execute', selected)
        try:
            assert await read(context(), 'packet', path, expected_revision=skill['revision']) == result
        finally:
            sa.event.remove(engine.sync_engine, 'before_cursor_execute', selected)
        assert content_queries == [['size', 'digest']]
        assert len(loads) == 1
    key = next(iter(objects))
    original = objects[key]
    objects[key] = original[:-1] + bytes([original[-1] ^ 1])
    if operation == 'list_skill_resources':
        assert await read(context(), 'packet', path, expected_revision=skill['revision']) == result
        store._s3.side_effect = RuntimeError('source backend unavailable')
        assert await read(context(), 'packet', path, expected_revision=skill['revision']) == result
        assert not loads
        store._s3.side_effect = None
    else:
        assert await read(context(), 'packet', path, expected_revision=skill['revision']) == result
        store._s3.side_effect = RuntimeError('source backend unavailable')
        assert await read(context(), 'packet', path, expected_revision=skill['revision']) == result
        store._s3.side_effect = None
        cache_key = ('instance', WORKSPACE, ref)
        repository._database._discard_resource_archive(cache_key)
        with pytest.raises(ValueError, match='digest verification'):
            await read(context(), 'packet', path, expected_revision=skill['revision'])
    objects[key] = original
    assert await read(context(), 'packet', path, expected_revision=skill['revision']) == result
    before = len(loads)
    for foreign in (context(OTHER), replace(context(), instance_uuid='other-instance')):
        with pytest.raises(ValueError, match='pinned revision|stale Workspace'):
            await read(foreign, 'packet', path, expected_revision=skill['revision'])
    with pytest.raises(ValueError, match='pinned revision'):
        await read(context(), 'packet', path, expected_revision='sha256:' + '0' * 64)
    assert len(loads) == before
    original_record = repository._database._record

    if operation == 'list_skill_resources':

        async def bad_record(*args, **kwargs):
            result = await original_record(*args, **kwargs)
            return {**result, **invalid}

        monkeypatch.setattr(repository._database, '_record', bad_record)
        invalid = {'content_ref': 'invalid-ref'}
        with pytest.raises(FileNotFoundError, match='content reference'):
            await read(context(), 'packet', path, expected_revision=skill['revision'])
        invalid = {'manifest': {**publication['manifest'], 'total_bytes': 0}}
        with pytest.raises(ValueError):
            await read(context(), 'packet', path, expected_revision=skill['revision'])
        assert len(loads) == before

    async def record_then_cutover(*args, **kwargs):
        result = await original_record(*args, **kwargs)
        generation[0] = 2
        return result

    monkeypatch.setattr(repository._database, '_record', record_then_cutover)
    before = len(loads)
    with pytest.raises(WorkspaceRequiredError):
        await read(context(), 'packet', path, expected_revision=skill['revision'])
    assert len(loads) == before
    with pytest.raises(ValueError, match='stale Workspace'):
        await read(context(), 'packet', path, expected_revision=skill['revision'])
    assert len(loads) == before
    assert manager.current_session() is None


@pytest.mark.asyncio
async def test_scoped_alias_replaces_content_without_mutating_previous_ref(storage):
    # Only this alias-lifecycle case needs the Artifact holder schema. Keep the
    # shared minimal content fixture compatible with downstream Skill fixtures.
    async with storage.ap.persistence_mgr.get_db_engine().begin() as connection:
        for table in (SkillVersion.__table__, Artifact.__table__, ArtifactReference.__table__):
            await connection.run_sync(lambda sync, table=table: table.create(sync))
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
