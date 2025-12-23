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
    databases: dict[str, VectorDatabase] = {}
    default_db_name: str = 'default'

    def __init__(self, ap: app.Application):
        self.ap = ap
        self.databases = {}

    def _create_vdb_instance(self, vdb_type: str, config: dict) -> VectorDatabase:
        if vdb_type == 'chroma':
            return ChromaVectorDatabase(self.ap)
        elif vdb_type == 'qdrant':
            return QdrantVectorDatabase(self.ap)
        elif vdb_type == 'seekdb':
            # Extract fulltext configuration if present
            # We look for a 'fulltext' section in the database config or top-level vdb config
            # But here `config` is the specific instance config.
            fulltext_config = config.get('fulltext', {})
            return SeekDBVectorDatabase(self.ap, config_override=config, fulltext_config=fulltext_config)
        elif vdb_type == 'milvus':
            milvus_config = config.get('milvus', {})
            uri = milvus_config.get('uri', './data/milvus.db')
            token = milvus_config.get('token')
            return MilvusVectorDatabase(self.ap, uri=uri, token=token)
        elif vdb_type == 'pgvector':
            pgvector_config = config.get('pgvector', {})
            connection_string = pgvector_config.get('connection_string')
            if connection_string:
                return PgVectorDatabase(self.ap, connection_string=connection_string)
            else:
                host = pgvector_config.get('host', 'localhost')
                port = pgvector_config.get('port', 5432)
                database = pgvector_config.get('database', 'langbot')
                user = pgvector_config.get('user', 'postgres')
                password = pgvector_config.get('password', 'postgres')
                return PgVectorDatabase(
                    self.ap,
                    host=host,
                    port=port,
                    database=database,
                    user=user,
                    password=password
                )
        else:
            self.ap.logger.warning(f'Unknown vdb type: {vdb_type}, defaulting to Chroma')
            return ChromaVectorDatabase(self.ap)

    async def initialize(self):
        vdb_config = self.ap.instance_config.data.get('vdb')
        
        # Backward compatibility: Single DB config style
        if vdb_config and 'use' in vdb_config:
            self.ap.logger.info("Initializing single default vector database...")
            vdb_type = vdb_config.get('use')
            vdb_instance = self._create_vdb_instance(vdb_type, vdb_config)
            self.databases['default'] = vdb_instance
            self.vector_db = vdb_instance # Keep for backward compat
        
        # New style: Multiple DBs config
        # vdb:
        #   databases:
        #     default:
        #       type: seekdb
        #     es_fulltext:
        #       type: elasticsearch
        elif vdb_config and 'databases' in vdb_config:
            self.ap.logger.info("Initializing multiple vector databases...")
            for name, conf in vdb_config['databases'].items():
                vdb_type = conf.get('type')
                try:
                    instance = self._create_vdb_instance(vdb_type, conf)
                    self.databases[name] = instance
                    self.ap.logger.info(f"Initialized VDB '{name}' ({vdb_type})")
                except Exception as e:
                    self.ap.logger.error(f"Failed to initialize VDB '{name}': {e}")
            
            # Set convenience accessor for default
            self.vector_db = self.databases.get('default')
        
        # Fallback
        if not self.databases:
             self.ap.logger.warning('No vector database backend configured, defaulting to Chroma as default.')
             default_chroma = ChromaVectorDatabase(self.ap)
             self.databases['default'] = default_chroma
             self.vector_db = default_chroma

    def get_db(self, name: str = 'default') -> VectorDatabase | None:
        """Get a specific vector database instance by name"""
        return self.databases.get(name)
