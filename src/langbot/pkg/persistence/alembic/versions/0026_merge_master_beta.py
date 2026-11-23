"""Join the published master credentials and 4.11 bot processor branches.

Revision ID: 0026_merge_master_beta
Revises: 0024_passkey_credentials, 0025_bot_plugin_processors

Both parent chains are already published. Keep their identities and schema/data
operations intact; Alembic applies the missing branch before this no-op merge.
"""

revision = '0026_merge_master_beta'
down_revision = ('0024_passkey_credentials', '0025_bot_plugin_processors')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    # Only unmerge the revision graph; neither branch's schema/data is removed.
    pass
