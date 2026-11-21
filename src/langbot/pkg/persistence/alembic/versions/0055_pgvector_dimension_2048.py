"""enable 2048-dimensional pgvector embeddings

Revision ID: 0055_pgvector_dimension_2048
Revises: 0054_daily_message_usage
Create Date: 2026-11-21

2048 is the default output of e.g. jina-embeddings-v4 (LangBot Models) and
doubao embeddings. Like 3072 it exceeds pgvector's 2000-dimension HNSW limit
for ``vector``, so the partial ANN index is built over ``halfvec``.
"""

from __future__ import annotations

import sqlalchemy as sa
from alembic import op

revision = '0055_pgvector_dimension_2048'
down_revision = '0054_daily_message_usage'
branch_labels = None
depends_on = None

_TABLE = 'langbot_vectors'
_CHECK = 'ck_langbot_vectors_embedding_dimension_enabled'
_INDEX = 'ix_langbot_vectors_hnsw_cosine_2048'


def upgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql' or _TABLE not in sa.inspect(conn).get_table_names():
        return
    op.drop_constraint(_CHECK, _TABLE, type_='check')
    op.create_check_constraint(_CHECK, _TABLE, 'embedding_dimension IN (384, 512, 768, 1024, 1536, 2048, 3072)')
    op.execute(
        sa.text(
            f'CREATE INDEX IF NOT EXISTS {_INDEX} ON {_TABLE} USING hnsw '
            f'((embedding::halfvec(2048)) halfvec_cosine_ops) WHERE embedding_dimension = 2048'
        )
    )


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name != 'postgresql' or _TABLE not in sa.inspect(conn).get_table_names():
        return
    count = conn.scalar(sa.text(f'SELECT COUNT(*) FROM {_TABLE} WHERE embedding_dimension = 2048'))
    if count:
        raise RuntimeError('Cannot disable 2048-dimensional pgvector while matching embeddings exist')
    op.drop_index(_INDEX, table_name=_TABLE)
    op.drop_constraint(_CHECK, _TABLE, type_='check')
    op.create_check_constraint(_CHECK, _TABLE, 'embedding_dimension IN (384, 512, 768, 1024, 1536, 3072)')
