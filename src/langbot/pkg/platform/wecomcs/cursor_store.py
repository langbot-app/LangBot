from __future__ import annotations

import logging

import sqlalchemy

from ...entity.persistence import wecomcs as persistence_wecomcs
from .models import WecomCSCursorCheckpoint


_logger = logging.getLogger('langbot')


class WecomCSCursorStore:
    """Persist WeCom customer service cursor checkpoints in database."""

    def __init__(self, persistence_mgr = None):
        self.persistence_mgr = persistence_mgr

    def is_available(self) -> bool:
        return self.persistence_mgr is not None

    async def get_checkpoint(self, bot_uuid: str, open_kfid: str) -> WecomCSCursorCheckpoint | None:
        if not self.is_available():
            return None

        result = await self.persistence_mgr.execute_async(
            sqlalchemy.select(
                persistence_wecomcs.WecomCSCursorCheckpoint.id,
                persistence_wecomcs.WecomCSCursorCheckpoint.bot_uuid,
                persistence_wecomcs.WecomCSCursorCheckpoint.open_kfid,
                persistence_wecomcs.WecomCSCursorCheckpoint.cursor,
                persistence_wecomcs.WecomCSCursorCheckpoint.bootstrapped,
            )
            .where(persistence_wecomcs.WecomCSCursorCheckpoint.bot_uuid == bot_uuid)
            .where(persistence_wecomcs.WecomCSCursorCheckpoint.open_kfid == open_kfid)
        )
        row = result.mappings().one_or_none()
        if row is None:
            return None

        # 中文注释：AsyncConnection 执行 ORM select 时，不能用 scalar_one_or_none()，否则会拿到第一列 id。
        return WecomCSCursorCheckpoint(
            bot_uuid=str(row['bot_uuid']),
            open_kfid=str(row['open_kfid']),
            cursor=str(row['cursor'] or ''),
            bootstrapped=bool(row['bootstrapped']),
        )

    async def save_checkpoint(self, bot_uuid: str, open_kfid: str, cursor: str, bootstrapped: bool):
        if not self.is_available():
            return

        current = await self.get_checkpoint(bot_uuid, open_kfid)
        values = {
            'cursor': cursor,
            'bootstrapped': bootstrapped,
        }
        if current is None:
            await self.persistence_mgr.execute_async(
                sqlalchemy.insert(persistence_wecomcs.WecomCSCursorCheckpoint).values(
                    {
                        'bot_uuid': bot_uuid,
                        'open_kfid': open_kfid,
                        **values,
                    }
                )
            )
            _logger.debug(
                f'[wecomcs][cursor-store] 创建cursor检查点: bot_uuid={bot_uuid}, open_kfid={open_kfid}, bootstrapped={bootstrapped}, cursor={cursor}'
            )
            return

        await self.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_wecomcs.WecomCSCursorCheckpoint)
            .where(persistence_wecomcs.WecomCSCursorCheckpoint.bot_uuid == bot_uuid)
            .where(persistence_wecomcs.WecomCSCursorCheckpoint.open_kfid == open_kfid)
            .values(values)
        )
        _logger.debug(
            f'[wecomcs][cursor-store] 更新cursor检查点: bot_uuid={bot_uuid}, open_kfid={open_kfid}, bootstrapped={bootstrapped}, cursor={cursor}'
        )


    async def delete_checkpoint(self, bot_uuid: str, open_kfid: str):
        if not self.is_available():
            return

        await self.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_wecomcs.WecomCSCursorCheckpoint)
            .where(persistence_wecomcs.WecomCSCursorCheckpoint.bot_uuid == bot_uuid)
            .where(persistence_wecomcs.WecomCSCursorCheckpoint.open_kfid == open_kfid)
        )
        _logger.debug(
            f'[wecomcs][cursor-store] 删除cursor检查点: bot_uuid={bot_uuid}, open_kfid={open_kfid}'
        )
