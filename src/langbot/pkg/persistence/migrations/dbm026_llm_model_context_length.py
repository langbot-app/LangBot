import sqlalchemy
from .. import migration


@migration.migration_class(26)
class DBMigrateLLMModelContextLength(migration.DBMigration):
    """Add context_length column to LLM models"""

    async def upgrade(self):
        columns = await self._get_columns('llm_models')
        if 'context_length' not in columns:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE llm_models ADD COLUMN context_length INTEGER')
            )

    async def downgrade(self):
        columns = await self._get_columns('llm_models')
        if 'context_length' not in columns:
            return

        if self.ap.persistence_mgr.db.name == 'postgresql':
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE llm_models DROP COLUMN IF EXISTS context_length')
            )
        else:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE llm_models DROP COLUMN context_length')
            )

    async def _get_columns(self, table_name: str) -> set[str]:
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("""
                    SELECT column_name FROM information_schema.columns
                    WHERE table_name = :table_name
                """),
                {'table_name': table_name},
            )
            return {row[0] for row in result.fetchall()}

        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text(f'PRAGMA table_info({table_name})'))
        return {row[1] for row in result.fetchall()}
