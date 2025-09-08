from __future__ import annotations

import os
from ..core import app
from .vdb import VectorDatabase
from .vdbs.chroma import ChromaVectorDatabase
from .vdbs.qdrant import QdrantVectorDatabase


class VectorDBManager:
    ap: app.Application
    vector_db: VectorDatabase = None

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        if self.vector_db is None:
            vdb_backend = os.getenv('VDB', 'chroma').lower()
            if vdb_backend == 'qdrant':
                self.vector_db = QdrantVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Qdrant vector database backend.')
            else:
                self.vector_db = ChromaVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Chroma vector database backend.')
