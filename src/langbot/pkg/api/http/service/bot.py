from __future__ import annotations

import uuid
import sqlalchemy

from ....core import app
from ....entity.persistence import bot as persistence_bot
from ....entity.persistence import pipeline as persistence_pipeline
from ....workspace.errors import WorkspaceNotFoundError
from .tenant import TenantContext, require_workspace_uuid, scope_statement


class BotService:
    """Bot service"""

    ap: app.Application

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    async def get_bots(self, context: TenantContext, include_secret: bool = False) -> list[dict]:
        """获取所有机器人"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(sqlalchemy.select(persistence_bot.Bot), persistence_bot.Bot, context)
        )

        bots = result.all()

        masked_columns = []
        if not include_secret:
            masked_columns = ['adapter_config']

        return [self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot, masked_columns) for bot in bots]

    async def get_bot(self, context: TenantContext, bot_uuid: str, include_secret: bool = False) -> dict | None:
        """获取机器人"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid),
                persistence_bot.Bot,
                context,
            )
        )

        bot = result.first()

        if bot is None:
            return None

        masked_columns = []
        if not include_secret:
            masked_columns = ['adapter_config']

        return self.ap.persistence_mgr.serialize_model(persistence_bot.Bot, bot, masked_columns)

    async def get_runtime_bot_info(
        self,
        context: TenantContext,
        bot_uuid: str,
        include_secret: bool = False,
    ) -> dict:
        """获取机器人运行时信息"""
        persistence_bot = await self.get_bot(context, bot_uuid, include_secret)
        if persistence_bot is None:
            raise WorkspaceNotFoundError('Bot not found')

        adapter_runtime_values = {}

        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(context, bot_uuid)
        if runtime_bot is not None:
            adapter_runtime_values['bot_account_id'] = runtime_bot.adapter.bot_account_id

        # Webhook URL for unified webhook adapters (independent of bot running state)
        if persistence_bot['adapter'] in [
            'wecom',
            'wecombot',
            'officialaccount',
            'qqofficial',
            'slack',
            'wecomcs',
            'LINE',
            'lark',
        ]:
            webhook_prefix = self.ap.instance_config.data['api'].get('webhook_prefix', 'http://127.0.0.1:5300')
            extra_webhook_prefix = self.ap.instance_config.data['api'].get('extra_webhook_prefix', '')
            webhook_url = f'/bots/{bot_uuid}'
            adapter_runtime_values['webhook_url'] = webhook_url
            adapter_runtime_values['webhook_full_url'] = f'{webhook_prefix}{webhook_url}'
            adapter_runtime_values['extra_webhook_full_url'] = (
                f'{extra_webhook_prefix}{webhook_url}' if extra_webhook_prefix else ''
            )
        else:
            adapter_runtime_values['webhook_url'] = None
            adapter_runtime_values['webhook_full_url'] = None
            adapter_runtime_values['extra_webhook_full_url'] = None

        persistence_bot['adapter_runtime_values'] = adapter_runtime_values

        return persistence_bot

    async def create_bot(self, context: TenantContext, bot_data: dict) -> str:
        """Create bot"""
        workspace_uuid = require_workspace_uuid(context)
        # Check limitation
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_bots = limitation.get('max_bots', -1)
        if max_bots >= 0:
            existing_bots = await self.get_bots(context)
            if len(existing_bots) >= max_bots:
                raise ValueError(f'Maximum number of bots ({max_bots}) reached')

        # TODO: 检查配置信息格式
        bot_data = bot_data.copy()
        bot_data['uuid'] = str(uuid.uuid4())
        bot_data['workspace_uuid'] = workspace_uuid

        # bind the most recently updated pipeline if any exist
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_pipeline.LegacyPipeline),
                persistence_pipeline.LegacyPipeline,
                context,
            )
            .order_by(persistence_pipeline.LegacyPipeline.updated_at.desc())
            .limit(1)
        )
        pipeline = result.first()
        if pipeline is not None:
            bot_data['use_pipeline_uuid'] = pipeline.uuid
            bot_data['use_pipeline_name'] = pipeline.name

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_bot.Bot).values(bot_data))

        bot = await self.get_bot(context, bot_data['uuid'], include_secret=True)

        await self.ap.platform_mgr.load_bot(context, bot)

        return bot_data['uuid']

    async def update_bot(self, context: TenantContext, bot_uuid: str, bot_data: dict) -> None:
        """Update bot"""
        workspace_uuid = require_workspace_uuid(context)
        update_data = bot_data.copy()

        update_data.pop('uuid', None)
        update_data.pop('workspace_uuid', None)

        # set use_pipeline_name
        if 'use_pipeline_uuid' in update_data:
            result = await self.ap.persistence_mgr.execute_async(
                scope_statement(
                    sqlalchemy.select(persistence_pipeline.LegacyPipeline).where(
                        persistence_pipeline.LegacyPipeline.uuid == update_data['use_pipeline_uuid']
                    ),
                    persistence_pipeline.LegacyPipeline,
                    workspace_uuid,
                )
            )
            pipeline = result.first()
            if pipeline is not None:
                update_data['use_pipeline_name'] = pipeline.name
            else:
                raise WorkspaceNotFoundError('Pipeline not found')

        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(persistence_bot.Bot).values(update_data).where(persistence_bot.Bot.uuid == bot_uuid),
                persistence_bot.Bot,
                workspace_uuid,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Bot not found')
        await self.ap.platform_mgr.remove_bot(context, bot_uuid)

        # select from db
        bot = await self.get_bot(context, bot_uuid, include_secret=True)

        runtime_bot = await self.ap.platform_mgr.load_bot(context, bot)

        if runtime_bot.enable:
            await runtime_bot.run()

        # update all conversation that use this bot
        for session in self.ap.sess_mgr.session_list:
            if (
                session.using_conversation is not None
                and session.using_conversation.bot_uuid == bot_uuid
                and getattr(session, 'workspace_uuid', workspace_uuid) == workspace_uuid
            ):
                session.using_conversation = None

    async def delete_bot(self, context: TenantContext, bot_uuid: str) -> None:
        """Delete bot"""
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(persistence_bot.Bot).where(persistence_bot.Bot.uuid == bot_uuid),
                persistence_bot.Bot,
                context,
            )
        )
        if getattr(result, 'rowcount', None) == 0:
            raise WorkspaceNotFoundError('Bot not found')
        await self.ap.platform_mgr.remove_bot(context, bot_uuid)

    async def list_event_logs(
        self, context: TenantContext, bot_uuid: str, from_index: int, max_count: int
    ) -> tuple[list[dict], int]:
        if await self.get_bot(context, bot_uuid, include_secret=False) is None:
            raise WorkspaceNotFoundError('Bot not found')
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(context, bot_uuid)
        if runtime_bot is None:
            raise Exception('Bot not found')

        logs, total_count = await runtime_bot.logger.get_logs(from_index, max_count)

        return [log.to_json() for log in logs], total_count

    async def send_message(
        self,
        context: TenantContext,
        bot_uuid: str,
        target_type: str,
        target_id: str,
        message_chain_data: dict,
    ) -> None:
        """Send message to a specific target via bot

        Args:
            bot_uuid: The UUID of the bot
            target_type: The type of the target, can be "group", "person"
            target_id: The ID of the target
            message_chain_data: The message chain data in dict format
        """
        if await self.get_bot(context, bot_uuid, include_secret=False) is None:
            raise WorkspaceNotFoundError('Bot not found')

        # Import here to avoid circular imports
        import langbot_plugin.api.entities.builtin.platform.message as platform_message

        # Get runtime bot
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(context, bot_uuid)
        if runtime_bot is None:
            raise Exception(f'Bot not found: {bot_uuid}')

        # Validate and convert message chain
        try:
            message_chain = platform_message.MessageChain.model_validate(message_chain_data)
        except Exception as e:
            raise Exception(f'Invalid message_chain format: {str(e)}')

        # Send message via adapter
        await runtime_bot.adapter.send_message(target_type, str(target_id), message_chain)

    # ============ Bot Admins ============

    async def get_bot_admins(self, context: TenantContext, bot_uuid: str) -> list[dict]:
        from ....entity.persistence import bot as persistence_bot

        if await self.get_bot(context, bot_uuid, include_secret=False) is None:
            raise WorkspaceNotFoundError('Bot not found')
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(persistence_bot.BotAdmin).where(persistence_bot.BotAdmin.bot_uuid == bot_uuid),
                persistence_bot.BotAdmin,
                context,
            )
        )
        return [{'id': r.id, 'launcher_type': r.launcher_type, 'launcher_id': r.launcher_id} for r in result.all()]

    async def add_bot_admin(self, context: TenantContext, bot_uuid: str, launcher_type: str, launcher_id: str) -> int:
        from ....entity.persistence import bot as persistence_bot

        workspace_uuid = require_workspace_uuid(context)
        if await self.get_bot(context, bot_uuid, include_secret=False) is None:
            raise WorkspaceNotFoundError('Bot not found')
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_bot.BotAdmin).values(
                workspace_uuid=workspace_uuid,
                bot_uuid=bot_uuid,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
            )
        )
        return result.inserted_primary_key[0]

    async def delete_bot_admin(self, context: TenantContext, bot_uuid: str, admin_id: int) -> None:
        from ....entity.persistence import bot as persistence_bot

        if await self.get_bot(context, bot_uuid, include_secret=False) is None:
            raise WorkspaceNotFoundError('Bot not found')
        await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.delete(persistence_bot.BotAdmin).where(
                    persistence_bot.BotAdmin.bot_uuid == bot_uuid,
                    persistence_bot.BotAdmin.id == admin_id,
                ),
                persistence_bot.BotAdmin,
                context,
            )
        )
