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
        kb_config = self.ap.instance_config.data.get('kb')
        if kb_config:
            if kb_config.get('default_vector_db') == 'chroma':
                self.vector_db = ChromaVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Chroma vector database backend.')
            elif kb_config.get('default_vector_db') == 'qdrant':
                self.vector_db = QdrantVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Qdrant vector database backend.')
            else:
                self.vector_db = ChromaVectorDatabase(self.ap)
                self.ap.logger.warning('No valid vector database backend configured, defaulting to Chroma.')
        else:
            self.vector_db = ChromaVectorDatabase(self.ap)
            self.ap.logger.warning('No vector database backend configured, defaulting to Chroma.')
