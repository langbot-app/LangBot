"""Normalize AgentRunner config containers

Revision ID: 0005_migrate_runner_config
Revises: 0004_add_mcp_readme
Create Date: 2026-05-10
"""

import json
import sqlalchemy as sa
from alembic import op

from langbot.pkg.agent.runner.config_migration import ConfigMigration

revision = '0005_migrate_runner_config'
down_revision = '0004_add_mcp_readme'
branch_labels = None
depends_on = None

def migrate_pipeline_config(config: dict) -> dict:
    """Migrate persisted pipeline config to the AgentRunner plugin shape."""
    return ConfigMigration.migrate_pipeline_config(config)


def _load_config(config_value):
    if isinstance(config_value, dict):
        return config_value
    if isinstance(config_value, str):
        return json.loads(config_value)
    return None


def upgrade() -> None:
    """Normalize existing pipeline config containers."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    table_name = 'legacy_pipelines'

    # Check if pipeline table exists (may not exist in fresh install)
    if table_name not in inspector.get_table_names():
        return

    # Get all pipelines
    result = conn.execute(sa.text(f'SELECT uuid, config FROM {table_name}'))
    pipelines = result.fetchall()

    for pipeline_uuid, config_json in pipelines:
        if not config_json:
            continue

        try:
            config = _load_config(config_json)
            if not isinstance(config, dict):
                continue
            migrated_config = migrate_pipeline_config(config)

            # Only update if config changed
            if json.dumps(config, sort_keys=True) != json.dumps(migrated_config, sort_keys=True):
                conn.execute(
                    sa.text(f'UPDATE {table_name} SET config = :config WHERE uuid = :uuid'),
                    {'config': json.dumps(migrated_config), 'uuid': pipeline_uuid},
                )
        except Exception:
            # Skip invalid configs
            continue


def downgrade() -> None:
    """Downgrade is not supported for data migration."""
    # No downgrade - keep configs in new format
    pass
