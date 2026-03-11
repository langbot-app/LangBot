import sqlalchemy
from .. import migration


@migration.migration_class(21)
class DBMigrateMonitoringUserName(migration.DBMigration):
    """Add user_name column to monitoring_sessions and monitoring_messages tables"""

    async def upgrade(self):
        # Add user_name column to monitoring_sessions table
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE monitoring_sessions ADD COLUMN user_name VARCHAR(255);')
            )
        except Exception:
            pass  # Column may already exist

        # Add user_name column to monitoring_messages table
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE monitoring_messages ADD COLUMN user_name VARCHAR(255);')
            )
        except Exception:
            pass  # Column may already exist

    async def downgrade(self):
        # SQLite does not support DROP COLUMN, so we skip downgrade for SQLite
        pass
