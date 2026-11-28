"""Device-bound Harness OAuth records."""

import sqlalchemy as sa

from .base import Base


class HarnessDevice(Base):
    __tablename__ = 'harness_devices'

    id = sa.Column(sa.String(64), primary_key=True)
    binding_id = sa.Column(sa.String(36), nullable=False, index=True)
    device_kid = sa.Column(sa.String(128), nullable=False)
    x25519_pub = sa.Column(sa.Text, nullable=False)
    ed25519_pub = sa.Column(sa.Text, nullable=False)
    platform = sa.Column(sa.String(32), nullable=False, default='unknown')
    account_uuid = sa.Column(sa.String(36), nullable=True, index=True)
    created_at = sa.Column(sa.BigInteger, nullable=False)
    revoked_at = sa.Column(sa.BigInteger, nullable=True)


class HarnessHandoff(Base):
    __tablename__ = 'harness_handoffs'

    ticket_hash = sa.Column(sa.String(64), primary_key=True)
    instance_uuid = sa.Column(sa.String(36), nullable=False)
    binding_id = sa.Column(sa.String(36), nullable=False)
    device_id = sa.Column(sa.String(64), nullable=False)
    account_uuid = sa.Column(sa.String(36), nullable=False, unique=True)
    workspace_uuid = sa.Column(sa.String(36), nullable=False)
    password_digest = sa.Column(sa.String(64), nullable=False)
    credential_uuid = sa.Column(sa.String(36), nullable=False)
    expires_at = sa.Column(sa.BigInteger, nullable=False, index=True)
    attempts = sa.Column(sa.Integer, nullable=False)
    state = sa.Column(sa.String(12), nullable=False)


class HarnessOAuthGrant(Base):
    __tablename__ = 'harness_oauth_grants'

    id = sa.Column(sa.String(36), primary_key=True)
    binding_id = sa.Column(sa.String(36), nullable=False, index=True)
    device_id = sa.Column(sa.String(64), nullable=False, index=True)
    account_uuid = sa.Column(sa.String(36), nullable=False, index=True)
    workspace_uuid = sa.Column(sa.String(36), nullable=False, index=True)
    scope = sa.Column(sa.Text, nullable=False)
    refresh_token_hash = sa.Column(sa.String(64), nullable=False, unique=True)
    previous_refresh_token_hash = sa.Column(sa.String(64), nullable=True, index=True)
    refresh_generation = sa.Column(sa.Integer, nullable=False, default=0)
    refresh_expires_at = sa.Column(sa.BigInteger, nullable=False)
    created_at = sa.Column(sa.BigInteger, nullable=False)
    revoked_at = sa.Column(sa.BigInteger, nullable=True)
