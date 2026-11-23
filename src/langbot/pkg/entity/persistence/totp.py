from __future__ import annotations

import uuid as uuid_lib

import sqlalchemy

from .base import Base


class TotpCredential(Base):
    """Per-Account TOTP enrolment.

    ``secret_ciphertext`` stores the Fernet token produced by encrypting the
    base32 TOTP shared secret with a key derived from the instance JWT secret
    (HKDF-SHA256). The plaintext secret is never written to disk and never
    returned by read endpoints after enrolment completes.
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
    secret_ciphertext = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    # Key derivation epoch: allows rotating the wrapping key without losing the secret.
    key_version = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, server_default='1')
    algorithm = sqlalchemy.Column(sqlalchemy.String(16), nullable=False, server_default='SHA1')
    digits = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, server_default='6')
    period = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, server_default='30')
    confirmed_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    last_used_counter = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=True)
    disabled_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())
    last_used_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)

    __table_args__ = (
        sqlalchemy.Index('uq_totp_credentials_uuid', 'uuid', unique=True),
        sqlalchemy.Index('ix_totp_credentials_account', 'account_uuid'),
    )


class TotpRecoveryCode(Base):
    """Single-use TOTP recovery code stored only as a salted PBKDF2 digest."""

    __tablename__ = 'totp_recovery_codes'

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
    code_id = sqlalchemy.Column(sqlalchemy.String(16), nullable=False)
    salt = sqlalchemy.Column(sqlalchemy.String(64), nullable=False)
    digest = sqlalchemy.Column(sqlalchemy.String(128), nullable=False)
    algorithm = sqlalchemy.Column(sqlalchemy.String(32), nullable=False, server_default='pbkdf2_hmac_sha256')
    iterations = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    used_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, server_default=sqlalchemy.func.now())

    __table_args__ = (
        sqlalchemy.Index('uq_totp_recovery_codes_uuid', 'uuid', unique=True),
        sqlalchemy.Index('uq_totp_recovery_codes_code_id', 'code_id', unique=True),
        sqlalchemy.Index('ix_totp_recovery_codes_account', 'account_uuid'),
    )
