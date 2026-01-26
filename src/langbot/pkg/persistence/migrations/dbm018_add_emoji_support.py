import sqlalchemy
from .. import migration


@migration.migration_class(18)
class DBMigrateAddEmojiSupport(migration.DBMigration):
    """Add emoji field to knowledge_bases, external_knowledge_bases and legacy_pipelines tables"""

    async def upgrade(self):
        """Upgrade"""
        # Add emoji field to knowledge_bases
        await self._add_emoji_to_table('knowledge_bases', '📚')

        # Add emoji field to external_knowledge_bases
        await self._add_emoji_to_table('external_knowledge_bases', '🔗')

        # Add emoji field to legacy_pipelines
        await self._add_emoji_to_table('legacy_pipelines', '⚙️')

    async def _add_emoji_to_table(self, table_name: str, default_emoji: str):
        """Add emoji column to specified table if it doesn't exist"""
        # Get all column names from the table
        columns = []

        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}';"
                )
            )
            all_result = result.fetchall()
            columns = [row[0] for row in all_result]
        else:
            result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text(f'PRAGMA table_info({table_name});'))
            all_result = result.fetchall()
            columns = [row[1] for row in all_result]

        # Check and add emoji column
        if 'emoji' not in columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(f"ALTER TABLE {table_name} ADD COLUMN emoji VARCHAR(10) DEFAULT '{default_emoji}'")
                )
            else:
                # SQLite doesn't support DEFAULT with emoji directly in ALTER TABLE
                # Add column without default first
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(f'ALTER TABLE {table_name} ADD COLUMN emoji VARCHAR(10)')
                )

            # Set default emoji value for existing records
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(f"UPDATE {table_name} SET emoji = '{default_emoji}' WHERE emoji IS NULL")
            )

    async def downgrade(self):
        """Downgrade"""
        pass
