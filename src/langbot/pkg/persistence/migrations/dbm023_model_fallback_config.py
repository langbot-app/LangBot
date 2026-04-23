from .. import migration

import sqlalchemy
import json


@migration.migration_class(23)
class DBMigrateModelFallbackConfig(migration.DBMigration):
    """Convert model field from plain UUID string to object with primary/fallbacks"""

    async def upgrade(self):
        """Upgrade"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('SELECT uuid, config FROM legacy_pipelines')
        )
        pipelines = result.fetchall()

        current_version = self.ap.ver_mgr.get_current_version()

        for pipeline_row in pipelines:
            uuid = pipeline_row[0]
            config = json.loads(pipeline_row[1]) if isinstance(pipeline_row[1], str) else pipeline_row[1]

            if 'ai' not in config or 'local-agent' not in config['ai']:
                continue

            local_agent = config['ai']['local-agent']
            changed = False

            # Convert model from string to object
            model_value = local_agent.get('model', '')
            if isinstance(model_value, str):
                local_agent['model'] = {
                    'primary': model_value,
                    'fallbacks': [],
                }
                changed = True

            # Remove leftover fallback-models field if present
            if 'fallback-models' in local_agent:
                del local_agent['fallback-models']
                changed = True

            if not changed:
                continue

            # Update using raw SQL with compatibility for both SQLite and PostgreSQL
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'UPDATE legacy_pipelines SET config = :config::jsonb, for_version = :for_version WHERE uuid = :uuid'
                    ),
                    {'config': json.dumps(config), 'for_version': current_version, 'uuid': uuid},
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'UPDATE legacy_pipelines SET config = :config, for_version = :for_version WHERE uuid = :uuid'
                    ),
                    {'config': json.dumps(config), 'for_version': current_version, 'uuid': uuid},
                )

    async def downgrade(self):
        """Downgrade"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.text('SELECT uuid, config FROM legacy_pipelines')
        )
        pipelines = result.fetchall()

        current_version = self.ap.ver_mgr.get_current_version()

        for pipeline_row in pipelines:
            uuid = pipeline_row[0]
            config = json.loads(pipeline_row[1]) if isinstance(pipeline_row[1], str) else pipeline_row[1]

            if 'ai' not in config or 'local-agent' not in config['ai']:
                continue

            local_agent = config['ai']['local-agent']

            # Convert model from object back to string
            model_value = local_agent.get('model', '')
            if isinstance(model_value, dict):
                local_agent['model'] = model_value.get('primary', '')
            else:
                continue

            # Update using raw SQL with compatibility for both SQLite and PostgreSQL
            if self.ap.persistence_mgr.db.name == 'postgresql':
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'UPDATE legacy_pipelines SET config = :config::jsonb, for_version = :for_version WHERE uuid = :uuid'
                    ),
                    {'config': json.dumps(config), 'for_version': current_version, 'uuid': uuid},
                )
            else:
                await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.text(
                        'UPDATE legacy_pipelines SET config = :config, for_version = :for_version WHERE uuid = :uuid'
                    ),
                    {'config': json.dumps(config), 'for_version': current_version, 'uuid': uuid},
                )
