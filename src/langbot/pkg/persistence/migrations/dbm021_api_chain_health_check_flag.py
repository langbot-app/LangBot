import sqlalchemy
from .. import migration


@migration.migration_class(21)
class DBMigrateAPIChainHealthCheckFlag(migration.DBMigration):
    """Add health_check_last_failed column to api_chain_status"""

    async def upgrade(self):
        """Upgrade"""
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'ALTER TABLE api_chain_status ADD COLUMN health_check_last_failed BOOLEAN NOT NULL DEFAULT 0'
                )
            )
        except Exception:
            pass

    async def downgrade(self):
        """Downgrade"""
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE api_chain_status DROP COLUMN health_check_last_failed')
            )
        except Exception:
            pass
