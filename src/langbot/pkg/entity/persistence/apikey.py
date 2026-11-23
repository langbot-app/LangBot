import enum
import uuid as uuid_lib

import sqlalchemy

from .base import Base


class ApiKeyStatus(enum.StrEnum):
    ACTIVE = 'active'
    REVOKED = 'revoked'


def _new_uuid() -> str:
    return str(uuid_lib.uuid4())


class ApiKey(Base):
    """API Key for external service authentication"""

    __tablename__ = 'api_keys'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    uuid = sqlalchemy.Column(sqlalchemy.String(36), nullable=False, default=_new_uuid)
    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    created_by_account_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('users.uuid', ondelete='SET NULL'),
        nullable=True,
    )
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    key_hash = sqlalchemy.Column(sqlalchemy.String(64), nullable=False)
    scopes = sqlalchemy.Column(sqlalchemy.JSON, nullable=False, default=list, server_default='[]')
    status = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        server_default=ApiKeyStatus.ACTIVE.value,
    )
    expires_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    last_used_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    description = sqlalchemy.Column(sqlalchemy.String(512), nullable=True, default='')
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.Index('uq_api_keys_uuid', 'uuid', unique=True),
        # Authentication begins with the presented secret, before a Workspace
        # can be trusted, so hashes remain globally unique.
        sqlalchemy.Index('uq_api_keys_key_hash', 'key_hash', unique=True),
        sqlalchemy.Index('ix_api_keys_workspace_name', 'workspace_uuid', 'name'),
        sqlalchemy.Index('ix_api_keys_workspace_status', 'workspace_uuid', 'status'),
        sqlalchemy.CheckConstraint(
            "status IN ('active', 'revoked')",
            name='ck_api_keys_status',
        ),
    )
