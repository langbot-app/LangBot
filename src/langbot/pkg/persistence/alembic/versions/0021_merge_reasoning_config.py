"""merge reasoning config with the main migration branch

Revision ID: 0021_merge_reasoning_config
Revises: 0020_membership_source, 0018_llm_reasoning_config
Create Date: 2026-08-09
"""

from __future__ import annotations

revision = '0021_merge_reasoning_config'
down_revision = ('0020_membership_source', '0018_llm_reasoning_config')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
