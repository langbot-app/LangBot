import pytest
import sqlalchemy
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.entity.persistence.base import Base
from langbot.pkg.entity.persistence.wecomcs import WecomCSCursorCheckpoint as PersistenceCheckpoint
from langbot.pkg.platform.wecomcs.cursor_store import WecomCSCursorStore


class FakePersistenceManager:
    def __init__(self, engine):
        self.engine = engine

    async def execute_async(self, *args, **kwargs):
        async with self.engine.connect() as conn:
            result = await conn.execute(*args, **kwargs)
            await conn.commit()
            return result


@pytest.mark.asyncio
async def test_cursor_store_returns_checkpoint_object_instead_of_scalar_id():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            sqlalchemy.insert(PersistenceCheckpoint).values(
                bot_uuid="bot-1",
                open_kfid="kf-1",
                cursor="cursor-1",
                bootstrapped=True,
            )
        )

    store = WecomCSCursorStore(FakePersistenceManager(engine))

    checkpoint = await store.get_checkpoint("bot-1", "kf-1")

    assert checkpoint is not None
    assert checkpoint.bot_uuid == "bot-1"
    assert checkpoint.open_kfid == "kf-1"
    assert checkpoint.cursor == "cursor-1"
    assert checkpoint.bootstrapped is True

    await engine.dispose()
