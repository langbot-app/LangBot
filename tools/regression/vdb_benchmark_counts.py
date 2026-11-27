"""Read-only cardinality evidence for the benchmark's owned embedded backend."""

from contextlib import closing
from pathlib import Path
import sqlite3


def count_chroma(path):
    """Count committed vector records, not index HNSW graph nodes.

    Use only on a fresh, dedicated benchmark store. Confirm a single nonempty
    collection so a leftover collection cannot pad the benchmark population.
    Chroma's metadata segments have one row per logical embedding ID.
    """
    path = Path(path).resolve()
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as db:
        db.execute('PRAGMA query_only=ON')
        rows = db.execute(
            """
            SELECT c.id, c.dimension, COUNT(DISTINCT e.embedding_id)
            FROM collections AS c
            JOIN segments AS s ON s.collection = c.id AND s.scope = 'METADATA'
            JOIN embeddings AS e ON e.segment_id = s.id
            GROUP BY c.id, c.dimension
            """
        ).fetchall()
    if len(rows) > 1:
        raise ValueError('Expected only one nonempty Chroma collection in the isolated benchmark')
    _, dimensions, count = rows[0] if rows else (None, None, 0)
    return {'source': 'chroma_sqlite_committed_embedding_ids', 'vectors': count, 'dimensions': dimensions}
