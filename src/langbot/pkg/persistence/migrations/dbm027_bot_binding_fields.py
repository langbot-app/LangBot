"""Add binding_uuid field to bots table and migrate data"""
import sqlalchemy
from .. import migration


@migration.migration_class(27)
class DBMigrateBotBindingFields(migration.DBMigration):
    """Add binding_uuid field to bots table and migrate existing data"""

    async def upgrade(self):
        # Add binding_uuid column to bots table
        # Check if column exists first (SQLite doesn't support IF NOT EXISTS for columns)
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("SELECT binding_uuid FROM bots LIMIT 1")
            )
        except Exception:
            # Column doesn't exist, add it
            await self.ap.persistence_mgr.execute_async(sqlalchemy.text(
                "ALTER TABLE bots ADD COLUMN binding_uuid VARCHAR(64)"
            ))

        # Migrate existing data: copy use_pipeline_uuid to binding_uuid for records
        # that have a pipeline bound and binding_uuid is not set yet
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            UPDATE bots
            SET binding_uuid = use_pipeline_uuid
            WHERE use_pipeline_uuid IS NOT NULL
              AND use_pipeline_uuid != ''
              AND (binding_uuid IS NULL OR binding_uuid = '')
        """))

        # Ensure binding_type is 'pipeline' for records that were migrated
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text("""
            UPDATE bots
            SET binding_type = 'pipeline'
            WHERE binding_uuid IS NOT NULL
              AND binding_uuid != ''
              AND (binding_type IS NULL OR binding_type = '')
        """))

    async def downgrade(self):
        # SQLite doesn't support DROP COLUMN directly
        # This would need a table recreation in SQLite, so we'll skip it in downgrade
        # The column will remain but won't be used
        pass
