"""repair an ownerless local Workspace after tenancy migration

Revision ID: 0017_local_owner_repair
Revises: 0016_agent_workspace
Create Date: 2026-07-31
"""

from __future__ import annotations

import datetime
import uuid

import sqlalchemy as sa
from alembic import op


revision = '0017_local_owner_repair'
down_revision = '0016_agent_workspace'
branch_labels = None
depends_on = None


def _table_names(conn: sa.Connection) -> set[str]:
    return set(sa.inspect(conn).get_table_names())


def upgrade() -> None:
    conn = op.get_bind()
    required = {'metadata', 'users', 'workspaces', 'workspace_memberships'}
    if not required.issubset(_table_names(conn)):
        return

    metadata = sa.table(
        'metadata',
        sa.column('key', sa.String(255)),
        sa.column('value', sa.String(255)),
    )
    instance_uuid = conn.execute(
        sa.select(metadata.c.value).where(metadata.c.key == 'instance_uuid')
    ).scalar_one_or_none()
    if not isinstance(instance_uuid, str) or not instance_uuid.strip():
        return

    workspaces = sa.table(
        'workspaces',
        sa.column('uuid', sa.String(36)),
        sa.column('instance_uuid', sa.String(255)),
        sa.column('source', sa.String(32)),
        sa.column('created_by_account_uuid', sa.String(36)),
    )
    workspace_uuids = conn.execute(
        sa.select(workspaces.c.uuid).where(
            workspaces.c.instance_uuid == instance_uuid.strip(),
            workspaces.c.source == 'local',
        )
    ).scalars().all()
    if not workspace_uuids:
        return
    if len(workspace_uuids) > 1:
        raise RuntimeError(f'Multiple local Workspaces exist for instance {instance_uuid!r}')
    workspace_uuid = workspace_uuids[0]

    if conn.dialect.name == 'postgresql':
        conn.execute(
            sa.text("SELECT set_config('langbot.workspace_uuid', :workspace_uuid, true)"),
            {'workspace_uuid': workspace_uuid},
        )

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
    active_owner = conn.execute(
        sa.select(memberships.c.account_uuid).where(
            memberships.c.workspace_uuid == workspace_uuid,
            memberships.c.role == 'owner',
            memberships.c.status == 'active',
        )
    ).scalar_one_or_none()
    if active_owner is not None:
        conn.execute(
            workspaces.update()
            .where(workspaces.c.uuid == workspace_uuid)
            .where(workspaces.c.created_by_account_uuid.is_(None))
            .values(created_by_account_uuid=active_owner)
        )
        return

    users = sa.table(
        'users',
        sa.column('id', sa.Integer()),
        sa.column('uuid', sa.String(36)),
        sa.column('status', sa.String(32)),
    )
    owner_account_uuid = conn.execute(
        sa.select(users.c.uuid)
        .where(users.c.status == 'active')
        .order_by(users.c.id)
        .limit(1)
    ).scalar_one_or_none()
    if owner_account_uuid is None:
        return

    now = datetime.datetime.now(datetime.UTC).replace(tzinfo=None)
    membership = conn.execute(
        sa.select(memberships.c.uuid, memberships.c.joined_at).where(
            memberships.c.workspace_uuid == workspace_uuid,
            memberships.c.account_uuid == owner_account_uuid,
        )
    ).first()
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
    conn.execute(
        workspaces.update()
        .where(workspaces.c.uuid == workspace_uuid)
        .values(created_by_account_uuid=owner_account_uuid)
    )


def downgrade() -> None:
    # The repair restores a required invariant; downgrading the revision should
    # not deliberately recreate an ownerless Workspace.
    pass
