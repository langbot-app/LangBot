"""Migrate pipeline config to new runner format

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

# Mapping from old built-in runner names to official plugin runner IDs
OLD_RUNNER_TO_PLUGIN_RUNNER_ID = {
    'local-agent': 'plugin:langbot/local-agent/default',
    'dify-service-api': 'plugin:langbot/dify-agent/default',
    'n8n-service-api': 'plugin:langbot/n8n-agent/default',
    'coze-api': 'plugin:langbot/coze-agent/default',
    'dashscope-app-api': 'plugin:langbot/dashscope-agent/default',
    'langflow-api': 'plugin:langbot/langflow-agent/default',
    'tbox-app-api': 'plugin:langbot/tbox-agent/default',
}


def is_plugin_runner_id(runner_id: str) -> bool:
    """Check if runner ID is in plugin:* format."""
    return runner_id.startswith('plugin:')


def migrate_pipeline_config(config: dict) -> dict:
    """Migrate pipeline config to new format."""
    new_config = dict(config)
    ai_config = new_config.get('ai', {})
    if not ai_config:
        return new_config

    runner_config = ai_config.get('runner', {})
    runner_configs = ai_config.get('runner_config', {})

    # Check for new format first
    runner_id = runner_config.get('id')
    if runner_id and is_plugin_runner_id(runner_id):
        # Already in new format, no need to migrate
        return new_config

    # Check for old format
    old_runner_name = runner_config.get('runner')
    if old_runner_name:
        # Map to new runner ID
        if is_plugin_runner_id(old_runner_name):
            runner_id = old_runner_name
        else:
            runner_id = OLD_RUNNER_TO_PLUGIN_RUNNER_ID.get(old_runner_name, old_runner_name)

        # Set new format
        runner_config['id'] = runner_id

        # Remove old runner field if it's a mapped built-in runner
        if old_runner_name in OLD_RUNNER_TO_PLUGIN_RUNNER_ID:
            del runner_config['runner']

        # Migrate runner-specific config and remove old config blocks
        if old_runner_name in ai_config:
            old_runner_config = ai_config[old_runner_name]
            if old_runner_config:
                runner_configs[runner_id] = old_runner_config
            # Remove old config block after migration
            del ai_config[old_runner_name]

        # Also check if runner_id has config under other old name formats
        for old_name, mapped_id in OLD_RUNNER_TO_PLUGIN_RUNNER_ID.items():
            if mapped_id == runner_id and old_name in ai_config:
                runner_configs[runner_id] = ai_config[old_name]
                # Remove old config block after migration
                del ai_config[old_name]

    # Update configs
    ai_config['runner'] = runner_config
    ai_config['runner_config'] = runner_configs
    new_config['ai'] = ai_config

    return new_config


def upgrade() -> None:
    """Migrate existing pipeline configs to new runner format."""
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
                    {'config': json.dumps(migrated_config), 'uuid': pipeline_uuid}
                )
        except Exception:
            # Skip invalid configs
            continue


def downgrade() -> None:
    """Downgrade is not supported for data migration."""
    # No downgrade - keep configs in new format
    pass