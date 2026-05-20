"""Tests for VectorDBManager provider selection logic.

Tests the initialization logic that selects the appropriate VDB backend
based on configuration, without actually creating real VDB instances.
"""

from __future__ import annotations

from unittest.mock import MagicMock

from tests.utils.import_isolation import isolated_sys_modules


class TestVectorDBManagerInitialization:
    """Tests for VectorDBManager.initialize provider selection."""

    def _create_mock_app(self, vdb_config: dict | None):
        """Create mock app with vdb configuration."""
        mock_app = MagicMock()
        mock_app.instance_config = MagicMock()
        mock_app.instance_config.data = MagicMock()
        mock_app.instance_config.data.get = MagicMock(return_value=vdb_config)
        mock_app.logger = MagicMock()
        mock_app.logger.info = MagicMock()
        mock_app.logger.warning = MagicMock()
        return mock_app

    def _make_vector_import_mocks(self):
        """Create mocks for VDB backends to prevent real imports."""
        mocks = {}

        # Mock core.app to break circular import
        mocks['langbot.pkg.core.app'] = MagicMock()

        # Mock all VDB backend implementations
        for backend in ['chroma', 'qdrant', 'seekdb', 'milvus', 'pgvector_db']:
            mocks[f'langbot.pkg.vector.vdbs.{backend}'] = MagicMock()

        return mocks

    def test_initialize_no_config_defaults_to_chroma(self):
        """No vdb config defaults to Chroma."""
        mock_app = self._create_mock_app(None)

        mocks = self._make_vector_import_mocks()
        # Create mock Chroma class
        mock_chroma_class = MagicMock()
        mocks['langbot.pkg.vector.vdbs.chroma'].ChromaVectorDatabase = mock_chroma_class

        with isolated_sys_modules(mocks):
            # Import after mocking
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)

            # Run initialize synchronously for test
            import asyncio
            asyncio.get_event_loop().run_until_complete(mgr.initialize())

            # Chroma should be instantiated
            mock_chroma_class.assert_called_once_with(mock_app)
            mock_app.logger.warning.assert_called()

    def test_initialize_chroma_backend(self):
        """Explicit chroma config uses Chroma backend."""
        vdb_config = {'use': 'chroma'}
        mock_app = self._create_mock_app(vdb_config)

        mocks = self._make_vector_import_mocks()
        mock_chroma_class = MagicMock()
        mocks['langbot.pkg.vector.vdbs.chroma'].ChromaVectorDatabase = mock_chroma_class

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)

            import asyncio
            asyncio.get_event_loop().run_until_complete(mgr.initialize())

            mock_chroma_class.assert_called_once_with(mock_app)
            mock_app.logger.info.assert_called()

    def test_initialize_qdrant_backend(self):
        """Qdrant config uses Qdrant backend."""
        vdb_config = {'use': 'qdrant'}
        mock_app = self._create_mock_app(vdb_config)

        mocks = self._make_vector_import_mocks()
        mock_qdrant_class = MagicMock()
        mocks['langbot.pkg.vector.vdbs.qdrant'].QdrantVectorDatabase = mock_qdrant_class

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)

            import asyncio
            asyncio.get_event_loop().run_until_complete(mgr.initialize())

            mock_qdrant_class.assert_called_once_with(mock_app)

    def test_initialize_seekdb_backend(self):
        """SeekDB config uses SeekDB backend."""
        vdb_config = {'use': 'seekdb'}
        mock_app = self._create_mock_app(vdb_config)

        mocks = self._make_vector_import_mocks()
        mock_seekdb_class = MagicMock()
        mocks['langbot.pkg.vector.vdbs.seekdb'].SeekDBVectorDatabase = mock_seekdb_class

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)

            import asyncio
            asyncio.get_event_loop().run_until_complete(mgr.initialize())

            mock_seekdb_class.assert_called_once_with(mock_app)

    def test_initialize_milvus_backend_with_uri(self):
        """Milvus config with custom URI."""
        vdb_config = {
            'use': 'milvus',
            'milvus': {
                'uri': 'http://localhost:19530',
                'token': 'root:Milvus',
                'db_name': 'langbot_db'
            }
        }
        mock_app = self._create_mock_app(vdb_config)

        mocks = self._make_vector_import_mocks()
        mock_milvus_class = MagicMock()
        mocks['langbot.pkg.vector.vdbs.milvus'].MilvusVectorDatabase = mock_milvus_class

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)

            import asyncio
            asyncio.get_event_loop().run_until_complete(mgr.initialize())

            mock_milvus_class.assert_called_once_with(
                mock_app,
                uri='http://localhost:19530',
                token='root:Milvus',
                db_name='langbot_db'
            )

    def test_initialize_milvus_backend_defaults(self):
        """Milvus defaults when config not fully specified."""
        vdb_config = {'use': 'milvus'}
        mock_app = self._create_mock_app(vdb_config)

        mocks = self._make_vector_import_mocks()
        mock_milvus_class = MagicMock()
        mocks['langbot.pkg.vector.vdbs.milvus'].MilvusVectorDatabase = mock_milvus_class

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)

            import asyncio
            asyncio.get_event_loop().run_until_complete(mgr.initialize())

            # Should use default values
            mock_milvus_class.assert_called_once_with(
                mock_app,
                uri='./data/milvus.db',
                token=None,
                db_name='default'
            )

    def test_initialize_pgvector_with_connection_string(self):
        """pgvector with connection string."""
        vdb_config = {
            'use': 'pgvector',
            'pgvector': {
                'connection_string': 'postgresql://user:pass@host:5432/langbot'
            }
        }
        mock_app = self._create_mock_app(vdb_config)

        mocks = self._make_vector_import_mocks()
        mock_pgvector_class = MagicMock()
        mocks['langbot.pkg.vector.vdbs.pgvector_db'].PgVectorDatabase = mock_pgvector_class

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)

            import asyncio
            asyncio.get_event_loop().run_until_complete(mgr.initialize())

            mock_pgvector_class.assert_called_once_with(
                mock_app,
                connection_string='postgresql://user:pass@host:5432/langbot'
            )

    def test_initialize_pgvector_with_individual_params(self):
        """pgvector with individual connection parameters."""
        vdb_config = {
            'use': 'pgvector',
            'pgvector': {
                'host': 'db.example.com',
                'port': 5433,
                'database': 'vectordb',
                'user': 'admin',
                'password': 'secret'
            }
        }
        mock_app = self._create_mock_app(vdb_config)

        mocks = self._make_vector_import_mocks()
        mock_pgvector_class = MagicMock()
        mocks['langbot.pkg.vector.vdbs.pgvector_db'].PgVectorDatabase = mock_pgvector_class

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)

            import asyncio
            asyncio.get_event_loop().run_until_complete(mgr.initialize())

            mock_pgvector_class.assert_called_once_with(
                mock_app,
                host='db.example.com',
                port=5433,
                database='vectordb',
                user='admin',
                password='secret'
            )

    def test_initialize_pgvector_defaults(self):
        """pgvector defaults when no config params."""
        vdb_config = {'use': 'pgvector'}
        mock_app = self._create_mock_app(vdb_config)

        mocks = self._make_vector_import_mocks()
        mock_pgvector_class = MagicMock()
        mocks['langbot.pkg.vector.vdbs.pgvector_db'].PgVectorDatabase = mock_pgvector_class

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)

            import asyncio
            asyncio.get_event_loop().run_until_complete(mgr.initialize())

            mock_pgvector_class.assert_called_once_with(
                mock_app,
                host='localhost',
                port=5432,
                database='langbot',
                user='postgres',
                password='postgres'
            )

    def test_initialize_unknown_backend_defaults_to_chroma(self):
        """Unknown vdb type defaults to Chroma with warning."""
        vdb_config = {'use': 'unknown_backend'}
        mock_app = self._create_mock_app(vdb_config)

        mocks = self._make_vector_import_mocks()
        mock_chroma_class = MagicMock()
        mocks['langbot.pkg.vector.vdbs.chroma'].ChromaVectorDatabase = mock_chroma_class

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)

            import asyncio
            asyncio.get_event_loop().run_until_complete(mgr.initialize())

            mock_chroma_class.assert_called_once_with(mock_app)
            mock_app.logger.warning.assert_called()
            # Should warn about no valid backend
            warning_msg = mock_app.logger.warning.call_args[0][0]
            assert 'No valid' in warning_msg or 'defaulting' in warning_msg


class TestVectorDBManagerProxies:
    """Tests for VectorDBManager proxy methods."""

    def test_get_supported_search_types_no_vector_db(self):
        """get_supported_search_types returns vector when no vector_db."""
        mock_app = MagicMock()
        mock_app.instance_config = MagicMock()
        mock_app.instance_config.data = MagicMock()
        mock_app.instance_config.data.get = MagicMock(return_value=None)
        mock_app.logger = MagicMock()

        mocks = {'langbot.pkg.core.app': MagicMock()}
        for backend in ['chroma', 'qdrant', 'seekdb', 'milvus', 'pgvector_db']:
            mocks[f'langbot.pkg.vector.vdbs.{backend}'] = MagicMock()

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)
            mgr.vector_db = None  # Explicitly None

            result = mgr.get_supported_search_types()
            assert result == ['vector']

    def test_get_supported_search_types_with_vector_db(self):
        """get_supported_search_types delegates to vector_db."""
        mock_app = MagicMock()

        # Create mock vector_db with supported_search_types
        mock_vector_db = MagicMock()
        mock_vector_db.supported_search_types = MagicMock(
            return_value=[
                MagicMock(value='vector'),
                MagicMock(value='full_text'),
            ]
        )

        mocks = {'langbot.pkg.core.app': MagicMock()}
        for backend in ['chroma', 'qdrant', 'seekdb', 'milvus', 'pgvector_db']:
            mocks[f'langbot.pkg.vector.vdbs.{backend}'] = MagicMock()

        with isolated_sys_modules(mocks):
            from langbot.pkg.vector.mgr import VectorDBManager

            mgr = VectorDBManager(mock_app)
            mgr.vector_db = mock_vector_db

            result = mgr.get_supported_search_types()
            assert result == ['vector', 'full_text']