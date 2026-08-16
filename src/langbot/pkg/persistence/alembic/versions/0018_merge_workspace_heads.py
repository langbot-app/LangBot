"""merge AgentRunner and OSS Workspace migration heads

Revision ID: 0018_merge_workspace_heads
Revises: 0017_local_owner_repair, 0017_oss_workspace_identity
Create Date: 2026-08-01
"""

revision = '0018_merge_workspace_heads'
down_revision = ('0017_local_owner_repair', '0017_oss_workspace_identity')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
