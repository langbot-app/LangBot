import sqlalchemy
from .. import migration


@migration.migration_class(13)
class DBMigrateKnowledgeBaseUpdatedAt(migration.DBMigration):
    """Add updated_at field to knowledge_bases table"""

    async def upgrade(self):
        """Upgrade"""
        # Get all column names from the table
        columns = []

        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = 'knowledge_bases';"
                )
            )
            all_result = result.fetchall()
            columns = [row[0] for row in all_result]
        else:
            result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text('PRAGMA table_info(knowledge_bases);'))
            all_result = result.fetchall()
            columns = [row[1] for row in all_result]

        # Check and add updated_at column
        if 'updated_at' not in columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'ALTER TABLE knowledge_bases ADD COLUMN updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP'
                    )
                )
            else:
                # SQLite doesn't support DEFAULT CURRENT_TIMESTAMP in ALTER TABLE
                # Add column without default first
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE knowledge_bases ADD COLUMN updated_at DATETIME')
                )

            # Set initial updated_at values to created_at for existing records
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('UPDATE knowledge_bases SET updated_at = created_at WHERE updated_at IS NULL')
            )

    async def downgrade(self):
        """Downgrade"""
        pass
