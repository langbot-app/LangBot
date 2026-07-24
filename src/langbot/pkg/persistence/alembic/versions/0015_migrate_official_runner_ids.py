"""Migrate official AgentRunner IDs to their marketplace identities.

Revision ID: 0015_official_runner_ids
Revises: 0014_interaction_delivery
"""

from __future__ import annotations

import hashlib
import json
import typing

import sqlalchemy as sa
from alembic import op


revision = '0015_official_runner_ids'
down_revision = '0014_interaction_delivery'
branch_labels = None
depends_on = None


_RUNNER_ID_RENAMES = {
    'plugin:langbot/acp-agent-runner/default': 'plugin:langbot-team/ACPAgentRunner/default',
    'plugin:langbot/claude-code-agent/default': 'plugin:langbot-team/ClaudeCodeAgent/default',
    'plugin:langbot/codex-agent/default': 'plugin:langbot-team/CodexAgent/default',
    'plugin:langbot/coze-agent/default': 'plugin:langbot-team/CozeAgent/default',
    'plugin:langbot/dashscope-agent/default': 'plugin:langbot-team/DashScopeAgent/default',
    'plugin:langbot/deerflow-agent/default': 'plugin:langbot-team/DeerFlowAgent/default',
    'plugin:langbot/dify-agent/default': 'plugin:langbot-team/DifyAgent/default',
    'plugin:langbot/langflow-agent/default': 'plugin:langbot-team/LangflowAgent/default',
    'plugin:langbot/n8n-agent/default': 'plugin:langbot-team/N8nAgent/default',
    'plugin:langbot/tbox-agent/default': 'plugin:langbot-team/TboxAgent/default',
    'plugin:langbot/weknora-agent/default': 'plugin:langbot-team/WeKnoraAgent/default',
}

_JSON_COLUMNS = {
    'legacy_pipelines': ('uuid', ('config',)),
    'agents': ('uuid', ('config',)),
    'workflows': ('uuid', ('definition', 'global_config')),
}

_TEXT_COLUMNS = {
    'agents': ('uuid', ('component_ref',)),
    'agent_run': ('id', ('runner_id', 'binding_id')),
    'agent_interaction': ('id', ('runner_id', 'binding_id')),
    'event_log': ('id', ('runner_id',)),
    'transcript': ('id', ('runner_id',)),
}


def _table_columns(table_name: str) -> set[str]:
    inspector = sa.inspect(op.get_bind())
    if table_name not in inspector.get_table_names():
        return set()
    return {column['name'] for column in inspector.get_columns(table_name)}


def _rewrite_text(value: typing.Any, renames: dict[str, str]) -> typing.Any:
    if not isinstance(value, str):
        return value
    for old_id, new_id in renames.items():
        value = value.replace(old_id, new_id)
    return value


def _rewrite_json_value(value: typing.Any, renames: dict[str, str]) -> typing.Any:
    if isinstance(value, dict):
        result: dict[str, typing.Any] = {}
        renamed_items: list[tuple[str, typing.Any]] = []
        for key, item in value.items():
            rewritten_key = _rewrite_text(key, renames)
            if rewritten_key != key:
                renamed_items.append((rewritten_key, item))
            else:
                result[key] = _rewrite_json_value(item, renames)
        for rewritten_key, item in renamed_items:
            result.setdefault(rewritten_key, _rewrite_json_value(item, renames))
        return result
    if isinstance(value, list):
        return [_rewrite_json_value(item, renames) for item in value]
    return _rewrite_text(value, renames)


def _rewrite_json_columns(table_name: str, primary_key: str, columns: tuple[str, ...], renames: dict[str, str]) -> None:
    available_columns = _table_columns(table_name)
    if primary_key not in available_columns or not set(columns) <= available_columns:
        return

    bind = op.get_bind()
    selected_columns = ', '.join((primary_key, *columns))
    rows = bind.execute(sa.text(f'SELECT {selected_columns} FROM {table_name}')).mappings().all()
    for row in rows:
        updates: dict[str, str] = {}
        for column in columns:
            raw_value = row[column]
            if raw_value is None:
                continue
            try:
                decoded = json.loads(raw_value) if isinstance(raw_value, str) else raw_value
            except (TypeError, ValueError):
                continue
            rewritten = _rewrite_json_value(decoded, renames)
            if rewritten != decoded:
                updates[column] = json.dumps(rewritten, ensure_ascii=False, separators=(',', ':'))
        if not updates:
            continue
        assignments = ', '.join(f'{column} = :{column}' for column in updates)
        bind.execute(
            sa.text(f'UPDATE {table_name} SET {assignments} WHERE {primary_key} = :_pk'),
            {**updates, '_pk': row[primary_key]},
        )


def _rewrite_text_columns(table_name: str, primary_key: str, columns: tuple[str, ...], renames: dict[str, str]) -> None:
    available_columns = _table_columns(table_name)
    if primary_key not in available_columns or not set(columns) <= available_columns:
        return

    bind = op.get_bind()
    selected_columns = ', '.join((primary_key, *columns))
    rows = bind.execute(sa.text(f'SELECT {selected_columns} FROM {table_name}')).mappings().all()
    for row in rows:
        updates = {
            column: rewritten for column in columns if (rewritten := _rewrite_text(row[column], renames)) != row[column]
        }
        if not updates:
            continue
        assignments = ', '.join(f'{column} = :{column}' for column in updates)
        bind.execute(
            sa.text(f'UPDATE {table_name} SET {assignments} WHERE {primary_key} = :_pk'),
            {**updates, '_pk': row[primary_key]},
        )


def _state_scope_key(row: typing.Mapping[str, typing.Any], runner_id: str, binding_identity: str) -> str | None:
    scope = row['scope']
    parts = {
        'runner_id': runner_id,
        'binding_identity': binding_identity,
        'bot_id': row['bot_id'],
        'workspace_id': row['workspace_id'],
    }
    if scope == 'conversation':
        parts.update(conversation_id=row['conversation_id'], thread_id=row['thread_id'])
    elif scope == 'actor':
        parts.update(actor_type=row['actor_type'] or 'user', actor_id=row['actor_id'])
    elif scope == 'subject':
        parts.update(subject_type=row['subject_type'] or 'unknown', subject_id=row['subject_id'])
    elif scope != 'runner':
        return None

    payload = {'version': 2, 'scope': scope, **parts}
    raw = json.dumps(payload, sort_keys=True, separators=(',', ':'), ensure_ascii=False)
    return f'{scope}:v2:{hashlib.sha256(raw.encode("utf-8")).hexdigest()}'


def _rewrite_runner_state(renames: dict[str, str]) -> None:
    table_name = 'agent_runner_state'
    required_columns = {
        'id',
        'runner_id',
        'binding_identity',
        'scope',
        'scope_key',
        'state_key',
        'bot_id',
        'workspace_id',
        'conversation_id',
        'thread_id',
        'actor_type',
        'actor_id',
        'subject_type',
        'subject_id',
    }
    if not required_columns <= _table_columns(table_name):
        return

    bind = op.get_bind()
    rows = bind.execute(sa.text(f'SELECT {", ".join(sorted(required_columns))} FROM {table_name}')).mappings().all()
    for row in rows:
        runner_id = _rewrite_text(row['runner_id'], renames)
        binding_identity = _rewrite_text(row['binding_identity'], renames)
        if runner_id == row['runner_id'] and binding_identity == row['binding_identity']:
            continue
        scope_key = _state_scope_key(row, runner_id, binding_identity) or row['scope_key']
        collision = bind.execute(
            sa.text(
                'SELECT id FROM agent_runner_state '
                'WHERE scope_key = :scope_key AND state_key = :state_key AND id != :id'
            ),
            {'scope_key': scope_key, 'state_key': row['state_key'], 'id': row['id']},
        ).scalar_one_or_none()
        if collision is not None:
            bind.execute(sa.text('DELETE FROM agent_runner_state WHERE id = :id'), {'id': row['id']})
            continue
        bind.execute(
            sa.text(
                'UPDATE agent_runner_state '
                'SET runner_id = :runner_id, binding_identity = :binding_identity, scope_key = :scope_key '
                'WHERE id = :id'
            ),
            {
                'runner_id': runner_id,
                'binding_identity': binding_identity,
                'scope_key': scope_key,
                'id': row['id'],
            },
        )


def _migrate(renames: dict[str, str]) -> None:
    for table_name, (primary_key, columns) in _JSON_COLUMNS.items():
        _rewrite_json_columns(table_name, primary_key, columns, renames)
    for table_name, (primary_key, columns) in _TEXT_COLUMNS.items():
        _rewrite_text_columns(table_name, primary_key, columns, renames)
    _rewrite_runner_state(renames)


def upgrade() -> None:
    _migrate(_RUNNER_ID_RENAMES)


def downgrade() -> None:
    _migrate({new_id: old_id for old_id, new_id in _RUNNER_ID_RENAMES.items()})
