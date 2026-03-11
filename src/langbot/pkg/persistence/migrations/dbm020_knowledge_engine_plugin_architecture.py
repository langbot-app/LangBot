import sqlalchemy
from .. import migration


@migration.migration_class(20)
class DBMigrateKnowledgeEnginePluginArchitecture(migration.DBMigration):
    """Migrate to unified Knowledge Engine plugin architecture.

    Changes:
    - Backup existing knowledge_bases data to knowledge_bases_backup
    - Clear knowledge_bases table and add new plugin architecture columns
    - Drop old columns (PostgreSQL only; SQLite leaves them unmapped)
    - Preserve external_knowledge_bases table as-is for future migration
    - Set rag_plugin_migration_needed flag in metadata if old data exists
    """

    async def upgrade(self):
        """Upgrade"""
        has_internal_data = await self._backup_knowledge_bases()
        has_external_data = await self._check_external_knowledge_bases()
        await self._clear_knowledge_bases()
        await self._add_columns_to_knowledge_bases()
        await self._drop_old_columns()
        if has_internal_data or has_external_data:
            await self._set_migration_flag()

    async def _get_table_columns(self, table_name: str) -> list[str]:
        """Get column names from a table (works for both SQLite and PostgreSQL)."""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'SELECT column_name FROM information_schema.columns WHERE table_name = :table_name;'
                ).bindparams(table_name=table_name)
            )
            return [row[0] for row in result.fetchall()]
        else:
            # SQLite PRAGMA does not support bind parameters; validate identifier.
            if not table_name.isidentifier():
                raise ValueError(f'Invalid table name: {table_name}')
            result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text(f'PRAGMA table_info({table_name});'))
            return [row[1] for row in result.fetchall()]

    async def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists."""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name);'
                ).bindparams(table_name=table_name)
            )
            return result.scalar()
        else:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name;").bindparams(
                    table_name=table_name
                )
            )
            return result.first() is not None

    async def _backup_knowledge_bases(self) -> bool:
        """Backup knowledge_bases data. Returns True if data was backed up."""
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text('SELECT COUNT(*) FROM knowledge_bases;'))
        count = result.scalar()
        if count == 0:
            return False

        # Drop backup table if it already exists (from a previous failed migration)
        if await self._table_exists('knowledge_bases_backup'):
            await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE knowledge_bases_backup;'))

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('CREATE TABLE knowledge_bases_backup AS SELECT * FROM knowledge_bases;')
        )
        self.ap.logger.info(
            'Backed up %d knowledge base(s) to knowledge_bases_backup table.',
            count,
        )
        return True

    async def _check_external_knowledge_bases(self) -> bool:
        """Check if external_knowledge_bases table exists and has data.

        The table is preserved as-is (not dropped) for future migration.
        """
        if not await self._table_exists('external_knowledge_bases'):
            return False

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('SELECT COUNT(*) FROM external_knowledge_bases;')
        )
        count = result.scalar()
        if count > 0:
            self.ap.logger.info(
                'Found %d external knowledge base(s) in external_knowledge_bases table. '
                'Table preserved for future migration.',
                count,
            )
        return count > 0

    async def _clear_knowledge_bases(self):
        """Clear all rows from knowledge_bases table (preserve table structure)."""
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DELETE FROM knowledge_bases;'))

    async def _add_columns_to_knowledge_bases(self):
        """Add new RAG plugin architecture columns to knowledge_bases table."""
        columns = await self._get_table_columns('knowledge_bases')

        new_columns = {
            'knowledge_engine_plugin_id': 'VARCHAR',
            'collection_id': 'VARCHAR',
            'creation_settings': 'TEXT',  # JSON stored as TEXT for SQLite compatibility
            'retrieval_settings': 'TEXT',
        }

        for col_name, col_type in new_columns.items():
            if col_name not in columns:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(f'ALTER TABLE knowledge_bases ADD COLUMN {col_name} {col_type};')
                )

    async def _drop_old_columns(self):
        """Drop embedding_model_uuid and top_k columns (PostgreSQL only).

        SQLite does not support DROP COLUMN in older versions, so we leave the
        columns in place — the SQLAlchemy entity simply won't map them.
        """
        if self.ap.persistence_mgr.db.name != 'postgresql':
            return

        columns = await self._get_table_columns('knowledge_bases')

        if 'embedding_model_uuid' in columns:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE knowledge_bases DROP COLUMN embedding_model_uuid;')
            )

        if 'top_k' in columns:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE knowledge_bases DROP COLUMN top_k;')
            )

    async def _set_migration_flag(self):
        """Set rag_plugin_migration_needed flag in metadata table."""
        # Check if the key already exists
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text("SELECT value FROM metadata WHERE key = 'rag_plugin_migration_needed';")
        )
        row = result.first()
        if row is not None:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("UPDATE metadata SET value = 'true' WHERE key = 'rag_plugin_migration_needed';")
            )
        else:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("INSERT INTO metadata (key, value) VALUES ('rag_plugin_migration_needed', 'true');")
            )
        self.ap.logger.info('Set rag_plugin_migration_needed=true in metadata.')

    async def downgrade(self):
        """Downgrade"""
        pass
