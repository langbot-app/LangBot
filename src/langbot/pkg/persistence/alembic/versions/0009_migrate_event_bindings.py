"""Migrate legacy Bot routes into Pipeline event bindings.

Bindings keep referencing the original Pipeline UUIDs. This migration never
creates Agent rows or copies Pipeline runner configuration.

Revision ID: 0009_migrate_event_bindings
Revises: 0008_agent_product_surface
Create Date: 2026-06-26
"""

import json
import uuid

import sqlalchemy as sa
from alembic import op

revision = '0009_migrate_event_bindings'
down_revision = '0008_agent_product_surface'
depends_on = None


def _table_exists(table_name: str) -> bool:
    return table_name in sa.inspect(op.get_bind()).get_table_names()


def _column_exists(table_name: str, column_name: str) -> bool:
    if not _table_exists(table_name):
        return False
    return column_name in {column['name'] for column in sa.inspect(op.get_bind()).get_columns(table_name)}


def _rule_to_filters(rule: dict) -> list[dict] | None:
    """Convert one legacy Pipeline routing rule to an EBA event filter."""
    rule_type = rule.get('type')
    operator = rule.get('operator', 'eq')
    value = rule.get('value', '')

    if rule_type == 'launcher_type':
        return [{'field': 'chat_type', 'operator': operator, 'value': value}]
    if rule_type == 'launcher_id':
        return [{'field': 'chat_id', 'operator': operator, 'value': value}]
    if rule_type == 'message_content':
        return [{'field': 'message_text', 'operator': operator, 'value': value}]
    if rule_type == 'message_has_element':
        element_operator = {
            'eq': 'contains',
            'neq': 'not_contains',
        }.get(operator)
        if element_operator is None:
            # The legacy matcher treated every other operator as non-matching.
            element_operator = 'unsupported_legacy_operator'
        return [{'field': 'message_element_types', 'operator': element_operator, 'value': value}]

    return None


def upgrade() -> None:
    if not _table_exists('bots') or not _column_exists('bots', 'event_bindings'):
        return
    if not _column_exists('bots', 'use_pipeline_uuid') or not _column_exists('bots', 'pipeline_routing_rules'):
        return

    bind = op.get_bind()
    rows = bind.execute(
        sa.text('SELECT uuid, use_pipeline_uuid, pipeline_routing_rules, event_bindings FROM bots')
    ).fetchall()

    for bot_uuid, use_pipeline_uuid, routing_rules_raw, event_bindings_raw in rows:
        try:
            existing = (
                json.loads(event_bindings_raw) if isinstance(event_bindings_raw, str) else (event_bindings_raw or [])
            )
        except Exception:
            existing = []

        if existing:
            continue  # already has event_bindings — skip

        try:
            routing_rules = (
                json.loads(routing_rules_raw) if isinstance(routing_rules_raw, str) else (routing_rules_raw or [])
            )
        except Exception:
            routing_rules = []

        new_bindings: list[dict] = []
        base_priority = len(routing_rules)

        for i, rule in enumerate(routing_rules):
            target_uuid = rule.get('pipeline_uuid', '')
            if not target_uuid:
                continue
            filters = _rule_to_filters(rule)
            if filters is None:
                continue
            new_bindings.append(
                {
                    'id': str(uuid.uuid4()),
                    'event_pattern': 'message.*',
                    'target_type': 'pipeline',
                    'target_uuid': target_uuid,
                    'filters': filters,
                    'priority': base_priority - i,
                    'enabled': True,
                    'description': f'Migrated from routing rule ({rule.get("type")})',
                    'order': i,
                }
            )

        if use_pipeline_uuid:
            new_bindings.append(
                {
                    'id': str(uuid.uuid4()),
                    'event_pattern': 'message.*',
                    'target_type': 'pipeline',
                    'target_uuid': use_pipeline_uuid,
                    'filters': [],
                    'priority': 0,
                    'enabled': True,
                    'description': 'Migrated from default pipeline binding',
                    'order': len(new_bindings),
                }
            )

        if new_bindings:
            bind.execute(
                sa.text('UPDATE bots SET event_bindings = :b WHERE uuid = :u'),
                {'b': json.dumps(new_bindings, ensure_ascii=False), 'u': bot_uuid},
            )


def downgrade() -> None:
    pass  # not reversible
