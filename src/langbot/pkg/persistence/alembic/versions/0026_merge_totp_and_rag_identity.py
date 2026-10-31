"""merge the TOTP credential branch with the RAG document identity branch

Revision ID: 0026_merge_totp_and_rag_identity
Revises: 0025_totp_credentials, 0025_rag_document_identity
Create Date: 2026-09-22
"""

from __future__ import annotations

revision = '0026_merge_totp_and_rag_identity'
down_revision = ('0025_totp_credentials', '0025_rag_document_identity')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
