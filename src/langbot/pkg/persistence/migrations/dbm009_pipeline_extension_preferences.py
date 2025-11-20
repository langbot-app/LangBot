import sqlalchemy
from .. import migration


@migration.migration_class(9)
class DBMigratePipelineExtensionPreferences(migration.DBMigration):
    """Pipeline extension preferences"""

    async def upgrade(self):
        """Upgrade"""

        sql_text = sqlalchemy.text(
            "ALTER TABLE legacy_pipelines ADD COLUMN extensions_preferences JSON NOT NULL DEFAULT '{}'"
        )
        await self.ap.persistence_mgr.execute_async(sql_text)

    async def downgrade(self):
        """Downgrade"""
        sql_text = sqlalchemy.text('ALTER TABLE legacy_pipelines DROP COLUMN extensions_preferences')
        await self.ap.persistence_mgr.execute_async(sql_text)
