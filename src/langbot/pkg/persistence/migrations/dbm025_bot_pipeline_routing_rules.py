import sqlalchemy
from .. import migration


@migration.migration_class(25)
class DBMigrateBotPipelineRoutingRules(migration.DBMigration):
    """Add pipeline_routing_rules column to bots table"""

    async def upgrade(self):
        sql_text = sqlalchemy.text("ALTER TABLE bots ADD COLUMN pipeline_routing_rules JSON NOT NULL DEFAULT '[]'")
        await self.ap.persistence_mgr.execute_async(sql_text)

    async def downgrade(self):
        sql_text = sqlalchemy.text('ALTER TABLE bots DROP COLUMN pipeline_routing_rules')
        await self.ap.persistence_mgr.execute_async(sql_text)
