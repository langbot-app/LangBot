"""merge AgentRunner and model reasoning migration heads

Revision ID: 0022_merge_agent_reasoning_heads
Revises: 0020_merge_agent_cloud_heads, 0021_merge_reasoning_config
Create Date: 2026-08-14
"""

from __future__ import annotations

revision = '0022_merge_agent_reasoning_heads'
down_revision = ('0020_merge_agent_cloud_heads', '0021_merge_reasoning_config')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
