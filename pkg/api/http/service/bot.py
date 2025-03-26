from __future__ import annotations

import uuid
import datetime
import sqlalchemy

from ....core import app
from ....entity.persistence import bot as persistence_bot


class BotService:
    """机器人服务"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_bots(self) -> list[dict]:
        """获取所有机器人"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_bot.Bot)
        )

        bots = result.all()

        return [
            self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot)
            for bot in bots
        ]
    
    async def get_bot(self, bot_uuid: str) -> dict | None:
        """获取机器人"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid)
        )
        
        bot = result.first()

        if bot is None:
            return None

        return self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot)

    async def create_bot(self, bot_data: dict) -> str:
        """创建机器人"""
        bot_data['uuid'] = str(uuid.uuid4())
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_bot.Bot).values(bot_data)
        )
        # TODO: 加载机器人到机器人管理器
        return bot_data['uuid']

    async def update_bot(self, bot_uuid: str, bot_data: dict) -> None:
        """更新机器人"""
        if 'uuid' in bot_data:
            del bot_data['uuid']
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_bot.Bot).values(bot_data).where(persistence_bot.Bot.uuid == bot_uuid)
        )
        # TODO: 加载机器人到机器人管理器

    async def delete_bot(self, bot_uuid: str) -> None:
        """删除机器人"""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid)
        )
        # TODO: 从机器人管理器中删除机器人


