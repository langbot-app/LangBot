from __future__ import annotations

import sqlalchemy

from .. import migration


@migration.migration_class(26)
class DBMigrateKukuSilenceSeconds(migration.DBMigration):
    """KUKU: add silence_seconds, migrate from silence_minutes (* 60), drop silence_minutes."""

    async def _table_exists(self, table_name: str) -> bool:
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = :table_name);'
                ).bindparams(table_name=table_name)
            )
            return bool(result.scalar())
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text("SELECT name FROM sqlite_master WHERE type='table' AND name=:table_name;").bindparams(
                table_name=table_name
            )
        )
        return result.first() is not None

    async def _get_table_columns(self, table_name: str) -> list[str]:
        if self.ap.persistence_mgr.db.name == 'postgresql':
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'SELECT column_name FROM information_schema.columns WHERE table_name = :table_name;'
                ).bindparams(table_name=table_name)
            )
            return [row[0] for row in result.fetchall()]
        if not table_name.isidentifier():
            raise ValueError(f'Invalid table name: {table_name}')
        result = await self.ap.persistence_mgr.execute_async(sqlalchemy.text(f'PRAGMA table_info({table_name});'))
        return [row[1] for row in result.fetchall()]

    async def _add_column_if_not_exists(self, table_name: str, column_name: str, column_type: str) -> None:
        columns = await self._get_table_columns(table_name)
        if column_name in columns:
            self.ap.logger.debug('%s column already exists in %s.', column_name, table_name)
            return
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(f'ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type};')
        )
        self.ap.logger.info('Added %s column to %s table.', column_name, table_name)

    async def _drop_column_if_exists(self, table_name: str, column_name: str) -> None:
        columns = await self._get_table_columns(table_name)
        if column_name not in columns:
            return
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(f'ALTER TABLE {table_name} DROP COLUMN {column_name};')
        )
        self.ap.logger.info('Dropped %s column from %s table.', column_name, table_name)

    async def upgrade(self) -> None:
        if not await self._table_exists('kuku_group_settings'):
            self.ap.logger.warning('kuku_group_settings table does not exist, skipping migration.')
            return

        columns = await self._get_table_columns('kuku_group_settings')
        if 'silence_seconds' not in columns:
            await self._add_column_if_not_exists('kuku_group_settings', 'silence_seconds', 'INTEGER')

        columns = await self._get_table_columns('kuku_group_settings')
        if 'silence_minutes' in columns:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    """
                    UPDATE kuku_group_settings
                    SET silence_seconds = COALESCE(
                        NULLIF(silence_seconds, 0),
                        NULLIF(silence_minutes, 0) * 60,
                        1800
                    )
                    """
                )
            )
            await self._drop_column_if_exists('kuku_group_settings', 'silence_minutes')

        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text(
                """
                UPDATE kuku_group_settings
                SET silence_seconds = 1800
                WHERE silence_seconds IS NULL OR silence_seconds < 1
                """
            )
        )

    async def downgrade(self) -> None:
        pass
