import sqlalchemy
from .. import migration


@migration.migration_class(22)
class DBMigrateMonitoringUserId(migration.DBMigration):
    """Add user_id and user_name columns to monitoring_sessions table

    This migration adds the missing user_id column and also ensures user_name
    column exists (in case migration 21 failed or was skipped).
    """

    async def upgrade(self):
        # Check if monitoring_sessions table exists
        try:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text("SELECT name FROM sqlite_master WHERE type='table' AND name='monitoring_sessions';")
            )
            if not result.fetchone():
                self.ap.logger.warning('monitoring_sessions table does not exist, skipping migration.')
                return
        except Exception as e:
            self.ap.logger.warning(f'Failed to check if monitoring_sessions table exists: {e}')

        # Add user_id column to monitoring_sessions table
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE monitoring_sessions ADD COLUMN user_id VARCHAR(255);')
            )
            self.ap.logger.info('Added user_id column to monitoring_sessions table.')
        except Exception as e:
            if 'duplicate column name' in str(e).lower():
                self.ap.logger.debug('user_id column already exists in monitoring_sessions.')
            else:
                self.ap.logger.warning(f'Failed to add user_id column to monitoring_sessions: {e}')

        # Add user_name column to monitoring_sessions table (in case migration 21 failed)
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE monitoring_sessions ADD COLUMN user_name VARCHAR(255);')
            )
            self.ap.logger.info('Added user_name column to monitoring_sessions table.')
        except Exception as e:
            if 'duplicate column name' in str(e).lower():
                self.ap.logger.debug('user_name column already exists in monitoring_sessions.')
            else:
                self.ap.logger.warning(f'Failed to add user_name column to monitoring_sessions: {e}')

        # Add user_name column to monitoring_messages table (in case migration 21 failed)
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE monitoring_messages ADD COLUMN user_name VARCHAR(255);')
            )
            self.ap.logger.info('Added user_name column to monitoring_messages table.')
        except Exception as e:
            if 'duplicate column name' in str(e).lower():
                self.ap.logger.debug('user_name column already exists in monitoring_messages.')
            else:
                self.ap.logger.warning(f'Failed to add user_name column to monitoring_messages: {e}')

    async def downgrade(self):
        # SQLite does not support DROP COLUMN, so we skip downgrade for SQLite
        pass
