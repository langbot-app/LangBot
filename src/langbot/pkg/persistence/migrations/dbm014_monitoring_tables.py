import sqlalchemy
from .. import migration


@migration.migration_class(14)
class DBMigrateMonitoringTables(migration.DBMigration):
    """Create monitoring tables for observability"""

    async def upgrade(self):
        """Create monitoring tables"""

        # Import the monitoring entities to ensure tables are registered
        from ...entity.persistence import monitoring

        # The tables will be created by the create_tables method in persistence manager
        # This migration is mainly for version tracking

        self.ap.logger.info('Monitoring tables will be created by SQLAlchemy metadata')

    async def downgrade(self):
        """Downgrade - drop monitoring tables"""
        # Drop tables in reverse order of dependencies
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('DROP TABLE IF EXISTS monitoring_errors')
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('DROP TABLE IF EXISTS monitoring_sessions')
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('DROP TABLE IF EXISTS monitoring_llm_calls')
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('DROP TABLE IF EXISTS monitoring_messages')
        )
