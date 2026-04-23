import sqlalchemy
from .. import migration


@migration.migration_class(22)
class DBMigrateMonitoringUserId(migration.DBMigration):
    """Add user_id and user_name columns to monitoring_sessions table

    This migration adds the missing user_id column and also ensures user_name
    column exists (in case migration 21 failed or was skipped).
    """

    async def _table_exists(self, table_name: str) -> bool:
        """Check if a table exists (works for both SQLite and PostgreSQL)."""
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name);'
                ).bindparams(table_name=table_name)
            )
            return bool(result.scalar())
        else:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name;").bindparams(
                    table_name=table_name
                )
            )
            return result.first() is not None

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
            if not table_name.isidentifier():
                raise ValueError(f'Invalid table name: {table_name}')
            result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text(f'PRAGMA table_info({table_name});'))
            return [row[1] for row in result.fetchall()]

    async def _add_column_if_not_exists(self, table_name: str, column_name: str, column_type: str):
        """Add a column to a table if it does not already exist."""
        columns = await self._get_table_columns(table_name)
        if column_name in columns:
            self.ap.logger.debug('%s column already exists in %s.', column_name, table_name)
            return
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};')
        )
        self.ap.logger.info('Added %s column to %s table.', column_name, table_name)

    async def upgrade(self):
        # Check if monitoring_sessions table exists
        if not await self._table_exists('monitoring_sessions'):
            self.ap.logger.warning('monitoring_sessions table does not exist, skipping migration.')
            return

        # Add user_id column to monitoring_sessions table
        await self._add_column_if_not_exists('monitoring_sessions', 'user_id', 'VARCHAR(255)')

        # Add user_name column to monitoring_sessions table (in case migration 21 failed)
        await self._add_column_if_not_exists('monitoring_sessions', 'user_name', 'VARCHAR(255)')

        # Add user_name column to monitoring_messages table (in case migration 21 failed)
        if await self._table_exists('monitoring_messages'):
            await self._add_column_if_not_exists('monitoring_messages', 'user_name', 'VARCHAR(255)')

    async def downgrade(self):
        pass
