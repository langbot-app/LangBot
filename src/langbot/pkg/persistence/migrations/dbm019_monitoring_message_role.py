import sqlalchemy
from .. import migration


@migration.migration_class(19)
class DBMigrateMonitoringMessageRole(migration.DBMigration):
    """Add role column to monitoring_messages table"""

    async def upgrade(self):
        """Upgrade"""
        try:
            sql_text = sqlalchemy.text(
                "ALTER TABLE monitoring_messages ADD COLUMN role VARCHAR(50) DEFAULT 'user'"
            )
            await self.ap.persistence_mgr.execute_async(sql_text)
        except Exception:
            # Column may already exist
            pass

    async def downgrade(self):
        """Downgrade"""
        try:
            sql_text = sqlalchemy.text('ALTER TABLE monitoring_messages DROP COLUMN role')
            await self.ap.persistence_mgr.execute_async(sql_text)
        except Exception:
            pass
