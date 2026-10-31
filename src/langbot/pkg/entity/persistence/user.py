import enum
import uuid as uuid_lib

import sqlalchemy

from .base import Base


class AccountStatus(enum.StrEnum):
    ACTIVE = 'active'
    DISABLED = 'disabled'
    DELETED = 'deleted'


class AccountSource(enum.StrEnum):
    LOCAL = 'local'
    CLOUD_PROJECTION = 'cloud_projection'


class User(Base):
    __tablename__ = 'users'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True)
    uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        nullable=False,
        default=lambda: str(uuid_lib.uuid4()),
    )
    user = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    normalized_email = sqlalchemy.Column(sqlalchemy.String(320), nullable=False)
    password = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)

    status = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        server_default=AccountStatus.ACTIVE.value,
    )
    source = sqlalchemy.Column(
        sqlalchemy.String(32),
        nullable=False,
        server_default=AccountSource.LOCAL.value,
    )
    projection_revision = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=False, server_default='0')

    # Account type: 'local' (default) or 'space'
    account_type = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, server_default='local')

    # Space account fields (nullable, only used when account_type='space')
    space_account_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    space_access_token = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    space_refresh_token = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    space_access_token_expires_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    space_api_key = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.Index('uq_users_uuid', 'uuid', unique=True),
        sqlalchemy.Index('uq_users_normalized_email', 'normalized_email', unique=True),
        sqlalchemy.CheckConstraint(
            'normalized_email = trim(normalized_email) '
            'AND length(normalized_email) > 0 '
            'AND length(normalized_email) <= 320',
            name='ck_users_normalized_email',
        ),
        sqlalchemy.CheckConstraint(
            "status IN ('active', 'disabled', 'deleted')",
            name='ck_users_status',
        ),
        sqlalchemy.CheckConstraint(
            "source IN ('local', 'cloud_projection')",
            name='ck_users_source',
        ),
    )
