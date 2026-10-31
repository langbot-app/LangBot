"""Join the TOTP credential branch with the release head.

Revision ID: 0030_merge_totp_into_release
Revises: 0026_merge_totp_and_rag_identity, 0029_merge_rag_identity
Create Date: 2026-09-23

The TOTP branch merged itself with the RAG document identity branch at
``0026_merge_totp_and_rag_identity``. Meanwhile the release branch reached its
own head at ``0029_merge_rag_identity``, which joined the same identity work
with the 4.11 manual migration and knowledge base draft branches.

Both heads therefore reach ``0025_rag_document_identity`` but neither includes
the other, leaving Alembic with two heads. This revision joins them so a single
``upgrade head`` applies the TOTP credential tables together with everything on
the release line.

Schemas and data are untouched; only the revision graph is joined.
"""

from __future__ import annotations

revision = '0030_merge_totp_into_release'
down_revision = ('0026_merge_totp_and_rag_identity', '0029_merge_rag_identity')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    # Unmerge the graph only; retain both branches' schemas and user data.
    pass
