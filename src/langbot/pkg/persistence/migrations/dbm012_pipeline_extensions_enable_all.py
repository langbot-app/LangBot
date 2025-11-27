from .. import migration

import sqlalchemy

from ...entity.persistence import pipeline as persistence_pipeline


@migration.migration_class(12)
class DBMigratePipelineExtensionsEnableAll(migration.DBMigration):
    """Pipeline extensions enable all"""

    async def upgrade(self):
        """Upgrade"""
        # read all pipelines
        pipelines = await self.ap.persistence_mgr.execute_async(sqlalchemy.select(persistence_pipeline.LegacyPipeline))

        for pipeline in pipelines:
            serialized_pipeline = self.ap.persistence_mgr.serialize_model(persistence_pipeline.LegacyPipeline, pipeline)

            extensions_preferences = serialized_pipeline['extensions_preferences']

            if 'enable_all_plugins' not in extensions_preferences:
                if 'plugins' in extensions_preferences:
                    extensions_preferences['enable_all_plugins'] = False
                else:
                    extensions_preferences['enable_all_plugins'] = True
                    extensions_preferences['plugins'] = []

            if 'enable_all_mcp_servers' not in extensions_preferences:
                if 'mcp_servers' in extensions_preferences:
                    extensions_preferences['enable_all_mcp_servers'] = False
                else:
                    extensions_preferences['enable_all_mcp_servers'] = True
                    extensions_preferences['mcp_servers'] = []

            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_pipeline.LegacyPipeline)
                .where(persistence_pipeline.LegacyPipeline.uuid == serialized_pipeline['uuid'])
                .values(
                    extensions_preferences=extensions_preferences,
                    for_version=self.ap.ver_mgr.get_current_version(),
                )
            )

    async def downgrade(self):
        """Downgrade"""
        pass
