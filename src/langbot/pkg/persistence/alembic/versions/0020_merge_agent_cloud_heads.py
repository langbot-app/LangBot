"""merge AgentRunner and Cloud Workspace migration heads

Revision ID: 0020_merge_agent_cloud_heads
Revises: 0018_merge_workspace_heads, 0019_single_workspace_owner
Create Date: 2026-08-04
"""

from __future__ import annotations

revision = '0020_merge_agent_cloud_heads'
down_revision = ('0018_merge_workspace_heads', '0019_single_workspace_owner')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
