"""Move trigger, safety and general output settings from Messaging to bots.

Each bot gets a ``message_policy``. So that nothing behaves differently after
the upgrade, an existing bot's own policy is neutral (admit everything, change
nothing) and every route pointing at a Messaging processor receives a copy of
the settings that processor used to carry, as the route's policy override.

The moved keys are kept verbatim in ``legacy_pipelines.message_policy_backup``
and put back on downgrade.
"""

from __future__ import annotations

import copy
import json

from alembic import op
import sqlalchemy as sa

from langbot.pkg.message_policy import schema as policy_schema

revision = '0049_bot_message_policy'
down_revision = '0048_platform_command_sync'
branch_labels = None
depends_on = None


def _json(value):
    """Return a JSON column value as Python data; some rows hold it as text."""
    if isinstance(value, (str, bytes)):
        try:
            return json.loads(value)
        except (TypeError, ValueError):
            return None
    return value


def _columns(inspector, table: str) -> set[str]:
    return {column['name'] for column in inspector.get_columns(table)}


def _table(name: str, columns: set[str], wanted: tuple[str, ...]) -> sa.TableClause:
    """A lightweight table over the wanted columns that actually exist."""
    json_columns = {'config', 'message_policy_backup', 'event_bindings', 'message_policy'}
    return sa.table(
        name,
        *(
            sa.column(column, sa.JSON() if column in json_columns else sa.String())
            for column in wanted
            if column in columns
        ),
    )


def _scope(row) -> str:
    """Workspace of a row; installations that predate workspaces have one implicit scope."""
    return str(row.get('workspace_uuid') or '')


def _same_row(table: sa.TableClause, row):
    conditions = [table.c.uuid == row['uuid']]
    if 'workspace_uuid' in table.c:
        conditions.append(table.c.workspace_uuid == row['workspace_uuid'])
    return sa.and_(*conditions)


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    # Partial schemas (a table or its JSON column missing) have nothing to convert.
    has_bots = inspector.has_table('bots') and {'uuid', 'event_bindings'} <= _columns(inspector, 'bots')
    has_pipelines = inspector.has_table('legacy_pipelines') and {'uuid', 'config'} <= _columns(
        inspector, 'legacy_pipelines'
    )

    bots_had_policy = has_bots and 'message_policy' in _columns(inspector, 'bots')
    if has_bots and not bots_had_policy:
        with op.batch_alter_table('bots') as batch:
            batch.add_column(sa.Column('message_policy', sa.JSON(), nullable=False, server_default='{}'))
    if has_pipelines and 'message_policy_backup' not in _columns(inspector, 'legacy_pipelines'):
        with op.batch_alter_table('legacy_pipelines') as batch:
            batch.add_column(sa.Column('message_policy_backup', sa.JSON(), nullable=True))

    # (workspace, processor) -> the policy override that reproduces its old settings.
    overrides: dict[tuple[str, str], dict] = {}
    if has_pipelines:
        inspector = sa.inspect(bind)
        pipelines = _table(
            'legacy_pipelines',
            _columns(inspector, 'legacy_pipelines'),
            ('uuid', 'workspace_uuid', 'config', 'message_policy_backup'),
        )
        for row in bind.execute(sa.select(pipelines)).mappings().all():
            config = _json(row['config'])
            if not isinstance(config, dict):
                continue
            remaining, moved = policy_schema.extract_legacy_policy(config)
            if not moved:
                # Already converted (a re-run): the backup still tells what it carried.
                moved = _json(row['message_policy_backup'])
                if isinstance(moved, dict) and moved:
                    overrides[(_scope(row), row['uuid'])] = policy_schema.policy_from_legacy(moved)
                continue
            overrides[(_scope(row), row['uuid'])] = policy_schema.policy_from_legacy(moved)
            bind.execute(
                pipelines.update()
                .where(_same_row(pipelines, row))
                .values(config=remaining, message_policy_backup=moved)
            )

    if not has_bots:
        return
    bots = _table(
        'bots',
        _columns(sa.inspect(bind), 'bots'),
        ('uuid', 'workspace_uuid', 'event_bindings', 'message_policy'),
    )
    for row in bind.execute(sa.select(bots)).mappings().all():
        values: dict = {}
        if not bots_had_policy:
            values['message_policy'] = policy_schema.neutral_policy()
        bindings = _json(row['event_bindings'])
        if isinstance(bindings, list):
            changed = False
            for binding in bindings:
                if not isinstance(binding, dict) or binding.get('target_type') != 'pipeline':
                    continue
                if 'policy' in binding:
                    continue
                override = overrides.get((_scope(row), str(binding.get('target_uuid') or '')))
                if override:
                    binding['policy'] = copy.deepcopy(override)
                    changed = True
            if changed:
                values['event_bindings'] = bindings
        if values:
            bind.execute(bots.update().where(_same_row(bots, row)).values(**values))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    has_bots = inspector.has_table('bots')
    has_pipelines = inspector.has_table('legacy_pipelines')
    bot_columns = _columns(inspector, 'bots') if has_bots else set()
    pipeline_columns = _columns(inspector, 'legacy_pipelines') if has_pipelines else set()
    bots_have_policy = 'message_policy' in bot_columns

    # Processors created after the upgrade have no backup. Give them the policy
    # of a route that used them, so the older version finds its settings.
    route_policies: dict[tuple[str, str], dict] = {}
    if {'uuid', 'event_bindings'} <= bot_columns:
        bots = _table('bots', bot_columns, ('uuid', 'workspace_uuid', 'event_bindings', 'message_policy'))
        for row in bind.execute(sa.select(bots)).mappings().all():
            bindings = _json(row['event_bindings'])
            if not isinstance(bindings, list):
                continue
            bot_policy = _json(row['message_policy']) if bots_have_policy else None
            changed = False
            for binding in bindings:
                if not isinstance(binding, dict):
                    continue
                if binding.get('target_type') == 'pipeline' and binding.get('target_uuid'):
                    key = (_scope(row), str(binding['target_uuid']))
                    route_policies.setdefault(key, policy_schema.resolve_policy(bot_policy, binding.get('policy')))
                if 'policy' in binding:
                    del binding['policy']
                    changed = True
            if changed:
                bind.execute(bots.update().where(_same_row(bots, row)).values(event_bindings=bindings))

    if 'message_policy_backup' in pipeline_columns:
        if {'uuid', 'config'} <= pipeline_columns:
            pipelines = _table(
                'legacy_pipelines',
                pipeline_columns,
                ('uuid', 'workspace_uuid', 'config', 'message_policy_backup'),
            )
            for row in bind.execute(sa.select(pipelines)).mappings().all():
                config = _json(row['config'])
                if not isinstance(config, dict):
                    continue
                moved = _json(row['message_policy_backup'])
                if not isinstance(moved, dict) or not moved:
                    if 'trigger' in config and 'safety' in config:
                        continue
                    moved = policy_schema.policy_to_legacy(
                        route_policies.get((_scope(row), row['uuid'])) or policy_schema.default_policy()
                    )
                bind.execute(
                    pipelines.update()
                    .where(_same_row(pipelines, row))
                    .values(config=policy_schema.restore_legacy_config(config, moved))
                )
        with op.batch_alter_table('legacy_pipelines') as batch:
            batch.drop_column('message_policy_backup')

    if bots_have_policy:
        with op.batch_alter_table('bots') as batch:
            batch.drop_column('message_policy')
