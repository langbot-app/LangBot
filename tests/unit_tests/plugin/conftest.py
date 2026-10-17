"""Database fixture for plugin persistence behavior tests."""

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.bstorage import BinaryStorage
from langbot.pkg.entity.persistence.plugin import PluginSetting
from langbot.pkg.entity.persistence.user import User
from langbot.pkg.entity.persistence.workspace import Workspace


@pytest.fixture
async def plugin_db():
    engine = create_async_engine('sqlite+aiosqlite:///:memory:')
    try:
        async with engine.begin() as connection:
            await connection.execute(text('PRAGMA foreign_keys=ON'))
            await connection.run_sync(
                Base.metadata.create_all,
                tables=[User.__table__, Workspace.__table__, PluginSetting.__table__, BinaryStorage.__table__],
            )
        async with AsyncSession(engine, expire_on_commit=False) as session:
            session.add_all(
                Workspace(
                    uuid=workspace,
                    instance_uuid='instance-a',
                    name=workspace,
                    slug=workspace,
                    source='cloud_projection',
                )
                for workspace in ('workspace-a', 'workspace-b')
            )
            await session.flush()
            yield session
    finally:
        await engine.dispose()
