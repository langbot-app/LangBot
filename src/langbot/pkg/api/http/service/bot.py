from __future__ import annotations

import uuid
import sqlalchemy
import typing

from ....core import app
from ....entity.persistence import bot as persistence_bot
from ....entity.persistence import pipeline as persistence_pipeline


class BotService:
    """Bot service"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_bots(self, include_secret: bool = True) -> list[dict]:
        """获取所有机器人"""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_bot.Bot))

        bots = result.all()

        masked_columns = []
        if not include_secret:
            masked_columns = ['adapter_config']

        return [self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot, masked_columns) for bot in bots]

    async def get_bot(self, bot_uuid: str, include_secret: bool = True) -> dict | None:
        """获取机器人"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid)
        )

        bot = result.first()

        if bot is None:
            return None

        masked_columns = []
        if not include_secret:
            masked_columns = ['adapter_config']

        return self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot, masked_columns)

    async def get_runtime_bot_info(self, bot_uuid: str, include_secret: bool = True) -> dict:
        """获取机器人运行时信息"""
        persistence_bot = await self.get_bot(bot_uuid, include_secret)
        if persistence_bot is None:
            raise Exception('Bot not found')

        adapter_runtime_values = {}

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is not None:
            adapter_runtime_values['bot_account_id'] = runtime_bot.adapter.bot_account_id

        persistence_bot['adapter_runtime_values'] = adapter_runtime_values

        return persistence_bot

    async def create_bot(self, bot_data: dict) -> str:
        """Create bot"""
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
        """Update bot"""
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

        # update all conversation that use this bot
        for session in self.ap.sess_mgr.session_list:
            if session.using_conversation is not None and session.using_conversation.bot_uuid == bot_uuid:
                session.using_conversation = None

    async def delete_bot(self, bot_uuid: str) -> None:
        """Delete bot"""
        await self.ap.platform_mgr.remove_bot(bot_uuid)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid)
        )

    async def list_event_logs(
        self, bot_uuid: str, from_index: int, max_count: int
    ) -> typing.Tuple[list[dict], int, int, int]:
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
        if runtime_bot is None:
            raise Exception('Bot not found')

        logs, total_count = await runtime_bot.logger.get_logs(from_index, max_count)

        return [log.to_json() for log in logs], total_count
