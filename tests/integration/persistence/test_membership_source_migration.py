from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.persistence.alembic_runner import run_alembic_stamp, run_alembic_upgrade


@pytest.mark.asyncio
async def test_membership_source_migration_backfills_existing_rows_as_local_and_enforces_constraint(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "membership-source.db"}')
    try:
        async with engine.begin() as connection:
            await connection.execute(
                sa.text(
                    """
                    CREATE TABLE workspace_memberships (
                        uuid VARCHAR(36) PRIMARY KEY,
                        workspace_uuid VARCHAR(36) NOT NULL,
                        account_uuid VARCHAR(36) NOT NULL,
                        role VARCHAR(32) NOT NULL,
                        status VARCHAR(32) NOT NULL,
                        projection_revision BIGINT NOT NULL DEFAULT 0,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                    )
                    """
                )
            )
            await connection.execute(
                sa.text(
                    """
                    INSERT INTO workspace_memberships
                        (uuid, workspace_uuid, account_uuid, role, status, projection_revision)
                    VALUES
                        ('00000000-0000-4000-8000-000000000001', 'workspace', 'local-account',
                         'viewer', 'active', 0),
                        ('00000000-0000-4000-8000-000000000002', 'workspace', 'cloud-account',
                         'viewer', 'active', 0)
                    """
                )
            )

        await run_alembic_stamp(engine, '0019_single_workspace_owner')
        await run_alembic_upgrade(engine, 'head')

        async with engine.connect() as connection:
            rows = (
                await connection.execute(sa.text('SELECT uuid, source FROM workspace_memberships ORDER BY uuid'))
            ).all()
            columns = await connection.run_sync(
                lambda sync_connection: {
                    column['name']: column
                    for column in sa.inspect(sync_connection).get_columns('workspace_memberships')
                }
            )
        assert rows == [
            ('00000000-0000-4000-8000-000000000001', 'local'),
            ('00000000-0000-4000-8000-000000000002', 'local'),
        ]
        assert columns['source']['nullable'] is False

        with pytest.raises(sa.exc.IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    sa.text("UPDATE workspace_memberships SET source = 'guessed-from-user-source'")
                )
    finally:
        await engine.dispose()
