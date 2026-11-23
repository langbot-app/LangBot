from __future__ import annotations

import hashlib
import uuid

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.persistence.alembic_runner import (
    get_alembic_current,
    run_alembic_stamp,
    run_alembic_upgrade,
)


pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_legacy_plugin_settings_receive_stable_random_installation_identities(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "plugin-identity.db"}')
    metadata = sa.MetaData()
    plugin_settings = sa.Table(
        'plugin_settings',
        metadata,
        sa.Column('workspace_uuid', sa.String(36), primary_key=True),
        sa.Column('plugin_author', sa.String(255), primary_key=True),
        sa.Column('plugin_name', sa.String(255), primary_key=True),
        sa.Column('enabled', sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column('priority', sa.Integer, nullable=False, server_default='0'),
        sa.Column('config', sa.JSON, nullable=False, server_default='{}'),
        sa.Column('install_source', sa.String(255), nullable=False, server_default='local'),
        sa.Column('install_info', sa.JSON, nullable=False, server_default='{}'),
    )
    try:
        async with engine.begin() as connection:
            await connection.run_sync(metadata.create_all)
            await connection.execute(
                plugin_settings.insert(),
                [
                    {
                        'workspace_uuid': '11111111-1111-4111-8111-111111111111',
                        'plugin_author': 'author',
                        'plugin_name': 'one',
                    },
                    {
                        'workspace_uuid': '22222222-2222-4222-8222-222222222222',
                        'plugin_author': 'author',
                        'plugin_name': 'two',
                    },
                ],
            )
        await run_alembic_stamp(engine, '0011_postgres_tenant_rls')
        await run_alembic_upgrade(engine, '0012_plugin_identity')

        async with engine.connect() as connection:
            rows = (
                (
                    await connection.execute(
                        sa.text(
                            'SELECT installation_uuid, artifact_digest, runtime_revision '
                            'FROM plugin_settings ORDER BY workspace_uuid'
                        )
                    )
                )
                .mappings()
                .all()
            )
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column['name']: column for column in sa.inspect(sync_connection).get_columns('plugin_settings')
                }
            )
            indexes = await connection.run_sync(
                lambda sync_connection: {
                    index['name']: index for index in sa.inspect(sync_connection).get_indexes('plugin_settings')
                }
            )

        assert await get_alembic_current(engine) == '0012_plugin_identity'
        assert columns['installation_uuid']['nullable'] is False
        assert columns['artifact_digest']['nullable'] is False
        assert columns['runtime_revision']['nullable'] is False
        assert indexes['ix_plugin_settings_workspace_installation']['unique'] == 1
        assert len({row['installation_uuid'] for row in rows}) == 2
        for row in rows:
            uuid.UUID(row['installation_uuid'])
            assert row['runtime_revision'] == 1
            assert (
                row['artifact_digest']
                == hashlib.sha256(f'legacy-installation:{row["installation_uuid"]}'.encode()).hexdigest()
            )
    finally:
        await engine.dispose()
