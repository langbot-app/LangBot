from __future__ import annotations

import sqlalchemy

from .. import migration


@migration.migration_class(25)
class DBMigrateKukuGroupSettings(migration.DBMigration):
    """Create KUKU group settings storage."""

    async def upgrade(self):
        """Upgrade"""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS kuku_group_settings (
                        uuid VARCHAR(255) PRIMARY KEY,
                        bot_uuid VARCHAR(255) NOT NULL,
                        platform VARCHAR(32) NOT NULL,
                        group_id VARCHAR(255) NOT NULL,
                        persona_id VARCHAR(255) NOT NULL,
                        silence_minutes INTEGER NOT NULL DEFAULT 30,
                        quiet_hours JSONB NOT NULL DEFAULT '{}'::jsonb,
                        cooldown_minutes INTEGER NOT NULL DEFAULT 10,
                        enabled BOOLEAN NOT NULL DEFAULT TRUE,
                        created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_kuku_group_settings_scope UNIQUE (bot_uuid, platform, group_id)
                    )
                """)
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'CREATE INDEX IF NOT EXISTS idx_kuku_group_settings_bot_uuid ON kuku_group_settings (bot_uuid)'
                )
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'CREATE INDEX IF NOT EXISTS idx_kuku_group_settings_group_id ON kuku_group_settings (group_id)'
                )
            )
        else:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("""
                    CREATE TABLE IF NOT EXISTS kuku_group_settings (
                        uuid VARCHAR(255) PRIMARY KEY,
                        bot_uuid VARCHAR(255) NOT NULL,
                        platform VARCHAR(32) NOT NULL,
                        group_id VARCHAR(255) NOT NULL,
                        persona_id VARCHAR(255) NOT NULL,
                        silence_minutes INTEGER NOT NULL DEFAULT 30,
                        quiet_hours JSON NOT NULL DEFAULT '{}',
                        cooldown_minutes INTEGER NOT NULL DEFAULT 10,
                        enabled BOOLEAN NOT NULL DEFAULT 1,
                        created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                        CONSTRAINT uq_kuku_group_settings_scope UNIQUE (bot_uuid, platform, group_id)
                    )
                """)
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'CREATE INDEX IF NOT EXISTS idx_kuku_group_settings_bot_uuid ON kuku_group_settings (bot_uuid)'
                )
            )
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'CREATE INDEX IF NOT EXISTS idx_kuku_group_settings_group_id ON kuku_group_settings (group_id)'
                )
            )

    async def downgrade(self):
        """Downgrade"""
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE IF EXISTS kuku_group_settings'))
