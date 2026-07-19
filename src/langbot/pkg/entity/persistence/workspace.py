from __future__ import annotations

import enum
import uuid as uuid_lib

import sqlalchemy

from .base import Base


class WorkspaceType(enum.StrEnum):
    PERSONAL = 'personal'
    TEAM = 'team'


class WorkspaceStatus(enum.StrEnum):
    PROVISIONING = 'provisioning'
    ACTIVE = 'active'
    SUSPENDED = 'suspended'
    ARCHIVED = 'archived'
    DELETED = 'deleted'


class WorkspaceSource(enum.StrEnum):
    LOCAL = 'local'
    CLOUD_PROJECTION = 'cloud_projection'


class MembershipRole(enum.StrEnum):
    OWNER = 'owner'
    ADMIN = 'admin'
    DEVELOPER = 'developer'
    OPERATOR = 'operator'
    VIEWER = 'viewer'


class MembershipStatus(enum.StrEnum):
    ACTIVE = 'active'
    DISABLED = 'disabled'
    REMOVED = 'removed'


class InvitationStatus(enum.StrEnum):
    PENDING = 'pending'
    ACCEPTED = 'accepted'
    REVOKED = 'revoked'
    EXPIRED = 'expired'


class WorkspaceExecutionStatus(enum.StrEnum):
    PROVISIONING = 'provisioning'
    ACTIVE = 'active'
    MIGRATING = 'migrating'
    DRAINING = 'draining'
    INACTIVE = 'inactive'


class WorkspaceExecutionSource(enum.StrEnum):
    LOCAL = 'local'
    CLOUD = 'cloud'


def _new_uuid() -> str:
    return str(uuid_lib.uuid4())


class Workspace(Base):
    __tablename__ = 'workspaces'

    uuid = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True, default=_new_uuid)
    instance_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    slug = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    type = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        server_default=WorkspaceType.TEAM.value,
    )
    status = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        server_default=WorkspaceStatus.ACTIVE.value,
    )
    created_by_account_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('users.uuid', ondelete='SET NULL'),
        nullable=True,
    )
    source = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        server_default=WorkspaceSource.LOCAL.value,
    )
    projection_revision = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=False, server_default='0')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.UniqueConstraint('instance_uuid', 'slug', name='uq_workspaces_instance_slug'),
        sqlalchemy.Index('ix_workspaces_instance_status', 'instance_uuid', 'status'),
        sqlalchemy.Index(
            'uq_workspaces_local_instance',
            'instance_uuid',
            unique=True,
            sqlite_where=sqlalchemy.text("source = 'local'"),
            postgresql_where=sqlalchemy.text("source = 'local'"),
        ),
        sqlalchemy.CheckConstraint(
            "type IN ('personal', 'team')",
            name='ck_workspaces_type',
        ),
        sqlalchemy.CheckConstraint(
            "status IN ('provisioning', 'active', 'suspended', 'archived', 'deleted')",
            name='ck_workspaces_status',
        ),
        sqlalchemy.CheckConstraint(
            "source IN ('local', 'cloud_projection')",
            name='ck_workspaces_source',
        ),
    )


class WorkspaceMembership(Base):
    __tablename__ = 'workspace_memberships'

    uuid = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True, default=_new_uuid)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    account_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('users.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    role = sqlalchemy.Column(sqlalchemy.String(32), nullable=False)
    status = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        server_default=MembershipStatus.ACTIVE.value,
    )
    invited_by_account_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('users.uuid', ondelete='SET NULL'),
        nullable=True,
    )
    joined_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    projection_revision = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=False, server_default='0')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.UniqueConstraint('workspace_uuid', 'account_uuid', name='uq_workspace_membership_account'),
        sqlalchemy.Index('ix_workspace_memberships_account_status', 'account_uuid', 'status'),
        sqlalchemy.CheckConstraint(
            "role IN ('owner', 'admin', 'developer', 'operator', 'viewer')",
            name='ck_workspace_memberships_role',
        ),
        sqlalchemy.CheckConstraint(
            "status IN ('active', 'disabled', 'removed')",
            name='ck_workspace_memberships_status',
        ),
    )


class WorkspaceInvitation(Base):
    __tablename__ = 'workspace_invitations'

    uuid = sqlalchemy.Column(sqlalchemy.String(36), primary_key=True, default=_new_uuid)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    normalized_email = sqlalchemy.Column(sqlalchemy.String(320), nullable=False)
    role = sqlalchemy.Column(sqlalchemy.String(32), nullable=False)
    token_hash = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    status = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        server_default=InvitationStatus.PENDING.value,
    )
    expires_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False)
    accepted_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    revoked_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    created_by_account_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('users.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.Index('uq_workspace_invitations_token_hash', 'token_hash', unique=True),
        sqlalchemy.Index(
            'uq_workspace_invitations_pending_email',
            'workspace_uuid',
            'normalized_email',
            unique=True,
            sqlite_where=sqlalchemy.text("status = 'pending'"),
            postgresql_where=sqlalchemy.text("status = 'pending'"),
        ),
        sqlalchemy.CheckConstraint(
            "role IN ('admin', 'developer', 'operator', 'viewer')",
            name='ck_workspace_invitations_role',
        ),
        sqlalchemy.CheckConstraint(
            "status IN ('pending', 'accepted', 'revoked', 'expired')",
            name='ck_workspace_invitations_status',
        ),
    )


class WorkspaceExecutionState(Base):
    __tablename__ = 'workspace_execution_states'

    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        primary_key=True,
    )
    instance_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    active_generation = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=False, server_default='1')
    state = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        server_default=WorkspaceExecutionStatus.ACTIVE.value,
    )
    write_fenced = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, server_default=sqlalchemy.false())
    source = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        server_default=WorkspaceExecutionSource.LOCAL.value,
    )
    desired_state_revision = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=False, server_default='0')
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.Index('ix_workspace_execution_states_instance_state', 'instance_uuid', 'state'),
        sqlalchemy.CheckConstraint('active_generation > 0', name='ck_workspace_execution_generation'),
        sqlalchemy.CheckConstraint(
            "state IN ('provisioning', 'active', 'migrating', 'draining', 'inactive')",
            name='ck_workspace_execution_state',
        ),
        sqlalchemy.CheckConstraint(
            "source IN ('local', 'cloud')",
            name='ck_workspace_execution_source',
        ),
    )
