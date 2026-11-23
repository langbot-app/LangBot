"""add mcp resource preferences to pipelines

Revision ID: 0008_mcp_resource_prefs
Revises: 0007_add_bot_admins
Create Date: 2026-06-30
"""

from __future__ import annotations

import json
from typing import Any

import sqlalchemy as sa
from alembic import op

revision = '0008_mcp_resource_prefs'
down_revision = '0007_add_bot_admins'
branch_labels = None
depends_on = None


_PIPELINE_TABLE = sa.table(
    'legacy_pipelines',
    sa.column('uuid', sa.String(255)),
    sa.column('extensions_preferences', sa.JSON()),
)


def _has_extensions_preferences_table(conn: sa.Connection) -> bool:
    inspector = sa.inspect(conn)
    if 'legacy_pipelines' not in inspector.get_table_names():
        return False
    columns = {column['name'] for column in inspector.get_columns('legacy_pipelines')}
    return 'extensions_preferences' in columns


def _decode_preferences(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    if isinstance(value, str):
        try:
            decoded = json.loads(value)
        except json.JSONDecodeError:
            return {}
        if isinstance(decoded, dict):
            return decoded
    return {}


def _update_preferences(conn: sa.Connection, uuid: str, preferences: dict[str, Any]) -> None:
    conn.execute(
        _PIPELINE_TABLE.update().where(_PIPELINE_TABLE.c.uuid == uuid).values(extensions_preferences=preferences)
    )


def upgrade() -> None:
    conn = op.get_bind()
    if not _has_extensions_preferences_table(conn):
        return

    rows = conn.execute(sa.select(_PIPELINE_TABLE.c.uuid, _PIPELINE_TABLE.c.extensions_preferences)).all()
    for uuid, raw_preferences in rows:
        preferences = _decode_preferences(raw_preferences)
        changed = False

        if 'mcp_resources' not in preferences:
            preferences['mcp_resources'] = []
            changed = True
        if 'mcp_resource_agent_read_enabled' not in preferences:
            preferences['mcp_resource_agent_read_enabled'] = True
            changed = True

        if changed:
            _update_preferences(conn, uuid, preferences)


def downgrade() -> None:
    conn = op.get_bind()
    if not _has_extensions_preferences_table(conn):
        return

    rows = conn.execute(sa.select(_PIPELINE_TABLE.c.uuid, _PIPELINE_TABLE.c.extensions_preferences)).all()
    for uuid, raw_preferences in rows:
        preferences = _decode_preferences(raw_preferences)
        changed = False

        for key in ('mcp_resources', 'mcp_resource_agent_read_enabled'):
            if key in preferences:
                preferences.pop(key)
                changed = True

        if changed:
            _update_preferences(conn, uuid, preferences)
