import sqlalchemy

from .. import migration


@migration.migration_class(25)
class DBMigrateWecomCSCursorCheckpoint(migration.DBMigration):
    """Create wecomcs cursor checkpoint table."""

    async def upgrade(self):
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                '''
                CREATE TABLE IF NOT EXISTS wecomcs_cursor_checkpoints (
                    id INTEGER PRIMARY KEY,
                    bot_uuid VARCHAR(255) NOT NULL,
                    open_kfid VARCHAR(255) NOT NULL,
                    cursor TEXT NOT NULL DEFAULT '',
                    bootstrapped BOOLEAN NOT NULL DEFAULT 0,
                    created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
                )
                '''
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                'CREATE UNIQUE INDEX IF NOT EXISTS uq_wecomcs_cursor_bot_openkfid ON wecomcs_cursor_checkpoints(bot_uuid, open_kfid)'
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                'CREATE INDEX IF NOT EXISTS idx_wecomcs_cursor_bot_uuid ON wecomcs_cursor_checkpoints(bot_uuid)'
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                'CREATE INDEX IF NOT EXISTS idx_wecomcs_cursor_open_kfid ON wecomcs_cursor_checkpoints(open_kfid)'
            )
        )

    async def downgrade(self):
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('DROP TABLE IF EXISTS wecomcs_cursor_checkpoints')
            )
        except Exception:
            pass
