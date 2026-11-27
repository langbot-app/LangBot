"""Persistence records for Harness OAuth clients, grants and handoffs."""

import sqlalchemy as sa

from ..entity.persistence.base import Base


class OAuthClient(Base):
    __tablename__ = 'oauth_clients'

    id = sa.Column(sa.String(36), primary_key=True)
    binding_id = sa.Column(sa.String(36), nullable=False, index=True)
    device_id = sa.Column(sa.String(64), nullable=False, index=True)
    created_at = sa.Column(sa.BigInteger, nullable=False)
    revoked_at = sa.Column(sa.BigInteger)
    __table_args__ = (sa.UniqueConstraint('binding_id', 'device_id', name='uq_oauth_client_binding_device'),)


class OAuthGrant(Base):
    __tablename__ = 'oauth_grants'

    id = sa.Column(sa.String(36), primary_key=True)
    client_id = sa.Column(sa.String(36), nullable=False, index=True)
    binding_id = sa.Column(sa.String(36), nullable=False, index=True)
    device_id = sa.Column(sa.String(64), nullable=False, index=True)
    account_uuid = sa.Column(sa.String(36), nullable=False, index=True)
    workspace_uuid = sa.Column(sa.String(36), nullable=False, index=True)
    scope = sa.Column(sa.Text, nullable=False)
    refresh_token_hash = sa.Column(sa.String(64), nullable=False, unique=True)
    refresh_history = sa.Column(sa.Text, nullable=False, default='[]')
    refresh_expires_at = sa.Column(sa.BigInteger, nullable=False)
    created_at = sa.Column(sa.BigInteger, nullable=False)
    revoked_at = sa.Column(sa.BigInteger)


class OAuthPendingState(Base):
    __tablename__ = 'oauth_pending_states'

    id = sa.Column(sa.String(36), primary_key=True)
    state_hash = sa.Column(sa.String(64), nullable=False, unique=True)
    binding_id = sa.Column(sa.String(36), nullable=False)
    device_id = sa.Column(sa.String(64), nullable=False)
    workspace_uuid = sa.Column(sa.String(36), nullable=False)
    scope = sa.Column(sa.Text, nullable=False)
    expires_at = sa.Column(sa.BigInteger, nullable=False)
    consumed_at = sa.Column(sa.BigInteger)


class OAuthHandoffTicket(Base):
    __tablename__ = 'oauth_handoff_tickets'

    id = sa.Column(sa.String(36), primary_key=True)
    ticket_hash = sa.Column(sa.String(64), nullable=False, unique=True)
    pending_state_id = sa.Column(sa.String(36), nullable=False, index=True)
    account_uuid = sa.Column(sa.String(36), nullable=False)
    challenge_ciphertext = sa.Column(sa.Text, nullable=False)
    expires_at = sa.Column(sa.BigInteger, nullable=False)
    consumed_at = sa.Column(sa.BigInteger)
