from __future__ import annotations

from ..core import app
from .vdb import VectorDatabase
from .vdbs.chroma import ChromaVectorDatabase
from .vdbs.qdrant import QdrantVectorDatabase
from .vdbs.seekdb import SeekDBVectorDatabase
from .vdbs.milvus import MilvusVectorDatabase
from .vdbs.pgvector_db import PgVectorDatabase


class VectorDBManager:
    ap: app.Application
    vector_db: VectorDatabase = None

    def __init__(self, ap: app.Application):
        self.ap = ap

    async def initialize(self):
        kb_config = self.ap.instance_config.data.get('vdb')
        if kb_config:
            vdb_type = kb_config.get('use')

            if vdb_type == 'chroma':
                self.vector_db = ChromaVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Chroma vector database backend.')

            elif vdb_type == 'qdrant':
                self.vector_db = QdrantVectorDatabase(self.ap)
                self.ap.logger.info('Initialized Qdrant vector database backend.')
            elif vdb_type == 'seekdb':
                self.vector_db = SeekDBVectorDatabase(self.ap)
                self.ap.logger.info('Initialized SeekDB vector database backend.')

            elif vdb_type == 'milvus':
                # Get Milvus configuration
                milvus_config = kb_config.get('milvus', {})
                uri = milvus_config.get('uri', './data/milvus.db')
                token = milvus_config.get('token')
                db_name = milvus_config.get('db_name', 'default')
                self.vector_db = MilvusVectorDatabase(self.ap, uri=uri, token=token, db_name=db_name)
                self.ap.logger.info('Initialized Milvus vector database backend.')

            elif vdb_type == 'pgvector':
                # Get pgvector configuration
                pgvector_config = kb_config.get('pgvector', {})
                connection_string = pgvector_config.get('connection_string')
                if connection_string:
                    self.vector_db = PgVectorDatabase(self.ap, connection_string=connection_string)
                else:
                    # Use individual parameters
                    host = pgvector_config.get('host', 'localhost')
                    port = pgvector_config.get('port', 5432)
                    database = pgvector_config.get('database', 'langbot')
                    user = pgvector_config.get('user', 'postgres')
                    password = pgvector_config.get('password', 'postgres')
                    self.vector_db = PgVectorDatabase(
                        self.ap, host=host, port=port, database=database, user=user, password=password
                    )
                self.ap.logger.info('Initialized pgvector database backend.')

            else:
                self.vector_db = ChromaVectorDatabase(self.ap)
                self.ap.logger.warning('No valid vector database backend configured, defaulting to Chroma.')
        else:
            self.vector_db = ChromaVectorDatabase(self.ap)
            self.ap.logger.warning('No vector database backend configured, defaulting to Chroma.')
