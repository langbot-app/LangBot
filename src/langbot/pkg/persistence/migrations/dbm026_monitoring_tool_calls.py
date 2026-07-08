from langbot.pkg.entity.persistence import monitoring as persistence_monitoring
from .. import migration


@migration.migration_class(26)
class DBMigrateMonitoringToolCalls(migration.DBMigration):
    """Add monitoring_tool_calls table"""

    async def upgrade(self):
        """Upgrade"""
        async with self.ap.persistence_mgr.get_db_engine().begin() as conn:
            await conn.run_sync(persistence_monitoring.MonitoringToolCall.__table__.create, checkfirst=True)

    async def downgrade(self):
        """Downgrade"""
        async with self.ap.persistence_mgr.get_db_engine().begin() as conn:
            await conn.run_sync(persistence_monitoring.MonitoringToolCall.__table__.drop, checkfirst=True)
