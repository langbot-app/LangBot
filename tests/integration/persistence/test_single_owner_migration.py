from __future__ import annotations

import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceMembership
from langbot.pkg.persistence.alembic_runner import run_alembic_stamp, run_alembic_upgrade


@pytest.mark.asyncio
async def test_single_owner_migration_demotes_historical_extra_owner_and_installs_unique_index(tmp_path):
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "single-owner.db"}')
    try:
        async with engine.begin() as connection:
            await connection.run_sync(Base.metadata.create_all)
            await connection.execute(sa.text('DROP INDEX uq_workspace_memberships_one_active_owner'))

        session_factory = async_sessionmaker(engine, expire_on_commit=False)
        workspace_uuid = '00000000-0000-4000-8000-000000000001'
        creator_uuid = '00000000-0000-4000-8000-000000000010'
        promoted_uuid = '00000000-0000-4000-8000-000000000020'
        async with session_factory() as session:
            session.add_all(
                [
                    User(
                        uuid=creator_uuid,
                        user='creator@example.test',
                        normalized_email='creator@example.test',
                        password='hash',
                        account_type='local',
                    ),
                    User(
                        uuid=promoted_uuid,
                        user='promoted@example.test',
                        normalized_email='promoted@example.test',
                        password='hash',
                        account_type='local',
                    ),
                    Workspace(
                        uuid=workspace_uuid,
                        instance_uuid='instance-test',
                        name='Workspace',
                        slug='workspace',
                        type='team',
                        status='active',
                        source='local',
                        created_by_account_uuid=creator_uuid,
                    ),
                    WorkspaceMembership(
                        uuid='00000000-0000-4000-8000-000000000100',
                        workspace_uuid=workspace_uuid,
                        account_uuid=creator_uuid,
                        role='owner',
                        status='active',
                    ),
                    WorkspaceMembership(
                        uuid='00000000-0000-4000-8000-000000000200',
                        workspace_uuid=workspace_uuid,
                        account_uuid=promoted_uuid,
                        role='owner',
                        status='active',
                    ),
                ]
            )
            await session.commit()

        await run_alembic_stamp(engine, '0018_merge_launch_replay')
        await run_alembic_upgrade(engine, 'head')

        async with engine.connect() as connection:
            roles = dict(
                (
                    await connection.execute(
                        sa.text(
                            'SELECT account_uuid, role FROM workspace_memberships '
                            'WHERE workspace_uuid = :workspace_uuid ORDER BY account_uuid'
                        ),
                        {'workspace_uuid': workspace_uuid},
                    )
                ).all()
            )
            assert roles == {creator_uuid: 'owner', promoted_uuid: 'admin'}
            indexes = await connection.run_sync(
                lambda sync_connection: {
                    index['name'] for index in sa.inspect(sync_connection).get_indexes('workspace_memberships')
                }
            )
            assert 'uq_workspace_memberships_one_active_owner' in indexes

        with pytest.raises(sa.exc.IntegrityError):
            async with engine.begin() as connection:
                await connection.execute(
                    sa.text("UPDATE workspace_memberships SET role = 'owner' WHERE account_uuid = :account_uuid"),
                    {'account_uuid': promoted_uuid},
                )
    finally:
        await engine.dispose()
