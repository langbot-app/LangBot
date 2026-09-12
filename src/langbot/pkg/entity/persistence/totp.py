"""Persistence entity for per-Account TOTP (RFC 6238) second factors."""

from __future__ import annotations

import uuid as uuid_lib

import sqlalchemy

from .base import Base


class TotpCredential(Base):
    """Per-Account TOTP (RFC 6238) second factor and its recovery codes.

    A single row is kept per Account. The shared secret is stored encrypted
    (``secret_encrypted``, Fernet keyed off the instance JWT secret via HKDF)
    rather than in plaintext, and remains unenforced until the owner confirms
    possession by submitting a valid code (``enabled``). Recovery codes are
    stored only as salted PBKDF2-HMAC-SHA256 digests, so a database leak does
    not hand out account recovery. No plaintext secret or recovery code is ever
    persisted; both leave the server exactly once, in the enrolment response.
    """

    __tablename__ = 'totp_credentials'

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
    # Fernet-encrypted base32 secret; never exposed to the client after enrol.
    secret_encrypted = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    # Issuer label shown inside the authenticator app (e.g. the account email).
    account_name = sqlalchemy.Column(sqlalchemy.String(320), nullable=False)
    enabled = sqlalchemy.Column(sqlalchemy.Boolean, nullable=False, server_default='0')
    # JSON-encoded list of salted PBKDF2 hashes for the one-time recovery codes.
    recovery_codes = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    last_used_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    created_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
    )
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        onupdate=sqlalchemy.func.now(),
    )

    __table_args__ = (
        sqlalchemy.Index('uq_totp_credentials_uuid', 'uuid', unique=True),
        sqlalchemy.Index('uq_totp_credentials_account', 'account_uuid', unique=True),
    )
