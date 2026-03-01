import sqlalchemy
from .. import migration


@migration.migration_class(20)
class DBMigrateMonitoringSessionUserName(migration.DBMigration):
    """Add user_name column to monitoring_sessions table"""

    async def upgrade(self):
        """Upgrade"""
        try:
            sql_text = sqlalchemy.text('ALTER TABLE monitoring_sessions ADD COLUMN user_name VARCHAR(255)')
            await self.ap.persistence_mgr.execute_async(sql_text)
        except Exception:
            # Column may already exist
            pass

    async def downgrade(self):
        """Downgrade"""
        try:
            sql_text = sqlalchemy.text('ALTER TABLE monitoring_sessions DROP COLUMN user_name')
            await self.ap.persistence_mgr.execute_async(sql_text)
        except Exception:
            pass
