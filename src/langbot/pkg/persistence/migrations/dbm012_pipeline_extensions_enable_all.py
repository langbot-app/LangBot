from .. import migration

import sqlalchemy
import json


@migration.migration_class(12)
class DBMigratePipelineExtensionsEnableAll(migration.DBMigration):
    """Pipeline extensions enable all"""

    async def upgrade(self):
        """Upgrade"""
        # Read all pipelines using raw SQL
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('SELECT uuid, extensions_preferences FROM legacy_pipelines')
        )
        pipelines = result.fetchall()

        current_version = self.ap.ver_mgr.get_current_version()

        for pipeline_row in pipelines:
            uuid = pipeline_row[0]
            extensions_preferences = (
                json.loads(pipeline_row[1]) if isinstance(pipeline_row[1], str) else pipeline_row[1]
            )

            # Ensure extensions_preferences is a dict
            if extensions_preferences is None:
                extensions_preferences = {}

            # Add 'enable_all_plugins' if not exists
            if 'enable_all_plugins' not in extensions_preferences:
                if 'plugins' in extensions_preferences:
                    extensions_preferences['enable_all_plugins'] = False
                else:
                    extensions_preferences['enable_all_plugins'] = True
                    extensions_preferences['plugins'] = []

            # Add 'enable_all_mcp_servers' if not exists
            if 'enable_all_mcp_servers' not in extensions_preferences:
                if 'mcp_servers' in extensions_preferences:
                    extensions_preferences['enable_all_mcp_servers'] = False
                else:
                    extensions_preferences['enable_all_mcp_servers'] = True
                    extensions_preferences['mcp_servers'] = []

            # Update using raw SQL with compatibility for both SQLite and PostgreSQL
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'UPDATE legacy_pipelines SET extensions_preferences = :extensions_preferences::jsonb, for_version = :for_version WHERE uuid = :uuid'
                    ),
                    {
                        'extensions_preferences': json.dumps(extensions_preferences),
                        'for_version': current_version,
                        'uuid': uuid,
                    },
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'UPDATE legacy_pipelines SET extensions_preferences = :extensions_preferences, for_version = :for_version WHERE uuid = :uuid'
                    ),
                    {
                        'extensions_preferences': json.dumps(extensions_preferences),
                        'for_version': current_version,
                        'uuid': uuid,
                    },
                )

    async def downgrade(self):
        """Downgrade"""
        pass
