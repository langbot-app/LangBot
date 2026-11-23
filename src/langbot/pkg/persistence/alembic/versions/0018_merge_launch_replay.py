"""merge the published Space launch replay and main migration branches

Revision ID: 0018_merge_launch_replay
Revises: 0016_space_launch_replay, 0017_oss_workspace_identity
Create Date: 2026-08-01
"""

from __future__ import annotations

revision = '0018_merge_launch_replay'
down_revision = ('0016_space_launch_replay', '0017_oss_workspace_identity')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
