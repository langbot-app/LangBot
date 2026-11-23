"""Join document identity with the 4.11 manual migration and draft branches."""

revision = '0029_merge_rag_identity'
down_revision = ('0028_merge_knowledge_drafts', '0025_rag_document_identity')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    # Unmerge the graph only; retain both branches' schemas and user data.
    pass
