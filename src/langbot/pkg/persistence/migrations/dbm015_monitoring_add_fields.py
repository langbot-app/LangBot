import sqlalchemy
from .. import migration


@migration.migration_class(15)
class DBMigrateMonitoringAddFields(migration.DBMigration):
    """Add message_id and runner_name fields to monitoring tables"""

    async def upgrade(self):
        """Add new fields to monitoring tables"""

        # Add runner_name to monitoring_messages table
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'ALTER TABLE monitoring_messages ADD COLUMN runner_name VARCHAR(255)'
                )
            )
            self.ap.logger.info('Added runner_name column to monitoring_messages table')
        except Exception as e:
            self.ap.logger.warning(f'Failed to add runner_name column (may already exist): {e}')

        # Add message_id to monitoring_llm_calls table
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'ALTER TABLE monitoring_llm_calls ADD COLUMN message_id VARCHAR(255)'
                )
            )
            self.ap.logger.info('Added message_id column to monitoring_llm_calls table')
        except Exception as e:
            self.ap.logger.warning(f'Failed to add message_id column to llm_calls (may already exist): {e}')

        # Create index on message_id in monitoring_llm_calls
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'CREATE INDEX IF NOT EXISTS idx_monitoring_llm_calls_message_id ON monitoring_llm_calls(message_id)'
                )
            )
            self.ap.logger.info('Created index on message_id in monitoring_llm_calls table')
        except Exception as e:
            self.ap.logger.warning(f'Failed to create index on message_id in llm_calls: {e}')

        # Add message_id to monitoring_errors table
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'ALTER TABLE monitoring_errors ADD COLUMN message_id VARCHAR(255)'
                )
            )
            self.ap.logger.info('Added message_id column to monitoring_errors table')
        except Exception as e:
            self.ap.logger.warning(f'Failed to add message_id column to errors (may already exist): {e}')

        # Create index on message_id in monitoring_errors
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text(
                    'CREATE INDEX IF NOT EXISTS idx_monitoring_errors_message_id ON monitoring_errors(message_id)'
                )
            )
            self.ap.logger.info('Created index on message_id in monitoring_errors table')
        except Exception as e:
            self.ap.logger.warning(f'Failed to create index on message_id in errors: {e}')

    async def downgrade(self):
        """Remove added fields from monitoring tables"""

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

        # Drop columns
        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE monitoring_errors DROP COLUMN message_id')
            )
        except Exception as e:
            self.ap.logger.warning(f'Failed to drop message_id from errors: {e}')

        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE monitoring_llm_calls DROP COLUMN message_id')
            )
        except Exception as e:
            self.ap.logger.warning(f'Failed to drop message_id from llm_calls: {e}')

        try:
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('ALTER TABLE monitoring_messages DROP COLUMN runner_name')
            )
        except Exception as e:
            self.ap.logger.warning(f'Failed to drop runner_name from messages: {e}')
