from .. import migration


# this is a deprecated migration
@migration.migration_class(15)
class DBMigrateModelSourceTracking(migration.DBMigration):
    """Add source tracking fields to models tables for Space integration"""

    async def upgrade(self):
        """Upgrade"""
        pass

    async def downgrade(self):
        """Downgrade"""
        pass
