"""Instance enrollment records; the creator Workspace owns management only."""

import sqlalchemy as sa

from .base import Base


class HarnessRegistrationLink(Base):
    __tablename__ = 'harness_registration_links'

    id = sa.Column(sa.String(36), primary_key=True)
    token_hash = sa.Column(sa.String(64), nullable=False, unique=True)
    instance_uuid = sa.Column(sa.String(36), nullable=False)
    issuer_workspace_uuid = sa.Column(sa.String(36), nullable=False, index=True)
    created_by_account_uuid = sa.Column(sa.String(36), nullable=False)
    kid = sa.Column(sa.String(128), nullable=False)
    preferred_auth = sa.Column(sa.String(16))
    expires_at = sa.Column(sa.BigInteger, nullable=False)
    consumed_at = sa.Column(sa.BigInteger)
    revoked_at = sa.Column(sa.BigInteger)


class HarnessBinding(Base):
    __tablename__ = 'harness_bindings'

    id = sa.Column(sa.String(36), primary_key=True)
    instance_uuid = sa.Column(sa.String(36), nullable=False)
    issuer_workspace_uuid = sa.Column(sa.String(36), nullable=False, index=True)
    created_at = sa.Column(sa.BigInteger, nullable=False)
    revoked_at = sa.Column(sa.BigInteger)
