"""add the workspace tenancy persistence kernel

Revision ID: 0009_workspace_tenancy
Revises: 0008_mcp_resource_prefs
Create Date: 2026-07-18
"""

from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from alembic import op

revision = '0009_workspace_tenancy'
down_revision = '0008_mcp_resource_prefs'
branch_labels = None
depends_on = None


def _table_names(conn: sa.Connection) -> set[str]:
    return set(sa.inspect(conn).get_table_names())


def _column_map(conn: sa.Connection, table_name: str) -> dict[str, dict]:
    return {column['name']: column for column in sa.inspect(conn).get_columns(table_name)}


def _constraint_names(conn: sa.Connection, table_name: str) -> set[str]:
    inspector = sa.inspect(conn)
    names = {
        constraint['name']
        for constraint in inspector.get_check_constraints(table_name)
        if constraint.get('name') is not None
    }
    names.update(
        constraint['name']
        for constraint in inspector.get_unique_constraints(table_name)
        if constraint.get('name') is not None
    )
    return names


def _index_names(conn: sa.Connection, table_name: str) -> set[str]:
    return {index['name'] for index in sa.inspect(conn).get_indexes(table_name)}


def _upgrade_users(conn: sa.Connection) -> None:
    if 'users' not in _table_names(conn):
        return

    columns = _column_map(conn, 'users')
    if 'uuid' not in columns:
        op.add_column('users', sa.Column('uuid', sa.String(36), nullable=True))
    if 'status' not in columns:
        op.add_column('users', sa.Column('status', sa.String(32), nullable=True, server_default='active'))
    if 'source' not in columns:
        op.add_column('users', sa.Column('source', sa.String(32), nullable=True, server_default='local'))
    if 'projection_revision' not in columns:
        op.add_column(
            'users',
            sa.Column('projection_revision', sa.BigInteger(), nullable=True, server_default='0'),
        )

    users = sa.table(
        'users',
        sa.column('id', sa.Integer()),
        sa.column('uuid', sa.String(36)),
        sa.column('status', sa.String(32)),
        sa.column('source', sa.String(32)),
        sa.column('projection_revision', sa.BigInteger()),
    )

    seen_uuids: set[str] = set()
    for user_id, account_uuid in conn.execute(sa.select(users.c.id, users.c.uuid).order_by(users.c.id)).all():
        normalized_uuid = account_uuid.strip() if isinstance(account_uuid, str) else ''
        try:
            normalized_uuid = str(uuid.UUID(normalized_uuid))
        except (ValueError, AttributeError):
            normalized_uuid = ''
        if not normalized_uuid or normalized_uuid in seen_uuids:
            normalized_uuid = str(uuid.uuid4())
        if normalized_uuid != account_uuid:
            conn.execute(users.update().where(users.c.id == user_id).values(uuid=normalized_uuid))
        seen_uuids.add(normalized_uuid)

    conn.execute(users.update().where(users.c.status.is_(None)).values(status='active'))
    conn.execute(users.update().where(users.c.source.is_(None)).values(source='local'))
    conn.execute(users.update().where(users.c.projection_revision.is_(None)).values(projection_revision=0))

    columns = _column_map(conn, 'users')
    constraint_names = _constraint_names(conn, 'users')
    needs_batch_alter = any(
        columns[column_name]['nullable'] for column_name in ('uuid', 'status', 'source', 'projection_revision')
    ) or not {'ck_users_status', 'ck_users_source'}.issubset(constraint_names)

    if needs_batch_alter:
        with op.batch_alter_table('users') as batch_op:
            if columns['uuid']['nullable']:
                batch_op.alter_column('uuid', existing_type=sa.String(36), nullable=False)
            if columns['status']['nullable']:
                batch_op.alter_column(
                    'status',
                    existing_type=sa.String(32),
                    nullable=False,
                    server_default='active',
                )
            if columns['source']['nullable']:
                batch_op.alter_column(
                    'source',
                    existing_type=sa.String(32),
                    nullable=False,
                    server_default='local',
                )
            if columns['projection_revision']['nullable']:
                batch_op.alter_column(
                    'projection_revision',
                    existing_type=sa.BigInteger(),
                    nullable=False,
                    server_default='0',
                )
            if 'ck_users_status' not in constraint_names:
                batch_op.create_check_constraint(
                    'ck_users_status',
                    "status IN ('active', 'disabled', 'deleted')",
                )
            if 'ck_users_source' not in constraint_names:
                batch_op.create_check_constraint(
                    'ck_users_source',
                    "source IN ('local', 'cloud_projection')",
                )

    if 'uq_users_uuid' not in _index_names(conn, 'users'):
        op.create_index('uq_users_uuid', 'users', ['uuid'], unique=True)


def _create_workspace_tables(conn: sa.Connection) -> None:
    tables = _table_names(conn)
    if 'users' not in tables:
        # LangBot's supported startup path creates the baseline schema before
        # Alembic runs. Keep direct Alembic probes on an empty database safe.
        return

    if 'workspaces' not in tables:
        op.create_table(
            'workspaces',
            sa.Column('uuid', sa.String(36), primary_key=True),
            sa.Column('instance_uuid', sa.String(255), nullable=False),
            sa.Column('name', sa.String(255), nullable=False),
            sa.Column('slug', sa.String(255), nullable=False),
            sa.Column('type', sa.String(32), nullable=False, server_default='team'),
            sa.Column('status', sa.String(32), nullable=False, server_default='active'),
            sa.Column('created_by_account_uuid', sa.String(36), nullable=True),
            sa.Column('source', sa.String(32), nullable=False, server_default='local'),
            sa.Column('projection_revision', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ['created_by_account_uuid'],
                ['users.uuid'],
                name='fk_workspaces_created_by_account',
                ondelete='SET NULL',
            ),
            sa.UniqueConstraint('instance_uuid', 'slug', name='uq_workspaces_instance_slug'),
            sa.CheckConstraint("type IN ('personal', 'team')", name='ck_workspaces_type'),
            sa.CheckConstraint(
                "status IN ('provisioning', 'active', 'suspended', 'archived', 'deleted')",
                name='ck_workspaces_status',
            ),
            sa.CheckConstraint(
                "source IN ('local', 'cloud_projection')",
                name='ck_workspaces_source',
            ),
        )
    workspace_indexes = _index_names(conn, 'workspaces')
    if 'ix_workspaces_instance_status' not in workspace_indexes:
        op.create_index(
            'ix_workspaces_instance_status',
            'workspaces',
            ['instance_uuid', 'status'],
        )
    if 'uq_workspaces_local_instance' not in workspace_indexes:
        op.create_index(
            'uq_workspaces_local_instance',
            'workspaces',
            ['instance_uuid'],
            unique=True,
            sqlite_where=sa.text("source = 'local'"),
            postgresql_where=sa.text("source = 'local'"),
        )

    tables = _table_names(conn)
    if 'workspace_memberships' not in tables:
        op.create_table(
            'workspace_memberships',
            sa.Column('uuid', sa.String(36), primary_key=True),
            sa.Column('workspace_uuid', sa.String(36), nullable=False),
            sa.Column('account_uuid', sa.String(36), nullable=False),
            sa.Column('role', sa.String(32), nullable=False),
            sa.Column('status', sa.String(32), nullable=False, server_default='active'),
            sa.Column('invited_by_account_uuid', sa.String(36), nullable=True),
            sa.Column('joined_at', sa.DateTime(), nullable=True),
            sa.Column('projection_revision', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ['workspace_uuid'],
                ['workspaces.uuid'],
                name='fk_workspace_memberships_workspace',
                ondelete='CASCADE',
            ),
            sa.ForeignKeyConstraint(
                ['account_uuid'],
                ['users.uuid'],
                name='fk_workspace_memberships_account',
                ondelete='CASCADE',
            ),
            sa.ForeignKeyConstraint(
                ['invited_by_account_uuid'],
                ['users.uuid'],
                name='fk_workspace_memberships_invited_by_account',
                ondelete='SET NULL',
            ),
            sa.UniqueConstraint(
                'workspace_uuid',
                'account_uuid',
                name='uq_workspace_membership_account',
            ),
            sa.CheckConstraint(
                "role IN ('owner', 'admin', 'developer', 'operator', 'viewer')",
                name='ck_workspace_memberships_role',
            ),
            sa.CheckConstraint(
                "status IN ('active', 'disabled', 'removed')",
                name='ck_workspace_memberships_status',
            ),
        )
    membership_indexes = _index_names(conn, 'workspace_memberships')
    if 'ix_workspace_memberships_account_status' not in membership_indexes:
        op.create_index(
            'ix_workspace_memberships_account_status',
            'workspace_memberships',
            ['account_uuid', 'status'],
        )

    tables = _table_names(conn)
    if 'workspace_invitations' not in tables:
        op.create_table(
            'workspace_invitations',
            sa.Column('uuid', sa.String(36), primary_key=True),
            sa.Column('workspace_uuid', sa.String(36), nullable=False),
            sa.Column('normalized_email', sa.String(320), nullable=False),
            sa.Column('role', sa.String(32), nullable=False),
            sa.Column('token_hash', sa.String(255), nullable=False),
            sa.Column('status', sa.String(32), nullable=False, server_default='pending'),
            sa.Column('expires_at', sa.DateTime(), nullable=False),
            sa.Column('accepted_at', sa.DateTime(), nullable=True),
            sa.Column('revoked_at', sa.DateTime(), nullable=True),
            sa.Column('created_by_account_uuid', sa.String(36), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ['workspace_uuid'],
                ['workspaces.uuid'],
                name='fk_workspace_invitations_workspace',
                ondelete='CASCADE',
            ),
            sa.ForeignKeyConstraint(
                ['created_by_account_uuid'],
                ['users.uuid'],
                name='fk_workspace_invitations_created_by_account',
                ondelete='CASCADE',
            ),
            sa.CheckConstraint(
                "role IN ('admin', 'developer', 'operator', 'viewer')",
                name='ck_workspace_invitations_role',
            ),
            sa.CheckConstraint(
                "status IN ('pending', 'accepted', 'revoked', 'expired')",
                name='ck_workspace_invitations_status',
            ),
        )
    invitation_indexes = _index_names(conn, 'workspace_invitations')
    if 'uq_workspace_invitations_token_hash' not in invitation_indexes:
        op.create_index(
            'uq_workspace_invitations_token_hash',
            'workspace_invitations',
            ['token_hash'],
            unique=True,
        )
    if 'uq_workspace_invitations_pending_email' not in invitation_indexes:
        op.create_index(
            'uq_workspace_invitations_pending_email',
            'workspace_invitations',
            ['workspace_uuid', 'normalized_email'],
            unique=True,
            sqlite_where=sa.text("status = 'pending'"),
            postgresql_where=sa.text("status = 'pending'"),
        )

    tables = _table_names(conn)
    if 'workspace_execution_states' not in tables:
        op.create_table(
            'workspace_execution_states',
            sa.Column('workspace_uuid', sa.String(36), primary_key=True),
            sa.Column('instance_uuid', sa.String(255), nullable=False),
            sa.Column('active_generation', sa.BigInteger(), nullable=False, server_default='1'),
            sa.Column('state', sa.String(32), nullable=False, server_default='active'),
            sa.Column('write_fenced', sa.Boolean(), nullable=False, server_default=sa.false()),
            sa.Column('source', sa.String(32), nullable=False, server_default='local'),
            sa.Column('desired_state_revision', sa.BigInteger(), nullable=False, server_default='0'),
            sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
            sa.ForeignKeyConstraint(
                ['workspace_uuid'],
                ['workspaces.uuid'],
                name='fk_workspace_execution_states_workspace',
                ondelete='CASCADE',
            ),
            sa.CheckConstraint('active_generation > 0', name='ck_workspace_execution_generation'),
            sa.CheckConstraint(
                "state IN ('provisioning', 'active', 'migrating', 'draining', 'inactive')",
                name='ck_workspace_execution_state',
            ),
            sa.CheckConstraint(
                "source IN ('local', 'cloud')",
                name='ck_workspace_execution_source',
            ),
        )
    execution_indexes = _index_names(conn, 'workspace_execution_states')
    if 'ix_workspace_execution_states_instance_state' not in execution_indexes:
        op.create_index(
            'ix_workspace_execution_states_instance_state',
            'workspace_execution_states',
            ['instance_uuid', 'state'],
        )


def _load_instance_uuid(conn: sa.Connection) -> str | None:
    if 'metadata' not in _table_names(conn):
        return None

    metadata = sa.table(
        'metadata',
        sa.column('key', sa.String(255)),
        sa.column('value', sa.String(255)),
    )
    value = conn.execute(sa.select(metadata.c.value).where(metadata.c.key == 'instance_uuid')).scalar_one_or_none()
    if not isinstance(value, str) or not value.strip():
        return None
    return value.strip()


def _bootstrap_default_workspace(conn: sa.Connection) -> None:
    required_tables = {'users', 'workspaces', 'workspace_memberships', 'workspace_execution_states'}
    if not required_tables.issubset(_table_names(conn)):
        return

    instance_uuid = _load_instance_uuid(conn)
    users_exist = 'users' in _table_names(conn) and bool(conn.execute(sa.text('SELECT 1 FROM users LIMIT 1')).first())
    if instance_uuid is None:
        if users_exist:
            raise RuntimeError("Cannot bootstrap the default workspace without metadata['instance_uuid']")
        return

    workspaces = sa.table(
        'workspaces',
        sa.column('uuid', sa.String(36)),
        sa.column('instance_uuid', sa.String(255)),
        sa.column('name', sa.String(255)),
        sa.column('slug', sa.String(255)),
        sa.column('type', sa.String(32)),
        sa.column('status', sa.String(32)),
        sa.column('created_by_account_uuid', sa.String(36)),
        sa.column('source', sa.String(32)),
        sa.column('projection_revision', sa.BigInteger()),
    )
    local_rows = conn.execute(
        sa.select(workspaces.c.uuid).where(
            workspaces.c.instance_uuid == instance_uuid,
            workspaces.c.source == 'local',
        )
    ).all()
    if len(local_rows) > 1:
        raise RuntimeError(f'Multiple local workspaces already exist for instance {instance_uuid!r}')

    users = sa.table(
        'users',
        sa.column('id', sa.Integer()),
        sa.column('uuid', sa.String(36)),
    )
    owner_account_uuid = None
    if 'users' in _table_names(conn):
        owner_account_uuid = conn.execute(sa.select(users.c.uuid).order_by(users.c.id).limit(1)).scalar_one_or_none()

    if local_rows:
        workspace_uuid = local_rows[0][0]
        if owner_account_uuid is not None:
            conn.execute(
                workspaces.update()
                .where(workspaces.c.uuid == workspace_uuid)
                .where(workspaces.c.created_by_account_uuid.is_(None))
                .values(created_by_account_uuid=owner_account_uuid)
            )
    else:
        workspace_uuid = str(uuid.uuid4())
        conn.execute(
            workspaces.insert().values(
                uuid=workspace_uuid,
                instance_uuid=instance_uuid,
                name='Default Workspace',
                slug='default',
                type='team',
                status='active',
                created_by_account_uuid=owner_account_uuid,
                source='local',
                projection_revision=0,
            )
        )

    execution_states = sa.table(
        'workspace_execution_states',
        sa.column('workspace_uuid', sa.String(36)),
        sa.column('instance_uuid', sa.String(255)),
        sa.column('active_generation', sa.BigInteger()),
        sa.column('state', sa.String(32)),
        sa.column('write_fenced', sa.Boolean()),
        sa.column('source', sa.String(32)),
        sa.column('desired_state_revision', sa.BigInteger()),
    )
    execution_state = conn.execute(
        sa.select(
            execution_states.c.instance_uuid,
            execution_states.c.active_generation,
            execution_states.c.state,
            execution_states.c.write_fenced,
            execution_states.c.source,
        ).where(execution_states.c.workspace_uuid == workspace_uuid)
    ).first()
    if execution_state is None:
        conn.execute(
            execution_states.insert().values(
                workspace_uuid=workspace_uuid,
                instance_uuid=instance_uuid,
                active_generation=1,
                state='active',
                write_fenced=False,
                source='local',
                desired_state_revision=0,
            )
        )
    elif (
        execution_state.instance_uuid != instance_uuid
        or execution_state.active_generation != 1
        or execution_state.state != 'active'
        or execution_state.write_fenced
        or execution_state.source != 'local'
    ):
        raise RuntimeError(f'Default workspace {workspace_uuid!r} has an invalid local execution state')

    if owner_account_uuid is None:
        return

    memberships = sa.table(
        'workspace_memberships',
        sa.column('uuid', sa.String(36)),
        sa.column('workspace_uuid', sa.String(36)),
        sa.column('account_uuid', sa.String(36)),
        sa.column('role', sa.String(32)),
        sa.column('status', sa.String(32)),
        sa.column('joined_at', sa.DateTime()),
        sa.column('projection_revision', sa.BigInteger()),
    )
    membership = conn.execute(
        sa.select(memberships.c.uuid, memberships.c.joined_at).where(
            memberships.c.workspace_uuid == workspace_uuid,
            memberships.c.account_uuid == owner_account_uuid,
        )
    ).first()
    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    if membership is None:
        conn.execute(
            memberships.insert().values(
                uuid=str(uuid.uuid4()),
                workspace_uuid=workspace_uuid,
                account_uuid=owner_account_uuid,
                role='owner',
                status='active',
                joined_at=now,
                projection_revision=0,
            )
        )
    else:
        conn.execute(
            memberships.update()
            .where(memberships.c.uuid == membership.uuid)
            .values(
                role='owner',
                status='active',
                joined_at=membership.joined_at or now,
            )
        )


def upgrade() -> None:
    conn = op.get_bind()
    _upgrade_users(conn)
    _create_workspace_tables(conn)
    _bootstrap_default_workspace(conn)


def downgrade() -> None:
    conn = op.get_bind()
    tables = _table_names(conn)
    for table_name in (
        'workspace_execution_states',
        'workspace_invitations',
        'workspace_memberships',
        'workspaces',
    ):
        if table_name in tables:
            op.drop_table(table_name)

    if 'users' not in _table_names(conn):
        return

    indexes = _index_names(conn, 'users')
    if 'uq_users_uuid' in indexes:
        op.drop_index('uq_users_uuid', table_name='users')

    columns = _column_map(conn, 'users')
    constraint_names = _constraint_names(conn, 'users')
    with op.batch_alter_table('users') as batch_op:
        # SQLite batch recreation otherwise preserves the named checks while
        # dropping their referenced columns, producing ``no such column`` only
        # after the Workspace directory tables have already been removed.
        for constraint_name in ('ck_users_source', 'ck_users_status'):
            if constraint_name in constraint_names:
                batch_op.drop_constraint(constraint_name, type_='check')
        for column_name in ('projection_revision', 'source', 'status', 'uuid'):
            if column_name in columns:
                batch_op.drop_column(column_name)
