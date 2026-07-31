from __future__ import annotations

import logging
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity import persistence
from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.persistence.mgr import PersistenceManager
from langbot.pkg.persistence.alembic_runner import (
    get_alembic_head,
    get_alembic_current,
    run_alembic_downgrade,
    run_alembic_stamp,
    run_alembic_upgrade,
)
from langbot.pkg.utils import constants
from langbot.pkg.utils import importutil
from langbot.pkg.workspace.collaboration import normalize_email


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def _create_legacy_schema(
    engine,
    *,
    include_instance_uuid: bool = True,
    include_users: bool = True,
) -> None:
    legacy_metadata = sa.MetaData()
    metadata_table = sa.Table(
        'metadata',
        legacy_metadata,
        sa.Column('key', sa.String(255), primary_key=True),
        sa.Column('value', sa.String(255)),
    )
    users = sa.Table(
        'users',
        legacy_metadata,
        sa.Column('id', sa.Integer, primary_key=True),
        sa.Column('user', sa.String(255), nullable=False),
        sa.Column('password', sa.String(255), nullable=False),
        sa.Column('account_type', sa.String(32), nullable=False, server_default='local'),
        sa.Column('space_account_uuid', sa.String(255), nullable=True),
        sa.Column('space_access_token', sa.Text, nullable=True),
        sa.Column('space_refresh_token', sa.Text, nullable=True),
        sa.Column('space_access_token_expires_at', sa.DateTime, nullable=True),
        sa.Column('space_api_key', sa.String(255), nullable=True),
        sa.Column('created_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime, nullable=False, server_default=sa.func.now()),
    )
    async with engine.begin() as conn:
        await conn.run_sync(legacy_metadata.create_all)
        await conn.execute(metadata_table.insert().values(key='database_version', value='25'))
        if include_instance_uuid:
            await conn.execute(metadata_table.insert().values(key='instance_uuid', value='instance_migration_test'))
        if include_users:
            await conn.execute(
                users.insert(),
                [
                    {'user': 'owner@example.com', 'password': 'owner-hash'},
                    {'user': 'member@example.com', 'password': 'member-hash'},
                ],
            )


@pytest.fixture
async def legacy_engine(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "legacy-workspace.db"}')
    await _create_legacy_schema(engine)
    await run_alembic_stamp(engine, '0008_mcp_resource_prefs')
    yield engine
    await engine.dispose()


async def test_legacy_instance_gets_stable_accounts_and_default_workspace(legacy_engine):
    await run_alembic_upgrade(legacy_engine, 'head')

    async with legacy_engine.connect() as conn:
        tables = set(await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_table_names()))
        assert {
            'workspaces',
            'workspace_memberships',
            'workspace_invitations',
            'workspace_execution_states',
        }.issubset(tables)

        accounts = (
            (await conn.execute(sa.text('SELECT id, uuid, status, source, projection_revision FROM users ORDER BY id')))
            .mappings()
            .all()
        )
        assert len(accounts) == 2
        assert len({account['uuid'] for account in accounts}) == 2
        for account in accounts:
            uuid.UUID(account['uuid'])
            assert account['status'] == 'active'
            assert account['source'] == 'local'
            assert account['projection_revision'] == 0

        workspace = (
            (await conn.execute(sa.text('SELECT * FROM workspaces WHERE source = :source'), {'source': 'local'}))
            .mappings()
            .one()
        )
        assert workspace['instance_uuid'] == 'instance_migration_test'
        assert workspace['slug'] == 'default'
        assert workspace['status'] == 'active'
        assert workspace['created_by_account_uuid'] == accounts[0]['uuid']

        membership = (await conn.execute(sa.text('SELECT * FROM workspace_memberships'))).mappings().one()
        assert membership['workspace_uuid'] == workspace['uuid']
        assert membership['account_uuid'] == accounts[0]['uuid']
        assert membership['role'] == 'owner'
        assert membership['status'] == 'active'

        execution_state = (await conn.execute(sa.text('SELECT * FROM workspace_execution_states'))).mappings().one()
        assert execution_state['workspace_uuid'] == workspace['uuid']
        assert execution_state['instance_uuid'] == 'instance_migration_test'
        assert execution_state['active_generation'] == 1
        assert execution_state['state'] == 'active'
        assert execution_state['write_fenced'] in (False, 0)

    assert await get_alembic_current(legacy_engine) == get_alembic_head()


async def test_workspace_upgrade_is_idempotent_and_preserves_identifiers(legacy_engine):
    await run_alembic_upgrade(legacy_engine, 'head')
    async with legacy_engine.connect() as conn:
        account_uuids_before = (await conn.execute(sa.text('SELECT uuid FROM users ORDER BY id'))).scalars().all()
        workspace_uuid_before = (
            await conn.execute(sa.text("SELECT uuid FROM workspaces WHERE source = 'local'"))
        ).scalar_one()

    await run_alembic_upgrade(legacy_engine, 'head')

    async with legacy_engine.connect() as conn:
        account_uuids_after = (await conn.execute(sa.text('SELECT uuid FROM users ORDER BY id'))).scalars().all()
        workspace_uuid_after = (
            await conn.execute(sa.text("SELECT uuid FROM workspaces WHERE source = 'local'"))
        ).scalar_one()
    assert account_uuids_after == account_uuids_before
    assert workspace_uuid_after == workspace_uuid_before


async def test_workspace_kernel_upgrade_downgrade_upgrade_round_trip(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "workspace-round-trip.db"}')
    try:
        await _create_legacy_schema(engine)
        await run_alembic_stamp(engine, '0008_mcp_resource_prefs')
        await run_alembic_upgrade(engine, '0009_workspace_tenancy')
        assert await get_alembic_current(engine) == '0009_workspace_tenancy'

        await run_alembic_downgrade(engine, '0008_mcp_resource_prefs')
        assert await get_alembic_current(engine) == '0008_mcp_resource_prefs'
        async with engine.connect() as conn:
            tables = set(await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_table_names()))
            user_columns = {
                column['name']
                for column in await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_columns('users'))
            }
            accounts = (await conn.execute(sa.text('SELECT user, password FROM users ORDER BY id'))).all()
        assert (
            not {
                'workspaces',
                'workspace_memberships',
                'workspace_invitations',
                'workspace_execution_states',
            }
            & tables
        )
        assert not {'uuid', 'status', 'source', 'projection_revision'} & user_columns
        assert accounts == [
            ('owner@example.com', 'owner-hash'),
            ('member@example.com', 'member-hash'),
        ]

        await run_alembic_upgrade(engine, '0009_workspace_tenancy')
        assert await get_alembic_current(engine) == '0009_workspace_tenancy'
        async with engine.connect() as conn:
            assert await conn.scalar(sa.text('SELECT COUNT(*) FROM workspaces')) == 1
            assert await conn.scalar(sa.text('SELECT COUNT(*) FROM workspace_memberships')) == 1
    finally:
        await engine.dispose()


@pytest.mark.parametrize(
    ('raw_email', 'expected_email'),
    [
        ('Straße@Example.COM', 'strasse@example.com'),
        ('Ꭰ@Example.COM', 'Ꭰ@example.com'),
    ],
)
async def test_workspace_upgrade_uses_runtime_unicode_email_normalization(
    tmp_path,
    raw_email,
    expected_email,
):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "unicode-email.db"}')
    try:
        await _create_legacy_schema(engine, include_users=False)
        async with engine.begin() as conn:
            await conn.execute(
                sa.text('INSERT INTO users (user, password, account_type) VALUES (:email, :password, :type)'),
                {'email': raw_email, 'password': 'owner-hash', 'type': 'local'},
            )
        await run_alembic_stamp(engine, '0008_mcp_resource_prefs')
        await run_alembic_upgrade(engine, 'head')

        async with engine.connect() as conn:
            assert await conn.scalar(sa.text('SELECT normalized_email FROM users')) == expected_email
    finally:
        await engine.dispose()


async def test_fresh_sqlite_schema_accepts_application_casefold_identity(tmp_path):
    importutil.import_modules_in_pkg(persistence)
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "fresh-unicode-email.db"}')
    canonical_email = normalize_email('Ꭰ@Example.COM')
    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
            await conn.execute(
                sa.insert(User).values(
                    uuid='00000000-0000-0000-0000-000000000099',
                    user=canonical_email,
                    normalized_email=canonical_email,
                    password='hash',
                )
            )
        async with engine.connect() as conn:
            assert await conn.scalar(sa.select(User.normalized_email)) == 'Ꭰ@example.com'
    finally:
        await engine.dispose()


async def test_workspace_upgrade_rejects_unicode_casefold_duplicate_accounts(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "unicode-email-duplicate.db"}')
    try:
        await _create_legacy_schema(engine, include_users=False)
        async with engine.begin() as conn:
            await conn.execute(
                sa.text(
                    'INSERT INTO users (user, password, account_type) VALUES '
                    "('Straße@Example.COM', 'first-hash', 'local'), "
                    "('STRASSE@example.com', 'second-hash', 'local')"
                )
            )
        await run_alembic_stamp(engine, '0008_mcp_resource_prefs')
        with pytest.raises(RuntimeError, match='both normalize'):
            await run_alembic_upgrade(engine, 'head')
    finally:
        await engine.dispose()


async def test_uninitialized_instance_gets_ownerless_default_workspace(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "uninitialized-instance.db"}')
    try:
        await _create_legacy_schema(engine, include_users=False)
        await run_alembic_stamp(engine, '0008_mcp_resource_prefs')
        await run_alembic_upgrade(engine, 'head')

        async with engine.connect() as conn:
            workspace = (await conn.execute(sa.text('SELECT * FROM workspaces'))).mappings().one()
            membership_count = await conn.scalar(sa.text('SELECT COUNT(*) FROM workspace_memberships'))
            execution_state = (await conn.execute(sa.text('SELECT * FROM workspace_execution_states'))).mappings().one()

        assert workspace['created_by_account_uuid'] is None
        assert membership_count == 0
        assert execution_state['workspace_uuid'] == workspace['uuid']
        assert execution_state['active_generation'] == 1
    finally:
        await engine.dispose()


async def test_local_workspace_unique_index_allows_cloud_projections(legacy_engine):
    await run_alembic_upgrade(legacy_engine, 'head')

    async with legacy_engine.begin() as conn:
        await conn.execute(
            sa.text(
                'INSERT INTO workspaces '
                '(uuid, instance_uuid, name, slug, type, status, source, projection_revision) '
                'VALUES (:uuid, :instance_uuid, :name, :slug, :type, :status, :source, 0)'
            ),
            {
                'uuid': str(uuid.uuid4()),
                'instance_uuid': 'instance_migration_test',
                'name': 'Cloud Projection',
                'slug': 'cloud-projection',
                'type': 'team',
                'status': 'active',
                'source': 'cloud_projection',
            },
        )

    with pytest.raises(IntegrityError):
        async with legacy_engine.begin() as conn:
            await conn.execute(
                sa.text(
                    'INSERT INTO workspaces '
                    '(uuid, instance_uuid, name, slug, type, status, source, projection_revision) '
                    'VALUES (:uuid, :instance_uuid, :name, :slug, :type, :status, :source, 0)'
                ),
                {
                    'uuid': str(uuid.uuid4()),
                    'instance_uuid': 'instance_migration_test',
                    'name': 'Second Local',
                    'slug': 'second-local',
                    'type': 'team',
                    'status': 'active',
                    'source': 'local',
                },
            )


async def test_legacy_instance_without_bound_instance_uuid_fails_closed(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "missing-instance.db"}')
    try:
        await _create_legacy_schema(engine, include_instance_uuid=False)
        await run_alembic_stamp(engine, '0008_mcp_resource_prefs')
        with pytest.raises(RuntimeError, match='instance_uuid'):
            await run_alembic_upgrade(engine, 'head')
    finally:
        await engine.dispose()


async def test_persistence_startup_defers_workspace_tables_until_account_upgrade(tmp_path, monkeypatch):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "startup-order.db"}')
    try:
        await _create_legacy_schema(engine)
        await run_alembic_stamp(engine, '0008_mcp_resource_prefs')
        monkeypatch.setattr(constants, 'instance_id', 'instance_migration_test')

        database = type('Database', (), {'get_engine': lambda self: engine})()
        application = type('Application', (), {})()
        application.logger = logging.getLogger('workspace-startup-test')
        manager = PersistenceManager(application)
        manager.db = database

        await manager.create_tables()
        async with engine.connect() as conn:
            tables_before_migration = set(
                await conn.run_sync(lambda sync_conn: sa.inspect(sync_conn).get_table_names())
            )
        assert 'workspaces' not in tables_before_migration

        await manager._run_alembic_migrations()

        async with engine.connect() as conn:
            workspace = (
                (await conn.execute(sa.text("SELECT * FROM workspaces WHERE source = 'local'"))).mappings().one()
            )
        assert workspace['instance_uuid'] == 'instance_migration_test'
    finally:
        await engine.dispose()


async def test_persistence_startup_rejects_instance_uuid_drift(tmp_path, monkeypatch):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "instance-drift.db"}')
    try:
        await _create_legacy_schema(engine)
        monkeypatch.setattr(constants, 'instance_id', 'different_instance')

        database = type('Database', (), {'get_engine': lambda self: engine})()
        application = type('Application', (), {})()
        application.logger = logging.getLogger('workspace-instance-drift-test')
        manager = PersistenceManager(application)
        manager.db = database

        with pytest.raises(RuntimeError, match='does not match'):
            await manager.create_tables()
    finally:
        await engine.dispose()
