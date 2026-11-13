"""0047 -> head and restricted-role RLS, confined to a disposable schema."""

from __future__ import annotations

import hashlib
import os
import secrets
from types import SimpleNamespace
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.content import ContentAlias, ContentObject
from langbot.pkg.entity.persistence.skill import SkillRegistry, SkillVersion
from langbot.pkg.entity.persistence.workspace import Workspace
from langbot.pkg.persistence.alembic_runner import (
    get_alembic_current,
    get_alembic_head,
    run_alembic_stamp,
    run_alembic_upgrade,
)
from langbot.pkg.persistence.mgr import PersistenceManager, PersistenceMode


pytestmark = [
    pytest.mark.integration,
    pytest.mark.slow,
    pytest.mark.asyncio,
    pytest.mark.skill_persistence,
    pytest.mark.contract('skill_content_rls'),
]
_TABLES = ('content_objects', 'content_aliases', 'skill_registry', 'skill_versions')
_A = '00000000-0000-0000-0000-000000000001'
_B = '00000000-0000-0000-0000-000000000002'
_PUBLIC = 'media_cache/' + 'a' * 64 + '.png'
_OTHER_PUBLIC = 'media_cache/' + 'b' * 64 + '.png'


def _content(workspace, ref, *, public=False, key=None):
    value = ref.encode()
    return dict(
        ref=ref,
        workspace_uuid=workspace,
        public_media=public,
        public_key=key,
        owner_type='public_media' if public else 'skill',
        owner='probe',
        key=ref,
        digest=hashlib.sha256(value).hexdigest(),
        size=len(value),
        backend='database',
        value=value,
    )


@pytest.fixture
async def migrated_store():
    raw_url = os.environ.get('LANGBOT_PERSISTENCE_POSTGRES_URL')
    if not raw_url:
        pytest.skip('LANGBOT_PERSISTENCE_POSTGRES_URL not set')
    url = sa.engine.make_url(raw_url).set(drivername='postgresql+asyncpg')
    suffix = uuid.uuid4().hex[:16]
    schema, role = 'skill_content_' + suffix, 'skill_content_reader_' + suffix
    password = secrets.token_hex(24)
    admin = create_async_engine(url, isolation_level='AUTOCOMMIT')
    scoped_admin = restricted = None
    schema_created = role_created = False
    try:
        async with admin.connect() as conn:
            await conn.execute(sa.text(f'CREATE SCHEMA "{schema}"'))
            schema_created = True
            # Names and password contain only generated ASCII identifier/hex characters.
            await conn.execute(
                sa.text(
                    f'CREATE ROLE "{role}" LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS PASSWORD \'{password}\''
                )
            )
            role_created = True
        # Exclude public so Alembic can never discover/stamp another schema's version table.
        settings = {'server_settings': {'search_path': schema}}
        scoped_admin = create_async_engine(url, connect_args=settings)
        async with scoped_admin.begin() as conn:
            assert await conn.scalar(sa.text('SELECT current_schema()')) == schema
            # Create the preceding release's ORM tables only. The four new tables
            # must be introduced by Alembic, never by metadata.create_all.
            old_tables = [table for table in Base.metadata.sorted_tables if table.name not in _TABLES]
            await conn.run_sync(lambda sync: Base.metadata.create_all(sync, tables=old_tables))
            before = set(await conn.run_sync(lambda sync: sa.inspect(sync).get_table_names(schema=schema)))
            assert not before.intersection(_TABLES)
            await conn.execute(
                sa.insert(Workspace).values(
                    [
                        dict(uuid=_A, instance_uuid='test-instance', name='A', slug='a', source='cloud_projection'),
                        dict(uuid=_B, instance_uuid='test-instance', name='B', slug='b', source='cloud_projection'),
                    ]
                )
            )
        await run_alembic_stamp(scoped_admin, '0047_workspace_alerts')
        assert await get_alembic_current(scoped_admin) == '0047_workspace_alerts'
        await run_alembic_upgrade(scoped_admin, 'head')
        assert await get_alembic_current(scoped_admin) == get_alembic_head()
        async with scoped_admin.begin() as conn:
            after = set(await conn.run_sync(lambda sync: sa.inspect(sync).get_table_names(schema=schema)))
            assert set(_TABLES).issubset(after - before)
            flags = (
                await conn.execute(
                    sa.text(
                        'SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity '
                        'FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace '
                        'WHERE n.nspname=:schema AND c.relname = ANY(:tables)'
                    ),
                    {'schema': schema, 'tables': list(_TABLES)},
                )
            ).all()
            assert len(flags) == 4 and all(enabled and forced for _, enabled, forced in flags)
            rows = (
                (
                    await conn.execute(
                        sa.text(
                            'SELECT c.relname, p.polname, p.polcmd::text AS polcmd, '
                            'pg_get_expr(p.polqual,p.polrelid) AS using_expression, '
                            'pg_get_expr(p.polwithcheck,p.polrelid) AS check_expression '
                            'FROM pg_policy p JOIN pg_class c ON c.oid=p.polrelid '
                            'JOIN pg_namespace n ON n.oid=c.relnamespace '
                            'WHERE n.nspname=:schema AND c.relname = ANY(:tables)'
                        ),
                        {'schema': schema, 'tables': list(_TABLES)},
                    )
                )
                .mappings()
                .all()
            )
            actual = {table: {} for table in _TABLES}
            for row in rows:
                actual[row['relname']][row['polname']] = {
                    'command': row['polcmd'],
                    'using_expression': row['using_expression'],
                    'check_expression': row['check_expression'],
                }
            expected = PersistenceManager._expected_postgres_tenant_policies()
            assert actual == {table: expected[table] for table in _TABLES}
            await conn.execute(sa.text(f'GRANT USAGE ON SCHEMA "{schema}" TO "{role}"'))
            for table in _TABLES:
                await conn.execute(sa.text(f'GRANT SELECT, INSERT, UPDATE, DELETE ON "{schema}"."{table}" TO "{role}"'))

        restricted = create_async_engine(
            url.set(username=role, password=password), connect_args=settings, pool_size=1, max_overflow=0
        )
        manager = PersistenceManager(SimpleNamespace(), mode=PersistenceMode.CLOUD_RUNTIME)
        manager.db = SimpleNamespace(get_engine=lambda: restricted)
        async with restricted.connect() as conn:
            identity = (
                await conn.execute(
                    sa.text('SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname=current_user')
                )
            ).one()
            assert identity == (role, False, False)
        # Seed through the restricted connection, not a table owner bypass.
        for workspace, prefix in ((_A, 'a'), (_B, 'b')):
            async with manager.tenant_uow(workspace) as uow:
                await uow.execute(sa.insert(ContentObject).values(_content(workspace, prefix + '-private')))
                await uow.execute(
                    sa.insert(ContentObject).values(
                        _content(
                            workspace, prefix + '-public', public=True, key=_PUBLIC if prefix == 'a' else _OTHER_PUBLIC
                        )
                    )
                )
                await uow.execute(
                    sa.insert(ContentAlias).values(
                        workspace_uuid=workspace, key='alias', content_ref=prefix + '-private'
                    )
                )
                await uow.execute(
                    sa.insert(SkillRegistry).values(
                        uuid=str(uuid.uuid4()),
                        workspace_uuid=workspace,
                        instance_uuid='test-instance',
                        name='probe',
                        current_revision='sha256:' + prefix * 64,
                        skill_json={},
                    )
                )
                await uow.execute(
                    sa.insert(SkillVersion).values(
                        uuid=str(uuid.uuid4()),
                        workspace_uuid=workspace,
                        instance_uuid='test-instance',
                        name='probe',
                        revision='sha256:' + prefix * 64,
                        manifest_json={},
                        skill_json={},
                        content_ref=prefix + '-private',
                    )
                )
        # Same media-shaped public_key without publication must remain private.
        async with manager.tenant_uow(_B) as uow:
            await uow.execute(sa.insert(ContentObject).values(_content(_B, 'private-media-shape', key=_PUBLIC)))
        yield manager
    finally:
        if restricted is not None:
            await restricted.dispose()
        if scoped_admin is not None:
            await scoped_admin.dispose()
        try:
            async with admin.connect() as conn:
                if schema_created:
                    await conn.execute(sa.text(f'DROP SCHEMA "{schema}" CASCADE'))
                if role_created:
                    await conn.execute(sa.text(f'DROP ROLE "{role}"'))
        finally:
            await admin.dispose()


async def test_migrated_skill_content_rls_and_exact_public_media(migrated_store):
    manager = migrated_store
    for workspace, other in ((_A, _B), (_B, _A)):
        async with manager.tenant_uow(workspace) as uow:
            for model in (ContentObject, ContentAlias, SkillRegistry, SkillVersion):
                rows = (await uow.execute(sa.select(model.workspace_uuid))).scalars().all()
                assert rows and set(rows) == {workspace}
                assert (await uow.execute(sa.delete(model).where(model.workspace_uuid == other))).rowcount == 0
            assert (
                await uow.execute(
                    sa.update(SkillRegistry).where(SkillRegistry.workspace_uuid == other).values(name='forbidden')
                )
            ).rowcount == 0
            assert (
                await uow.execute(
                    sa.update(ContentObject).where(ContentObject.workspace_uuid == other).values(value=b'forbidden')
                )
            ).rowcount == 0
        with pytest.raises(sa.exc.DBAPIError):
            async with manager.tenant_uow(workspace) as uow:
                await uow.execute(sa.insert(ContentObject).values(_content(other, 'forbidden-insert')))

    # The workspace/ref composite FK blocks even an authorized row in Workspace A
    # from pointing at Workspace B's known content identifier.
    for model, values in (
        (ContentAlias, dict(workspace_uuid=_A, key='cross-reference', content_ref='b-private')),
        (
            SkillVersion,
            dict(
                uuid=str(uuid.uuid4()),
                workspace_uuid=_A,
                instance_uuid='test-instance',
                name='cross-reference',
                revision='sha256:' + 'c' * 64,
                manifest_json={},
                skill_json={},
                content_ref='b-private',
            ),
        ),
    ):
        with pytest.raises(sa.exc.IntegrityError):
            async with manager.tenant_uow(_A) as uow:
                await uow.execute(sa.insert(model).values(**values))
    with pytest.raises(sa.exc.IntegrityError):
        async with manager.tenant_uow(_A) as uow:
            await uow.execute(sa.delete(ContentObject).where(ContentObject.ref == 'a-private'))

    # Simulate an inherited OSS singleton connection setting: public-media scope
    # must explicitly clear it rather than combine public and tenant permissions.
    async with manager.get_db_engine().begin() as conn:
        await conn.execute(sa.text("SELECT set_config('langbot.workspace_uuid', :workspace, false)"), {'workspace': _B})
    async with manager.public_media_uow(_PUBLIC) as uow:
        rows = (await uow.execute(sa.select(ContentObject.ref, ContentObject.value))).all()
        assert rows == [('a-public', b'a-public')]
        for model in (ContentAlias, SkillRegistry, SkillVersion):
            assert (await uow.execute(sa.select(model.__table__))).all() == []
        assert (await uow.execute(sa.update(ContentObject).values(value=b'forbidden'))).rowcount == 0
        assert (await uow.execute(sa.delete(ContentObject))).rowcount == 0
    with pytest.raises(sa.exc.DBAPIError):
        async with manager.public_media_uow(_PUBLIC) as uow:
            await uow.execute(sa.insert(ContentObject).values(_content(_A, 'public-write', public=True, key=_PUBLIC)))
    async with manager.public_media_uow('media_cache/' + 'c' * 64 + '.png') as uow:
        assert (await uow.execute(sa.select(ContentObject.ref))).all() == []
