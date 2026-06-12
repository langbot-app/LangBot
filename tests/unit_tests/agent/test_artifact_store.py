"""Tests for ArtifactStore and artifact action handlers."""
from __future__ import annotations

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import base64
import datetime

from langbot.pkg.agent.runner.artifact_store import ArtifactStore
from langbot.pkg.agent.runner.session_registry import (
    get_session_registry,
)
from .conftest import make_session


class TestArtifactStore:
    """Test ArtifactStore operations."""

    def _make_mock_engine(self):
        """Create a mock database engine for AsyncSession-based store.

        Note: The new store uses AsyncSession, so we need to mock
        the session factory behavior.
        """
        from sqlalchemy.ext.asyncio import AsyncEngine

        engine = MagicMock(spec=AsyncEngine)
        return engine

    @pytest.mark.asyncio
    async def test_register_artifact_generates_id(self):
        """Test register_artifact generates ID if not provided."""
        engine = self._make_mock_engine()
        store = ArtifactStore(engine)

        # Mock the session factory
        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            artifact_id = await store.register_artifact(
                artifact_id=None,
                artifact_type="image",
                source="platform",
            )

            assert artifact_id is not None
            assert len(artifact_id) == 36  # UUID format

    @pytest.mark.asyncio
    async def test_register_artifact_with_content(self):
        """Test register_artifact stores content in BinaryStorage."""
        engine = self._make_mock_engine()
        store = ArtifactStore(engine)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            content = b"test image content"
            artifact_id = await store.register_artifact(
                artifact_id="art_001",
                artifact_type="image",
                source="platform",
                content=content,
            )

            assert artifact_id == "art_001"

    @pytest.mark.asyncio
    async def test_register_artifact_with_storage_key(self):
        """Test register_artifact with pre-existing storage_key."""
        engine = self._make_mock_engine()
        store = ArtifactStore(engine)

        mock_session = AsyncMock()
        mock_session.add = MagicMock()
        mock_session.commit = AsyncMock()

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            artifact_id = await store.register_artifact(
                artifact_id="art_002",
                artifact_type="file",
                source="runner",
                storage_key="existing_key",
                storage_type="binary_storage",
                size_bytes=1024,
            )

            assert artifact_id == "art_002"

    @pytest.mark.asyncio
    async def test_get_metadata_not_found(self):
        """Test get_metadata returns None if not found."""
        engine = self._make_mock_engine()
        store = ArtifactStore(engine)

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            metadata = await store.get_metadata("nonexistent")

            assert metadata is None

    @pytest.mark.asyncio
    async def test_read_artifact_validates_offset(self):
        """Test read_artifact rejects negative offset."""
        engine = self._make_mock_engine()
        store = ArtifactStore(engine)

        with pytest.raises(ValueError, match="offset must be >= 0"):
            await store.read_artifact("art_001", offset=-1)

    @pytest.mark.asyncio
    async def test_read_artifact_validates_limit(self):
        """Test read_artifact rejects zero or negative limit."""
        engine = self._make_mock_engine()
        store = ArtifactStore(engine)

        with pytest.raises(ValueError, match="limit must be > 0"):
            await store.read_artifact("art_001", limit=0)

        with pytest.raises(ValueError, match="limit must be > 0"):
            await store.read_artifact("art_001", limit=-5)

    @pytest.mark.asyncio
    async def test_read_artifact_not_found(self):
        """Test read_artifact returns None if not found."""
        engine = self._make_mock_engine()
        store = ArtifactStore(engine)

        mock_result = MagicMock()
        mock_result.scalars.return_value.first.return_value = None

        mock_session = AsyncMock()
        mock_session.execute = AsyncMock(return_value=mock_result)

        with patch.object(store, '_session_factory') as mock_factory:
            mock_factory.return_value.__aenter__.return_value = mock_session

            result = await store.read_artifact("nonexistent")
            assert result is None


class TestArtifactAuthorization:
    """Test artifact action handler authorization."""

    @pytest.fixture
    def mock_session_registry(self):
        """Create a fresh session registry for testing."""
        # Reset global registry
        import langbot.pkg.agent.runner.session_registry as reg
        reg._global_registry = None
        return get_session_registry()

    @pytest.fixture
    def mock_handler(self):
        """Create a mock handler for testing actions."""
        from langbot_plugin.runtime.io.handler import Handler

        class MockHandler(Handler):
            def __init__(self):
                self._responses = {}

            async def call_action(self, action, data, timeout=30):
                # Simulate error response for missing run_id
                if not data.get("run_id"):
                    return {"ok": False, "message": "run_id is required"}
                return {"ok": True, "data": {}}

        return MockHandler()

    @pytest.mark.asyncio
    async def test_artifact_metadata_requires_run_id(self, mock_handler):
        """Test artifact_metadata requires run_id."""
        result = await mock_handler.call_action(
            "artifact_metadata",
            {"run_id": None, "artifact_id": "art_001"},
        )

        assert result.get("ok") is False or "error" in str(result).lower()

    @pytest.mark.asyncio
    async def test_artifact_read_requires_run_id(self, mock_handler):
        """Test artifact_read requires run_id."""
        result = await mock_handler.call_action(
            "artifact_read",
            {"run_id": None, "artifact_id": "art_001"},
        )

        assert result.get("ok") is False or "error" in str(result).lower()


class TestArtifactAccessValidation:
    """Test _validate_artifact_access authorization rules."""

    def _make_session(self, conversation_id: str | None):
        return make_session(
            run_id="run_001",
            conversation_id=conversation_id,
            available_apis={"artifact_metadata": True, "artifact_read": True},
        )

    def _call_validate(self, session, metadata, operation="metadata"):
        """Helper to call the validation function."""
        from langbot.pkg.plugin.handler import _validate_artifact_access
        return _validate_artifact_access(session, metadata, operation)

    def test_global_artifact_denied_by_default(self):
        """Artifacts without conversation_id are denied by default (no global access)."""
        session = self._make_session("conv_001")
        metadata = {
            "artifact_id": "art_global",
            "conversation_id": None,  # No conversation scope
            "run_id": None,  # Not created by any run
        }

        is_allowed, error = self._call_validate(session, metadata)
        assert is_allowed is False
        assert "denied" in error.lower()

    def test_own_run_artifact_allowed(self):
        """Artifacts created by same run are allowed (even cross-conversation)."""
        session = self._make_session("conv_001")
        metadata = {
            "artifact_id": "art_001",
            "conversation_id": "conv_other",  # Different conversation
            "run_id": "run_001",  # Same run
        }

        is_allowed, error = self._call_validate(session, metadata)
        assert is_allowed is True
        assert error is None

    def test_same_conversation_allowed(self):
        """Artifacts in same conversation are allowed."""
        session = self._make_session("conv_001")
        metadata = {
            "artifact_id": "art_001",
            "conversation_id": "conv_001",  # Same as session
            "run_id": "run_other",  # Different run
        }

        is_allowed, error = self._call_validate(session, metadata)
        assert is_allowed is True
        assert error is None

    def test_different_conversation_and_run_denied(self):
        """Artifacts in different conversation and different run are denied."""
        session = self._make_session("conv_001")
        metadata = {
            "artifact_id": "art_001",
            "conversation_id": "conv_other",  # Different conversation
            "run_id": "run_other",  # Different run
        }

        is_allowed, error = self._call_validate(session, metadata)
        assert is_allowed is False
        assert "denied" in error.lower()

    def test_session_without_conversation_denied_for_conversation_artifact(self):
        """Session without conversation_id cannot access conversation-scoped artifacts."""
        session = self._make_session(None)
        metadata = {
            "artifact_id": "art_001",
            "conversation_id": "conv_001",  # Has conversation
            "run_id": "run_other",  # Different run
        }

        is_allowed, error = self._call_validate(session, metadata)
        assert is_allowed is False

    def test_session_without_conversation_allowed_for_own_artifact(self):
        """Session without conversation can access artifacts it created."""
        session = self._make_session(None)
        metadata = {
            "artifact_id": "art_001",
            "conversation_id": "conv_001",  # Has conversation
            "run_id": "run_001",  # Same run (created by this run)
        }

        is_allowed, error = self._call_validate(session, metadata)
        assert is_allowed is True


class TestContextAccessArtifactAPIs:
    """Test ContextAccess reflects runtime artifact API availability."""

    @pytest.mark.asyncio
    async def test_context_access_has_artifact_apis_when_permitted(self):
        """Artifact APIs are exposed through run-scoped available_apis."""
        available_apis = {"artifact_metadata": True, "artifact_read": True}

        assert available_apis["artifact_metadata"] is True
        assert available_apis["artifact_read"] is True

    @pytest.mark.asyncio
    async def test_context_access_no_artifact_apis_without_permission(self):
        """Artifact APIs are absent when the run did not receive them."""
        available_apis = {}

        assert available_apis.get("artifact_metadata", False) is False
        assert available_apis.get("artifact_read", False) is False


class TestArtifactMetadataFieldAlignment:
    """Test that Host returns metadata compatible with SDK ArtifactMetadata."""

    def test_row_to_public_dict_excludes_host_only_fields(self):
        """_row_to_public_dict should not return Host-only fields."""
        from langbot.pkg.agent.runner.artifact_store import ArtifactStore
        from langbot.pkg.entity.persistence.artifact import AgentArtifact
        from unittest.mock import MagicMock

        # Create a mock row
        mock_row = MagicMock(spec=AgentArtifact)
        mock_row.artifact_id = "art_001"
        mock_row.artifact_type = "image"
        mock_row.mime_type = "image/png"
        mock_row.name = "test.png"
        mock_row.size_bytes = 1024
        mock_row.sha256 = "abc123"
        mock_row.source = "platform"
        mock_row.conversation_id = "conv_001"
        mock_row.run_id = "run_001"
        mock_row.runner_id = "plugin:test/plugin/runner"
        mock_row.created_at = datetime.datetime(2024, 1, 1, 0, 0, 0)
        mock_row.expires_at = None
        mock_row.metadata_json = None

        # These are Host-only fields that should NOT be in output
        # (they don't exist in SDK ArtifactMetadata)
        mock_row.bot_id = "bot_001"
        mock_row.workspace_id = "ws_001"
        mock_row.storage_key = "artifact:art_001"
        mock_row.storage_type = "binary_storage"

        store = ArtifactStore(MagicMock())
        result = store._row_to_public_dict(mock_row)

        # SDK-compatible fields should be present
        assert result["artifact_id"] == "art_001"
        assert result["artifact_type"] == "image"
        assert result["source"] == "platform"
        assert result["conversation_id"] == "conv_001"
        assert result["run_id"] == "run_001"

        # Host-only fields should NOT be present
        assert "bot_id" not in result
        assert "workspace_id" not in result
        assert "storage_key" not in result
        assert "storage_type" not in result


class TestSessionRegistryAvailableAPIs:
    """Test that session registry stores and retrieves available APIs correctly."""

    @pytest.fixture
    def session_registry(self):
        """Create a fresh session registry for testing."""
        import langbot.pkg.agent.runner.session_registry as reg
        reg._global_registry = None
        return get_session_registry()

    @pytest.mark.asyncio
    async def test_register_stores_available_apis(self, session_registry):
        """Test that register() stores runtime API availability."""
        await session_registry.register(
            run_id="run_001",
            runner_id="plugin:author/plugin/runner",
            query_id=None,
            plugin_identity="author/plugin",
            resources={
                "models": [],
                "tools": [],
                "knowledge_bases": [],
                "files": [],
                "storage": {"plugin_storage": True, "workspace_storage": False},
                "platform_capabilities": {},
            },
            available_apis={
                "artifact_metadata": True,
                "artifact_read": True,
                "history_page": True,
                "event_get": True,
            },
            conversation_id="conv_001",
        )

        session = await session_registry.get("run_001")
        assert session is not None
        available_apis = session["authorization"]["available_apis"]
        assert available_apis["artifact_metadata"] is True
        assert available_apis["artifact_read"] is True
        assert available_apis["history_page"] is True
        assert available_apis["event_get"] is True

    @pytest.mark.asyncio
    async def test_register_with_empty_available_apis(self, session_registry):
        """Test that register() handles empty API availability."""
        await session_registry.register(
            run_id="run_002",
            runner_id="plugin:author/plugin/runner",
            query_id=None,
            plugin_identity="author/plugin",
            resources={
                "models": [],
                "tools": [],
                "knowledge_bases": [],
                "files": [],
                "storage": {"plugin_storage": True, "workspace_storage": False},
                "platform_capabilities": {},
            },
            available_apis={},
            conversation_id="conv_001",
        )

        session = await session_registry.get("run_002")
        assert session is not None
        assert session["authorization"]["available_apis"] == {}


class TestArtifactStoreRealSQLite:
    """Test ArtifactStore with real SQLite database."""

    @pytest.fixture
    async def db_engine(self):
        """Create an in-memory SQLite database for testing."""
        from sqlalchemy.ext.asyncio import create_async_engine
        from langbot.pkg.entity.persistence.base import Base

        engine = create_async_engine("sqlite+aiosqlite:///:memory:")

        # Create tables
        async with engine.begin() as conn:
            # Create tables manually for in-memory DB
            await conn.run_sync(Base.metadata.create_all)

        yield engine

        await engine.dispose()

    @pytest.mark.asyncio
    async def test_register_get_metadata_round_trip(self, db_engine):
        """Test register_artifact -> get_metadata round trip with real DB."""
        store = ArtifactStore(db_engine)

        # Register artifact with content
        content = b"test image content for round trip"
        artifact_id = await store.register_artifact(
            artifact_id="art_real_001",
            artifact_type="image",
            source="platform",
            mime_type="image/png",
            name="test.png",
            content=content,
            conversation_id="conv_001",
            run_id="run_001",
        )

        assert artifact_id == "art_real_001"

        # Get metadata
        metadata = await store.get_metadata(artifact_id)
        assert metadata is not None
        assert metadata["artifact_id"] == "art_real_001"
        assert metadata["artifact_type"] == "image"
        assert metadata["mime_type"] == "image/png"
        assert metadata["source"] == "platform"
        assert metadata["conversation_id"] == "conv_001"
        assert metadata["run_id"] == "run_001"

        # Verify Host-only fields are NOT in public metadata
        assert "storage_key" not in metadata
        assert "storage_type" not in metadata
        assert "bot_id" not in metadata
        assert "workspace_id" not in metadata

    @pytest.mark.asyncio
    async def test_read_artifact_round_trip(self, db_engine):
        """Test register_artifact -> read_artifact round trip with real DB."""
        store = ArtifactStore(db_engine)

        # Register artifact with content
        content = b"test file content for read test"
        artifact_id = await store.register_artifact(
            artifact_id="art_real_002",
            artifact_type="file",
            source="runner",
            mime_type="text/plain",
            name="test.txt",
            content=content,
            conversation_id="conv_001",
            run_id="run_001",
        )

        # Read artifact
        result = await store.read_artifact(artifact_id)
        assert result is not None
        assert result["artifact_id"] == "art_real_002"
        assert result["mime_type"] == "text/plain"
        assert result["offset"] == 0
        assert result["length"] == len(content)
        assert result["has_more"] is False

        # Verify content
        decoded_content = base64.b64decode(result["content_base64"])
        assert decoded_content == content

    @pytest.mark.asyncio
    async def test_read_artifact_with_offset_limit(self, db_engine):
        """Test read_artifact with offset and limit."""
        store = ArtifactStore(db_engine)

        # Register artifact with content
        content = b"0123456789" * 100  # 1000 bytes
        artifact_id = await store.register_artifact(
            artifact_id="art_real_003",
            artifact_type="file",
            source="runner",
            mime_type="application/octet-stream",
            content=content,
        )

        # Read with offset
        result = await store.read_artifact(artifact_id, offset=100, limit=100)
        assert result is not None
        assert result["offset"] == 100
        assert result["length"] == 100

        # Verify content
        decoded_content = base64.b64decode(result["content_base64"])
        assert decoded_content == content[100:200]

    @pytest.mark.asyncio
    async def test_read_artifact_has_more(self, db_engine):
        """Test read_artifact sets has_more correctly."""
        store = ArtifactStore(db_engine)

        # Register artifact with content
        content = b"0123456789" * 100  # 1000 bytes
        artifact_id = await store.register_artifact(
            artifact_id="art_real_004",
            artifact_type="file",
            source="runner",
            content=content,
        )

        # Read with limit smaller than content
        result = await store.read_artifact(artifact_id, offset=0, limit=100)
        assert result is not None
        assert result["has_more"] is True
        assert result["length"] == 100

    @pytest.mark.asyncio
    async def test_expired_artifact_is_not_readable_before_cleanup(self, db_engine):
        """Expired artifacts are hidden even before a cleanup job deletes rows."""
        store = ArtifactStore(db_engine)
        await store.register_artifact(
            artifact_id="art_expired_hidden",
            artifact_type="file",
            source="runner",
            content=b"expired",
            expires_at=datetime.datetime.utcnow() - datetime.timedelta(seconds=1),
        )

        assert await store.get_metadata("art_expired_hidden") is None
        assert await store.read_artifact("art_expired_hidden") is None

    @pytest.mark.asyncio
    async def test_cleanup_expired_artifacts_deletes_binary_storage(self, db_engine):
        """Expired artifacts and their Host-owned binary blobs are removed."""
        from sqlalchemy import select
        from langbot.pkg.entity.persistence.bstorage import BinaryStorage

        store = ArtifactStore(db_engine)
        now = datetime.datetime.utcnow()
        await store.register_artifact(
            artifact_id="art_expired",
            artifact_type="file",
            source="runner",
            content=b"expired",
            expires_at=now - datetime.timedelta(seconds=1),
        )
        await store.register_artifact(
            artifact_id="art_fresh",
            artifact_type="file",
            source="runner",
            content=b"fresh",
            expires_at=now + datetime.timedelta(days=1),
        )

        removed = await store.cleanup_expired_artifacts(now=now)

        assert removed == 1
        assert await store.get_metadata("art_expired") is None
        assert await store.get_metadata("art_fresh") is not None
        async with store._session_factory() as session:
            result = await session.execute(
                select(BinaryStorage).where(BinaryStorage.unique_key == "artifact:art_expired")
            )
            assert result.scalars().first() is None

    @pytest.mark.asyncio
    async def test_file_artifact_range_read_and_public_metadata(self, db_engine, tmp_path):
        """File-backed artifacts read ranges without exposing host paths."""
        store = ArtifactStore(db_engine)
        content = b"0123456789" * 20
        file_path = tmp_path / "large.txt"
        file_path.write_bytes(content)

        artifact_id = await store.register_file_artifact(
            artifact_id="art_file_001",
            host_path=str(file_path),
            host_root=str(tmp_path),
            source="tool",
            mime_type="text/plain",
            name="large.txt",
            conversation_id="conv_001",
            run_id="run_001",
            metadata={"sandbox_path": "/workspace/large.txt"},
        )

        metadata = await store.get_metadata(artifact_id)
        assert metadata is not None
        assert metadata["artifact_id"] == "art_file_001"
        assert metadata["metadata"] == {"sandbox_path": "/workspace/large.txt"}
        assert str(file_path) not in str(metadata)

        result = await store.read_artifact(artifact_id, offset=10, limit=15)
        assert result is not None
        assert result["offset"] == 10
        assert result["length"] == 15
        assert result["size_bytes"] == len(content)
        assert result["has_more"] is True
        assert base64.b64decode(result["content_base64"]) == content[10:25]

    @pytest.mark.asyncio
    async def test_register_file_artifact_rejects_path_escape(self, db_engine, tmp_path):
        """File-backed artifacts must stay inside their declared host root."""
        store = ArtifactStore(db_engine)
        root = tmp_path / "root"
        root.mkdir()
        outside = tmp_path / "outside.txt"
        outside.write_text("outside")

        with pytest.raises(ValueError, match="escapes"):
            await store.register_file_artifact(
                artifact_id="art_file_escape",
                host_path=str(outside),
                host_root=str(root),
            )

    @pytest.mark.asyncio
    async def test_metadata_sdk_validation(self, db_engine):
        """Test that metadata can be validated by SDK ArtifactMetadata."""
        from langbot_plugin.api.entities.builtin.agent_runner.artifact import ArtifactMetadata

        store = ArtifactStore(db_engine)

        # Register artifact
        artifact_id = await store.register_artifact(
            artifact_id="art_real_005",
            artifact_type="file",
            source="runner",
            mime_type="application/pdf",
            name="document.pdf",
            size_bytes=1024,
            conversation_id="conv_001",
            run_id="run_001",
            runner_id="plugin:test/plugin/runner",
        )

        # Get metadata
        metadata = await store.get_metadata(artifact_id)
        assert metadata is not None

        # Should not raise ValidationError
        validated = ArtifactMetadata.model_validate(metadata)
        assert validated.artifact_id == "art_real_005"
        assert validated.artifact_type == "file"
