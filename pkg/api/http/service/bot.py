from __future__ import annotations

import uuid
import sqlalchemy

from ....core import app
from ....entity.persistence import bot as persistence_bot
from ....entity.persistence import pipeline as persistence_pipeline


class BotService:
    """机器人服务"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_bots(self) -> list[dict]:
        """获取所有机器人"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_bot.Bot))

        bots = result.all()

        return [self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot) for bot in bots]

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
        # TODO: 检查配置信息格式
        bot_data['uuid'] = str(uuid.uuid4())

        # checkout the default pipeline
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                persistence_pipeline.LegacyPipeline.is_default == True
            )
        )
        pipeline = result.first()
        if pipeline is not None:
            bot_data['use_pipeline_uuid'] = pipeline.uuid
            bot_data['use_pipeline_name'] = pipeline.name

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_bot.Bot).values(bot_data))

        bot = await self.get_bot(bot_data['uuid'])

        await self.ap.platform_mgr.load_bot(bot)

        return bot_data['uuid']

    async def update_bot(self, bot_uuid: str, bot_data: dict) -> None:
        """更新机器人"""
        if 'uuid' in bot_data:
            del bot_data['uuid']

        # set use_pipeline_name
        if 'use_pipeline_uuid' in bot_data:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                    persistence_pipeline.LegacyPipeline.uuid == bot_data['use_pipeline_uuid']
                )
            )
            pipeline = result.first()
            if pipeline is not None:
                bot_data['use_pipeline_name'] = pipeline.name
            else:
                raise Exception('Pipeline not found')

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_bot.Bot).values(bot_data).where(persistence_bot.Bot.uuid == bot_uuid)
        )
        await self.ap.platform_mgr.remove_bot(bot_uuid)

        # select from db
        bot = await self.get_bot(bot_uuid)

        runtime_bot = await self.ap.platform_mgr.load_bot(bot)

        if runtime_bot.enable:
            await runtime_bot.run()

    async def delete_bot(self, bot_uuid: str) -> None:
        """删除机器人"""
        await self.ap.platform_mgr.remove_bot(bot_uuid)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid)
        )
