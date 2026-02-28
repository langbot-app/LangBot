import sqlalchemy
from .. import migration


@migration.migration_class(20)
class DBMigrateAPIChainModelAPILevel(migration.DBMigration):
    """Add model_name and api_key_index columns to api_chain_status for per-model/api-key health tracking"""

    async def upgrade(self):
        """Upgrade"""
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'ALTER TABLE api_chain_status ADD COLUMN model_name VARCHAR(255) DEFAULT NULL'
                )
            )
        except Exception:
            pass

        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'ALTER TABLE api_chain_status ADD COLUMN api_key_index INTEGER DEFAULT NULL'
                )
            )
        except Exception:
            pass

    async def downgrade(self):
        """Downgrade"""
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE api_chain_status DROP COLUMN model_name')
            )
        except Exception:
            pass

        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE api_chain_status DROP COLUMN api_key_index')
            )
        except Exception:
            pass
