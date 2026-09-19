"""Join pipeline migration and knowledge base draft branches.

Revision ID: 0028_merge_knowledge_drafts
Revises: 0027_pipeline_migration, 0026_knowledge_base_drafts
"""

revision = '0028_merge_knowledge_drafts'
down_revision = ('0027_pipeline_migration', '0026_knowledge_base_drafts')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    # Only unmerge the revision graph; neither branch's schema is removed.
    pass
