"""Persist Harness OAuth clients, grants and TOTP browser handoffs."""

import sqlalchemy as sa
from alembic import op

revision = '0063_oauth_grants'
down_revision = '0062_harness_refresh_reuse'
branch_labels = None
depends_on = None


def upgrade():
    inspector = sa.inspect(op.get_bind())
    if not inspector.has_table('oauth_clients'):
        op.create_table(
            'oauth_clients',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('binding_id', sa.String(36), nullable=False),
            sa.Column('device_id', sa.String(64), nullable=False),
            sa.Column('created_at', sa.BigInteger, nullable=False),
            sa.Column('revoked_at', sa.BigInteger),
            sa.UniqueConstraint('binding_id', 'device_id', name='uq_oauth_client_binding_device'),
        )
        op.create_index('ix_oauth_clients_binding_id', 'oauth_clients', ['binding_id'])
        op.create_index('ix_oauth_clients_device_id', 'oauth_clients', ['device_id'])
    if not inspector.has_table('oauth_grants'):
        op.create_table(
            'oauth_grants',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('client_id', sa.String(36), nullable=False),
            sa.Column('binding_id', sa.String(36), nullable=False),
            sa.Column('device_id', sa.String(64), nullable=False),
            sa.Column('account_uuid', sa.String(36), nullable=False),
            sa.Column('workspace_uuid', sa.String(36), nullable=False),
            sa.Column('scope', sa.Text(), nullable=False),
            sa.Column('refresh_token_hash', sa.String(64), nullable=False, unique=True),
            sa.Column('refresh_history', sa.Text(), nullable=False, server_default='[]'),
            sa.Column('refresh_expires_at', sa.BigInteger, nullable=False),
            sa.Column('created_at', sa.BigInteger, nullable=False),
            sa.Column('revoked_at', sa.BigInteger),
        )
        for column in ('client_id', 'binding_id', 'device_id', 'account_uuid', 'workspace_uuid'):
            op.create_index(f'ix_oauth_grants_{column}', 'oauth_grants', [column])
    if not inspector.has_table('oauth_pending_states'):
        op.create_table(
            'oauth_pending_states',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('state_hash', sa.String(64), nullable=False, unique=True),
            sa.Column('binding_id', sa.String(36), nullable=False),
            sa.Column('device_id', sa.String(64), nullable=False),
            sa.Column('workspace_uuid', sa.String(36), nullable=False),
            sa.Column('scope', sa.Text(), nullable=False),
            sa.Column('expires_at', sa.BigInteger, nullable=False),
            sa.Column('consumed_at', sa.BigInteger),
        )
    if not inspector.has_table('oauth_handoff_tickets'):
        op.create_table(
            'oauth_handoff_tickets',
            sa.Column('id', sa.String(36), primary_key=True),
            sa.Column('ticket_hash', sa.String(64), nullable=False, unique=True),
            sa.Column('pending_state_id', sa.String(36), nullable=False),
            sa.Column('account_uuid', sa.String(36), nullable=False),
            sa.Column('challenge_ciphertext', sa.Text(), nullable=False),
            sa.Column('expires_at', sa.BigInteger, nullable=False),
            sa.Column('consumed_at', sa.BigInteger),
        )
        op.create_index('ix_oauth_handoff_tickets_pending_state_id', 'oauth_handoff_tickets', ['pending_state_id'])


def downgrade():
    inspector = sa.inspect(op.get_bind())
    if inspector.has_table('oauth_handoff_tickets'):
        op.drop_table('oauth_handoff_tickets')
    if inspector.has_table('oauth_pending_states'):
        op.drop_table('oauth_pending_states')
    if inspector.has_table('oauth_grants'):
        op.drop_table('oauth_grants')
    if inspector.has_table('oauth_clients'):
        op.drop_table('oauth_clients')
