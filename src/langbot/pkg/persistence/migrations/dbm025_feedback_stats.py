import sqlalchemy
from .. import migration


@migration.migration_class(25)
class DBMigrateFeedbackStats(migration.DBMigration):
    """Add monitoring_feedback table for storing user feedback from AI Bot conversations"""

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

    async def upgrade(self):
        """Create monitoring_feedback table."""
        if await self._table_exists('monitoring_feedback'):
            self.ap.logger.debug('monitoring_feedback table already exists, skipping migration.')
            return

        # Create monitoring_feedback table with all columns
        create_table_sql = '''
            CREATE TABLE monitoring_feedback (
                id VARCHAR(255) PRIMARY KEY,
                timestamp DATETIME NOT NULL,
                feedback_id VARCHAR(255) NOT NULL UNIQUE,
                feedback_type INTEGER NOT NULL,
                feedback_content TEXT,
                inaccurate_reasons TEXT,
                bot_id VARCHAR(255),
                bot_name VARCHAR(255),
                pipeline_id VARCHAR(255),
                pipeline_name VARCHAR(255),
                session_id VARCHAR(255),
                message_id VARCHAR(255),
                stream_id VARCHAR(255),
                user_id VARCHAR(255),
                platform VARCHAR(255)
            )
        '''
        await self.ap.persistence_mgr.execute_async(sqlalchemy.text(create_table_sql))

        # Create indexes
        indexes = [
            'CREATE INDEX ix_monitoring_feedback_timestamp ON monitoring_feedback (timestamp)',
            'CREATE UNIQUE INDEX ix_monitoring_feedback_feedback_id ON monitoring_feedback (feedback_id)',
            'CREATE INDEX ix_monitoring_feedback_bot_id ON monitoring_feedback (bot_id)',
            'CREATE INDEX ix_monitoring_feedback_pipeline_id ON monitoring_feedback (pipeline_id)',
            'CREATE INDEX ix_monitoring_feedback_session_id ON monitoring_feedback (session_id)',
            'CREATE INDEX ix_monitoring_feedback_message_id ON monitoring_feedback (message_id)',
            'CREATE INDEX ix_monitoring_feedback_stream_id ON monitoring_feedback (stream_id)',
        ]
        for index_sql in indexes:
            await self.ap.persistence_mgr.execute_async(sqlalchemy.text(index_sql))

        self.ap.logger.info('Created monitoring_feedback table with indexes.')

    async def downgrade(self):
        """Drop monitoring_feedback table."""
        if await self._table_exists('monitoring_feedback'):
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.text('DROP TABLE monitoring_feedback')
            )
            self.ap.logger.info('Dropped monitoring_feedback table.')
