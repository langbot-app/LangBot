"""Normalize AgentRunner config containers

Revision ID: 0004_migrate_runner_config
Revises: 0003_add_rerank_models
Create Date: 2026-05-10
"""

import json
import sqlalchemy as sa
from alembic import op

revision = '0004_migrate_runner_config'
down_revision = '0003_add_rerank_models'
branch_labels = None
depends_on = None

def migrate_pipeline_config(config: dict) -> dict:
    """Keep current AgentRunner config containers explicit."""
    new_config = dict(config)
    if 'ai' not in new_config:
        return new_config

    ai_config = dict(new_config.get('ai', {}))

    ai_config['runner'] = dict(ai_config.get('runner', {}))
    ai_config['runner_config'] = dict(ai_config.get('runner_config', {}))
    new_config['ai'] = ai_config

    return new_config


def upgrade() -> None:
    """Normalize existing pipeline config containers."""
    conn = op.get_bind()
    inspector = sa.inspect(conn)

    # Check if pipelines table exists (may not exist in fresh install)
    if 'pipelines' not in inspector.get_table_names():
        return

    # Get all pipelines
    result = conn.execute(sa.text('SELECT uuid, config FROM pipelines'))
    pipelines = result.fetchall()

    for pipeline_uuid, config_json in pipelines:
        if not config_json:
            continue

        try:
            config = json.loads(config_json)
            migrated_config = migrate_pipeline_config(config)

            # Only update if config changed
            if json.dumps(config, sort_keys=True) != json.dumps(migrated_config, sort_keys=True):
                conn.execute(
                    sa.text('UPDATE pipelines SET config = :config WHERE uuid = :uuid'),
                    {'config': json.dumps(migrated_config), 'uuid': pipeline_uuid},
                )
        except Exception:
            # Skip invalid configs
            continue


def downgrade() -> None:
    """Downgrade is not supported for data migration."""
    # No downgrade - keep configs in new format
    pass
