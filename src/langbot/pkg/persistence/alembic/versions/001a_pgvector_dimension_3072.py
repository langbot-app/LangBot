"""enable 3072-dimensional pgvector embeddings

Revision ID: 001a_pgvector_dimension_3072
Revises: 0019_single_workspace_owner
Create Date: 2026-08-05
"""

from __future__ import annotations
import sqlalchemy as sa
from alembic import op

revision = '001a_pgvector_dimension_3072'
down_revision = '0019_single_workspace_owner'
branch_labels = None
depends_on = None
_TABLE = 'langbot_vectors'
_CHECK = 'ck_langbot_vectors_embedding_dimension_enabled'
_INDEX = 'ix_langbot_vectors_hnsw_cosine_3072'


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql' or _TABLE not in sa.inspect(conn).get_table_names():
        return
    op.drop_constraint(_CHECK, _TABLE, type_='check')
    op.create_check_constraint(_CHECK, _TABLE, 'embedding_dimension IN (384, 512, 768, 1024, 1536, 3072)')
    op.execute(
        sa.text(
            f'CREATE INDEX {_INDEX} ON {_TABLE} USING hnsw ((embedding::halfvec(3072)) halfvec_cosine_ops) WHERE embedding_dimension = 3072'
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql' or _TABLE not in sa.inspect(conn).get_table_names():
        return
    count = conn.scalar(sa.text(f'SELECT COUNT(*) FROM {_TABLE} WHERE embedding_dimension = 3072'))
    if count:
        raise RuntimeError('Cannot disable 3072-dimensional pgvector while matching embeddings exist')
    op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_constraint(_CHECK, _TABLE, type_='check')
    op.create_check_constraint(_CHECK, _TABLE, 'embedding_dimension IN (384, 512, 768, 1024, 1536)')
