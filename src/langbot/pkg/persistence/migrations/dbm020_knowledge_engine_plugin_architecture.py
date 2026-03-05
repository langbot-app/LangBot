import json

import sqlalchemy
from .. import migration


@migration.migration_class(20)
class DBMigrateKnowledgeEnginePluginArchitecture(migration.DBMigration):
    """Migrate to unified Knowledge Engine plugin architecture.

    Changes:
    - Add knowledge_engine_plugin_id, collection_id, creation_settings, retrieval_settings columns to knowledge_bases
    - Migrate existing top_k values into retrieval_settings JSON
    - Migrate existing embedding_model_uuid into creation_settings JSON
    - Drop embedding_model_uuid and top_k columns (PostgreSQL only; SQLite leaves them unmapped)
    - Drop external_knowledge_bases table (no longer needed; external KB data is not migrated)
    """

    async def upgrade(self):
        """Upgrade"""
        await self._add_columns_to_knowledge_bases()
        await self._migrate_top_k_to_retrieval_settings()
        await self._migrate_embedding_model_uuid_to_creation_settings()
        await self._drop_old_columns()
        await self._drop_external_knowledge_bases_table()

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

        # For existing knowledge bases without knowledge_engine_plugin_id,
        # set collection_id = uuid (same default as new KBs)
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('UPDATE knowledge_bases SET collection_id = uuid WHERE collection_id IS NULL;')
        )

    async def _migrate_top_k_to_retrieval_settings(self):
        """Migrate existing top_k values into retrieval_settings JSON."""
        columns = await self._get_table_columns('knowledge_bases')
        if 'top_k' not in columns:
            return

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                'SELECT uuid, top_k FROM knowledge_bases WHERE top_k IS NOT NULL AND retrieval_settings IS NULL;'
            )
        )
        rows = result.fetchall()

        for row in rows:
            kb_uuid = row[0]
            top_k = row[1]
            retrieval_settings = json.dumps({'top_k': top_k})
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('UPDATE knowledge_bases SET retrieval_settings = :rs WHERE uuid = :uuid;').bindparams(
                    rs=retrieval_settings, uuid=kb_uuid
                )
            )

    async def _migrate_embedding_model_uuid_to_creation_settings(self):
        """Migrate existing embedding_model_uuid into creation_settings JSON."""
        columns = await self._get_table_columns('knowledge_bases')
        if 'embedding_model_uuid' not in columns:
            return

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                'SELECT uuid, embedding_model_uuid, creation_settings FROM knowledge_bases '
                "WHERE embedding_model_uuid IS NOT NULL AND embedding_model_uuid != '';"
            )
        )
        rows = result.fetchall()

        for row in rows:
            kb_uuid = row[0]
            emb_uuid = row[1]
            existing_settings = row[2]

            if existing_settings and isinstance(existing_settings, str):
                try:
                    settings = json.loads(existing_settings)
                except (json.JSONDecodeError, TypeError):
                    settings = {}
            elif isinstance(existing_settings, dict):
                settings = existing_settings
            else:
                settings = {}

            if 'embedding_model_uuid' not in settings:
                settings['embedding_model_uuid'] = emb_uuid
                new_settings = json.dumps(settings)
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'UPDATE knowledge_bases SET creation_settings = :cs WHERE uuid = :uuid;'
                    ).bindparams(cs=new_settings, uuid=kb_uuid)
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

    async def _drop_external_knowledge_bases_table(self):
        """Drop the external_knowledge_bases table if it exists."""
        if await self._table_exists('external_knowledge_bases'):
            # Log existing external KBs before dropping, so users are aware of data loss
            rows = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('SELECT * FROM external_knowledge_bases;')
            )
            existing = rows.fetchall()
            if existing:
                self.ap.logger.warning(
                    'Dropping external_knowledge_bases table with %d existing record(s). '
                    'These external KB configurations will be removed: %s',
                    len(existing),
                    [dict(row._mapping) for row in existing],
                )
            await self.ap.persistence_mgr.execute_async(sqlalchemy.text('DROP TABLE external_knowledge_bases;'))

    async def downgrade(self):
        """Downgrade"""
        pass
