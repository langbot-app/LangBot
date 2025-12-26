import sqlalchemy
from .. import migration


@migration.migration_class(15)
class DBMigrateModelSourceTracking(migration.DBMigration):
    """Add source tracking fields to models tables for Space integration"""

    async def upgrade(self):
        """Upgrade"""
        # Add source column to llm_models table
        llm_columns = await self._get_columns('llm_models')

        if 'source' not in llm_columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text("ALTER TABLE llm_models ADD COLUMN source VARCHAR(32) DEFAULT 'local' NOT NULL")
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text("ALTER TABLE llm_models ADD COLUMN source VARCHAR(32) DEFAULT 'local' NOT NULL")
                )

        if 'space_model_id' not in llm_columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE llm_models ADD COLUMN space_model_id VARCHAR(255)')
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE llm_models ADD COLUMN space_model_id VARCHAR(255)')
                )

        # Add source column to embedding_models table
        embedding_columns = await self._get_columns('embedding_models')

        if 'source' not in embedding_columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        "ALTER TABLE embedding_models ADD COLUMN source VARCHAR(32) DEFAULT 'local' NOT NULL"
                    )
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        "ALTER TABLE embedding_models ADD COLUMN source VARCHAR(32) DEFAULT 'local' NOT NULL"
                    )
                )

        if 'space_model_id' not in embedding_columns:
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE embedding_models ADD COLUMN space_model_id VARCHAR(255)')
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text('ALTER TABLE embedding_models ADD COLUMN space_model_id VARCHAR(255)')
                )

    async def _get_columns(self, table_name: str) -> list:
        """Get column names for a table"""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    f"SELECT column_name FROM information_schema.columns WHERE table_name = '{table_name}';"
                )
            )
            all_result = result.fetchall()
            return [row[0] for row in all_result]
        else:
            result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text(f'PRAGMA table_info({table_name});'))
            all_result = result.fetchall()
            return [row[1] for row in all_result]

    async def downgrade(self):
        """Downgrade"""
        pass
