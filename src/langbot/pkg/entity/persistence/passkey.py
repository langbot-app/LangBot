from __future__ import annotations

import uuid as uuid_lib

import sqlalchemy

from .base import Base


class PasskeyCredential(Base):
    __tablename__ = 'passkey_credentials'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        nullable=False,
        default=lambda: str(uuid_lib.uuid4()),
    )
    account_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('users.uuid', ondelete='CASCADE'),
        nullable=False,
    )
    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    credential_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    public_key = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    sign_count = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    aaguid = sqlalchemy.Column(sqlalchemy.String(64), nullable=True)
    transports = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    backed_up = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, default=False)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    last_used_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)

    __table_args__ = (
        sqlalchemy.Index('uq_passkey_credentials_uuid', 'uuid', unique=True),
        sqlalchemy.Index('uq_passkey_credentials_cred_id', 'credential_id', unique=True),
        sqlalchemy.Index('ix_passkey_credentials_account', 'account_uuid'),
    )
