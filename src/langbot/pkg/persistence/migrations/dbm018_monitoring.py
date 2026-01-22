import sqlalchemy
from .. import migration


@migration.migration_class(18)
class DBMigrateMonitoring(migration.DBMigration):
    """Setup monitoring tables and fields.

    This migration handles:
    1. Creating monitoring tables if they don't exist (via SQLAlchemy metadata)
    2. Adding runner_name column to monitoring_messages
    3. Adding message_id column to monitoring_llm_calls and monitoring_errors
    4. Adding variables column to monitoring_messages
    5. Creating necessary indexes

    All operations use try-except to handle cases where columns/indexes already exist.
    """

    async def upgrade(self):
        """Setup monitoring tables and add all required fields"""

        # Import monitoring entities to ensure tables are registered in metadata
        from ...entity.persistence import monitoring  # noqa: F401

        # The tables will be created by create_tables() if they don't exist
        # Below we add columns that might be missing for users upgrading from older versions

        # Add runner_name to monitoring_messages table
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'ALTER TABLE monitoring_messages ADD COLUMN runner_name VARCHAR(255)'
                )
            )
            self.ap.logger.info('Added runner_name column to monitoring_messages table')
        except Exception as e:
            self.ap.logger.debug(f'runner_name column may already exist: {e}')

        # Add variables to monitoring_messages table
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'ALTER TABLE monitoring_messages ADD COLUMN variables TEXT'
                )
            )
            self.ap.logger.info('Added variables column to monitoring_messages table')
        except Exception as e:
            self.ap.logger.debug(f'variables column may already exist: {e}')

        # Add message_id to monitoring_llm_calls table
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'ALTER TABLE monitoring_llm_calls ADD COLUMN message_id VARCHAR(255)'
                )
            )
            self.ap.logger.info('Added message_id column to monitoring_llm_calls table')
        except Exception as e:
            self.ap.logger.debug(f'message_id column in llm_calls may already exist: {e}')

        # Create index on message_id in monitoring_llm_calls
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'CREATE INDEX IF NOT EXISTS idx_monitoring_llm_calls_message_id ON monitoring_llm_calls(message_id)'
                )
            )
            self.ap.logger.info('Created index on message_id in monitoring_llm_calls table')
        except Exception as e:
            self.ap.logger.debug(f'Index on message_id in llm_calls may already exist: {e}')

        # Add message_id to monitoring_errors table
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'ALTER TABLE monitoring_errors ADD COLUMN message_id VARCHAR(255)'
                )
            )
            self.ap.logger.info('Added message_id column to monitoring_errors table')
        except Exception as e:
            self.ap.logger.debug(f'message_id column in errors may already exist: {e}')

        # Create index on message_id in monitoring_errors
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'CREATE INDEX IF NOT EXISTS idx_monitoring_errors_message_id ON monitoring_errors(message_id)'
                )
            )
            self.ap.logger.info('Created index on message_id in monitoring_errors table')
        except Exception as e:
            self.ap.logger.debug(f'Index on message_id in errors may already exist: {e}')

        self.ap.logger.info('Monitoring migration completed')

    async def downgrade(self):
        """Remove monitoring fields (tables are kept)"""

        # Drop indexes first
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('DROP INDEX IF EXISTS idx_monitoring_errors_message_id')
            )
        except Exception as e:
            self.ap.logger.warning(f'Failed to drop index: {e}')

        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('DROP INDEX IF EXISTS idx_monitoring_llm_calls_message_id')
            )
        except Exception as e:
            self.ap.logger.warning(f'Failed to drop index: {e}')

        # Drop columns (SQLite doesn't support DROP COLUMN in older versions, so this may fail)
        for table, column in [
            ('monitoring_errors', 'message_id'),
            ('monitoring_llm_calls', 'message_id'),
            ('monitoring_messages', 'runner_name'),
            ('monitoring_messages', 'variables'),
        ]:
            try:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(f'ALTER TABLE {table} DROP COLUMN {column}')
                )
            except Exception as e:
                self.ap.logger.warning(f'Failed to drop {column} from {table}: {e}')
