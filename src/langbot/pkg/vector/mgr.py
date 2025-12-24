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
            return SeekDBVectorDatabase(self.ap, config_override=config)
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

        # Track created instances to avoid duplicates (same type = same instance)
        created_instances = {}  # type -> (name, instance)

        # Backward compatibility: Single DB config style
        if vdb_config and 'use' in vdb_config:
            self.ap.logger.info("Initializing single default vector database...")
            vdb_type = vdb_config.get('use')
            vdb_instance = self._create_vdb_instance(vdb_type, vdb_config)
            self.databases['default'] = vdb_instance
            self.vector_db = vdb_instance # Keep for backward compat
            created_instances[vdb_type] = ('default', vdb_instance)

        # New style: Multiple DBs config (can coexist with 'use')
        # Support both formats:
        # 1. databases: {name: {type: xxx, ...}}  # object format
        # 2. databases: [type1, type2, ...]       # array format
        if vdb_config and 'databases' in vdb_config:
            self.ap.logger.info("Initializing multiple vector databases...")
            databases_config = vdb_config['databases']

            # Handle array format: ['chroma', 'seekdb']
            if isinstance(databases_config, list):
                for vdb_type in databases_config:
                    # Use type name as database name
                    name = vdb_type

                    # Check if we already have an instance of this type
                    if vdb_type in created_instances:
                        existing_name, existing_instance = created_instances[vdb_type]
                        self.databases[name] = existing_instance
                        self.ap.logger.info(f"Reused existing VDB instance '{existing_name}' ({vdb_type}) for '{name}'")
                    else:
                        try:
                            # Get config for this type (e.g., vdb.chroma, vdb.seekdb)
                            type_config = vdb_config.get(vdb_type, {})
                            instance = self._create_vdb_instance(vdb_type, type_config)
                            self.databases[name] = instance
                            created_instances[vdb_type] = (name, instance)
                            self.ap.logger.info(f"Initialized VDB '{name}' ({vdb_type})")
                        except Exception as e:
                            self.ap.logger.error(f"Failed to initialize VDB '{name}': {e}")
            else:
                # Handle object format: {name: {type: xxx, ...}}
                for name, conf in databases_config.items():
                    vdb_type = conf.get('type')

                    # Check if we already have an instance of this type
                    if vdb_type in created_instances:
                        existing_name, existing_instance = created_instances[vdb_type]
                        self.databases[name] = existing_instance
                        self.ap.logger.info(f"Reused existing VDB instance '{existing_name}' ({vdb_type}) for '{name}'")
                    else:
                        try:
                            instance = self._create_vdb_instance(vdb_type, conf)
                            self.databases[name] = instance
                            created_instances[vdb_type] = (name, instance)
                            self.ap.logger.info(f"Initialized VDB '{name}' ({vdb_type})")
                        except Exception as e:
                            self.ap.logger.error(f"Failed to initialize VDB '{name}': {e}")

        # Set convenience accessor for default
        if not self.vector_db:
            self.vector_db = self.databases.get('default')
            if not self.vector_db and self.databases:
                # If no 'default' VDB configured, use the first available one
                first_db_name = next(iter(self.databases.keys()))
                self.vector_db = self.databases[first_db_name]
                self.ap.logger.info(f"No 'default' VDB configured, using '{first_db_name}' as default")
        
        # Fallback
        if not self.databases:
             self.ap.logger.warning('No vector database backend configured, defaulting to Chroma as default.')
             default_chroma = ChromaVectorDatabase(self.ap)
             self.databases['default'] = default_chroma
             self.vector_db = default_chroma

    def get_db(self, name: str = 'default') -> VectorDatabase | None:
        """Get a specific vector database instance by name"""
        return self.databases.get(name)
