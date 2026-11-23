"""Join the TOTP credential branch with the workspace assistant branch.

Revision ID: 0031_merge_totp_assistant
Revises: 0030_merge_assistant, 0030_merge_totp_into_release

Both ``0030`` merge revisions were authored independently: the release/master
line converged on ``0030_merge_assistant`` while the TOTP two-factor feature
branch converged on ``0030_merge_totp_into_release``. Integrating them leaves
Alembic with two heads, so this revision rejoins the graph and lets a single
``upgrade head`` apply both the TOTP credential tables and the workspace
assistant conversation tables.

Schemas and data are untouched; only the revision graph is joined.
"""

from __future__ import annotations

revision = '0031_merge_totp_assistant'
down_revision = ('0030_merge_assistant', '0030_merge_totp_into_release')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    # Unmerge the graph only; retain both branches' schemas and user data.
    pass
