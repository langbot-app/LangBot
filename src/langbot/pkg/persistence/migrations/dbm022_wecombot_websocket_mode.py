from .. import migration

import sqlalchemy
import json


@migration.migration_class(22)
class DBMigrateWecomBotWebSocketMode(migration.DBMigration):
    """Add enable-webhook field to existing wecombot adapter configs.

    Existing wecombot bots were all using webhook mode, so we set
    enable-webhook=true to preserve their behavior after the new
    WebSocket long connection mode is introduced as default.
    """

    async def upgrade(self):
        """Upgrade"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text("SELECT uuid, adapter_config FROM bots WHERE adapter = 'wecombot'")
        )
        bots = result.fetchall()

        for bot_row in bots:
            bot_uuid = bot_row[0]
            adapter_config = json.loads(bot_row[1]) if isinstance(bot_row[1], str) else bot_row[1]

            if 'enable-webhook' in adapter_config:
                continue

            # Determine mode based on existing config: if webhook fields are present, keep webhook mode
            has_webhook_config = bool(
                adapter_config.get('Token') and adapter_config.get('EncodingAESKey') and adapter_config.get('Corpid')
            )
            adapter_config['enable-webhook'] = has_webhook_config

            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('UPDATE bots SET adapter_config = :config::jsonb WHERE uuid = :uuid'),
                    {'config': json.dumps(adapter_config), 'uuid': bot_uuid},
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('UPDATE bots SET adapter_config = :config WHERE uuid = :uuid'),
                    {'config': json.dumps(adapter_config), 'uuid': bot_uuid},
                )

    async def downgrade(self):
        """Downgrade"""
        pass
