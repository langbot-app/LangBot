import sqlalchemy
from .. import migration


@migration.migration_class(19)
class DBMigrateRAGEnginePluginArchitecture(migration.DBMigration):
    """Migrate to unified RAG Engine plugin architecture.

    Changes:
    - Add rag_engine_plugin_id, collection_id, creation_settings columns to knowledge_bases
    - Drop external_knowledge_bases table (no longer needed; external KB data is not migrated)
    """

    async def upgrade(self):
        """Upgrade"""
        await self._add_columns_to_knowledge_bases()
        await self._drop_external_knowledge_bases_table()

    async def _get_table_columns(self, table_name: str) -> list[str]:
        """Get column names from a table (works for both SQLite and PostgreSQL)."""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}';"
                )
            )
            return [row[0] for row in result.fetchall()]
        else:
            result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text(f'PRAGMA table_info({table_name});'))
            return [row[1] for row in result.fetchall()]

    async def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    f"SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = '{table_name}');"
                )
            )
            return result.scalar()
        else:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{table_name}';")
            )
            return result.first() is not None

    async def _add_columns_to_knowledge_bases(self):
        """Add new RAG plugin architecture columns to knowledge_bases table."""
        columns = await self._get_table_columns('knowledge_bases')

        new_columns = {
            'rag_engine_plugin_id': 'VARCHAR',
            'collection_id': 'VARCHAR',
            'creation_settings': 'TEXT',  # JSON stored as TEXT for SQLite compatibility
        }

        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(f'ALTER TABLE knowledge_bases ADD COLUMN {col_name} {col_type};')
                )

        # For existing knowledge bases without rag_engine_plugin_id,
        # set collection_id = uuid (same default as new KBs)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('UPDATE knowledge_bases SET collection_id = uuid WHERE collection_id IS NULL;')
        )

    async def _drop_external_knowledge_bases_table(self):
        """Drop the external_knowledge_bases table if it exists."""
        if await self._table_exists('external_knowledge_bases'):
            await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE external_knowledge_bases;'))

    async def downgrade(self):
        """Downgrade"""
        pass
