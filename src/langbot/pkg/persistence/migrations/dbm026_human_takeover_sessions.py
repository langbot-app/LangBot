import sqlalchemy
from .. import migration


@migration.migration_class(26)
class DBMigrateHumanTakeoverSessions(migration.DBMigration):
    """Create human_takeover_sessions table for human operator takeover support"""

    async def upgrade(self):
        sql_text = sqlalchemy.text("""
            CREATE TABLE IF NOT EXISTS human_takeover_sessions (
                id VARCHAR(255) PRIMARY KEY,
                session_id VARCHAR(255) NOT NULL UNIQUE,
                bot_uuid VARCHAR(255) NOT NULL,
                status VARCHAR(50) NOT NULL DEFAULT 'active',
                taken_by VARCHAR(255),
                taken_at DATETIME NOT NULL,
                released_at DATETIME,
                platform VARCHAR(255),
                user_id VARCHAR(255),
                user_name VARCHAR(255)
            )
        """)
        await self.ap.persistence_mgr.execute_async(sql_text)

        # Create indexes
        for idx_sql in [
            'CREATE INDEX IF NOT EXISTS idx_hts_session_id ON human_takeover_sessions (session_id)',
            'CREATE INDEX IF NOT EXISTS idx_hts_bot_uuid ON human_takeover_sessions (bot_uuid)',
            'CREATE INDEX IF NOT EXISTS idx_hts_status ON human_takeover_sessions (status)',
        ]:
            await self.ap.persistence_mgr.execute_async(sqlalchemy.text(idx_sql))

    async def downgrade(self):
        sql_text = sqlalchemy.text('DROP TABLE IF EXISTS human_takeover_sessions')
        await self.ap.persistence_mgr.execute_async(sql_text)
