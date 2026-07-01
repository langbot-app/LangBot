from __future__ import annotations

import uuid
import sqlalchemy
import typing

from ....core import app
from ....discover import engine
from ....entity.persistence import agent as persistence_agent
from ....entity.persistence import bot as persistence_bot
from ....entity.persistence import pipeline as persistence_pipeline


class BotService:
    """Bot service"""

    ap: app.Application
    BOT_FIELDS = {
        'uuid',
        'name',
        'description',
        'adapter',
        'adapter_config',
        'enable',
        'event_bindings',
    }

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap

    def _get_adapter_component(self, adapter_name: str) -> engine.Component | None:
        """Return the discovered platform adapter component for an adapter name."""
        for component in self.ap.discover.get_components_by_kind('MessagePlatformAdapter'):
            if component.metadata.name == adapter_name:
                return component
        return None

    def _adapter_declares_webhook_url(self, adapter_name: str) -> bool:
        """Whether the adapter manifest declares a generated webhook URL config item."""
        component = self._get_adapter_component(adapter_name)
        if component is None:
            return False

        for config_item in component.spec.get('config', []):
            if config_item.get('type') == 'webhook-url':
                return True
        return False

    @staticmethod
    def _is_message_event_pattern(event_pattern: str) -> bool:
        return event_pattern == 'message.*' or event_pattern.startswith('message.')

    @staticmethod
    def _event_pattern_covers(supported_pattern: str, binding_pattern: str) -> bool:
        if supported_pattern == '*':
            return True
        if supported_pattern == binding_pattern:
            return True
        if binding_pattern == '*':
            return False
        if supported_pattern.endswith('.*'):
            namespace = supported_pattern[:-2]
            return binding_pattern == f'{namespace}.*' or binding_pattern.startswith(f'{namespace}.')
        return False

    @classmethod
    def _agent_supports_event_pattern(cls, supported_patterns: list[str] | None, event_pattern: str) -> bool:
        patterns = supported_patterns or ['*']
        return any(cls._event_pattern_covers(pattern, event_pattern) for pattern in patterns)

    async def _normalize_event_bindings(self, bindings: list[dict] | None) -> list[dict]:
        """Validate and normalize Bot event bindings."""
        if not bindings:
            return []

        normalized: list[dict] = []
        for index, raw_binding in enumerate(bindings):
            if not isinstance(raw_binding, dict):
                continue

            event_pattern = str(raw_binding.get('event_pattern') or '').strip()
            target_type = str(raw_binding.get('target_type') or '').strip()
            target_uuid = str(raw_binding.get('target_uuid') or '').strip()
            if not event_pattern or not target_type:
                continue

            if target_type == 'pipeline':
                if not self._is_message_event_pattern(event_pattern):
                    raise ValueError('Pipeline can only be bound to message events')
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(persistence_pipeline.LegacyPipeline.uuid).where(
                        persistence_pipeline.LegacyPipeline.uuid == target_uuid
                    )
                )
                if result.first() is None:
                    raise ValueError('Pipeline not found')
            elif target_type == 'agent':
                result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(persistence_agent.Agent).where(persistence_agent.Agent.uuid == target_uuid)
                )
                agent = result.first()
                if agent is None:
                    raise ValueError('Agent not found')
                if not self._agent_supports_event_pattern(agent.supported_event_patterns, event_pattern):
                    raise ValueError('Agent does not support this event pattern')
            elif target_type == 'discard':
                target_uuid = ''
            else:
                raise ValueError(f'Unsupported event binding target type: {target_type}')

            normalized.append(
                {
                    'id': raw_binding.get('id') or str(uuid.uuid4()),
                    'event_pattern': event_pattern,
                    'target_type': target_type,
                    'target_uuid': target_uuid,
                    'filters': raw_binding.get('filters') or [],
                    'priority': int(raw_binding.get('priority') or 0),
                    'enabled': bool(raw_binding.get('enabled', True)),
                    'description': raw_binding.get('description') or '',
                    'order': index,
                }
            )

        return normalized

    async def _prepare_bot_data(self, bot_data: dict, *, include_uuid: bool) -> dict:
        """Normalize Bot write payloads to the current event-routing model."""
        update_data = bot_data.copy()
        if not include_uuid:
            update_data.pop('uuid', None)

        update_data = {key: value for key, value in update_data.items() if key in self.BOT_FIELDS}
        if 'event_bindings' in update_data:
            update_data['event_bindings'] = await self._normalize_event_bindings(update_data.get('event_bindings'))
        return update_data

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

        # Webhook URL for adapters that declare a generated webhook config item.
        # This is manifest-driven so EBA adapters do not need to be mirrored in a
        # second hard-coded list.
        if self._adapter_declares_webhook_url(persistence_bot['adapter']):
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

    async def create_bot(self, bot_data: dict) -> str:
        """Create bot"""
        # Check limitation
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_bots = limitation.get('max_bots', -1)
        if max_bots >= 0:
            existing_bots = await self.get_bots()
            if len(existing_bots) >= max_bots:
                raise ValueError(f'Maximum number of bots ({max_bots}) reached')

        # TODO: 检查配置信息格式
        bot_data = await self._prepare_bot_data(bot_data, include_uuid=True)
        bot_data['uuid'] = str(uuid.uuid4())
        bot_data.setdefault('event_bindings', [])

        await self.ap.persistence_mgr.execute_async(sqlalchemy.insert(persistence_bot.Bot).values(bot_data))

        bot = await self.get_bot(bot_data['uuid'])

        await self.ap.platform_mgr.load_bot(bot)

        return bot_data['uuid']

    async def update_bot(self, bot_uuid: str, bot_data: dict) -> None:
        """Update bot"""
        update_data = await self._prepare_bot_data(bot_data, include_uuid=False)

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_bot.Bot).values(update_data).where(persistence_bot.Bot.uuid == bot_uuid)
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

    async def send_message(self, bot_uuid: str, target_type: str, target_id: str, message_chain_data: dict) -> None:
        """Send message to a specific target via bot

        Args:
            bot_uuid: The UUID of the bot
            target_type: The type of the target, can be "group", "person"
            target_id: The ID of the target
            message_chain_data: The message chain data in dict format
        """
        # Import here to avoid circular imports
        import langbot_plugin.api.entities.builtin.platform.message as platform_message

        # Get runtime bot
        runtime_bot = await self.ap.platform_mgr.get_bot_by_uuid(bot_uuid)
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

    async def get_bot_admins(self, bot_uuid: str) -> list[dict]:
        from ....entity.persistence import bot as persistence_bot

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_bot.BotAdmin).where(persistence_bot.BotAdmin.bot_uuid == bot_uuid)
        )
        return [{'id': r.id, 'launcher_type': r.launcher_type, 'launcher_id': r.launcher_id} for r in result.all()]

    async def add_bot_admin(self, bot_uuid: str, launcher_type: str, launcher_id: str) -> int:
        from ....entity.persistence import bot as persistence_bot

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_bot.BotAdmin).values(
                bot_uuid=bot_uuid,
                launcher_type=launcher_type,
                launcher_id=launcher_id,
            )
        )
        return result.inserted_primary_key[0]

    async def delete_bot_admin(self, bot_uuid: str, admin_id: int) -> None:
        from ....entity.persistence import bot as persistence_bot

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_bot.BotAdmin).where(
                persistence_bot.BotAdmin.bot_uuid == bot_uuid,
                persistence_bot.BotAdmin.id == admin_id,
            )
        )
