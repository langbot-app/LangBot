"""Artifact store for managing Host-owned artifacts."""
from __future__ import annotations

import json
import datetime
import typing
import uuid
import base64
import os

import sqlalchemy
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession
from sqlalchemy.orm import sessionmaker

from ...entity.persistence.artifact import AgentArtifact
from ...entity.persistence.bstorage import BinaryStorage

_FILE_ARTIFACT_METADATA_KEY = '_langbot_file_artifact'


class ArtifactStore:
    """Store for AgentArtifact records.

    Handles artifact metadata registration and content retrieval.
    Actual blob storage is delegated to BinaryStorage or external storage.

    All methods are async and use the provided database engine.
    """

    engine: AsyncEngine

    # Hard limits
    MAX_INLINE_READ_BYTES = 1024 * 1024  # 1MB max for inline base64
    MAX_RANGE_READ_BYTES = 10 * 1024 * 1024  # 10MB max for range reads

    def __init__(self, engine: AsyncEngine):
        self.engine = engine
        self._session_factory = sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

    async def register_file_artifact(
        self,
        *,
        artifact_id: str | None,
        host_path: str,
        host_root: str,
        artifact_type: str = 'file',
        source: str = 'tool',
        mime_type: str | None = None,
        name: str | None = None,
        size_bytes: int | None = None,
        sha256: str | None = None,
        conversation_id: str | None = None,
        run_id: str | None = None,
        runner_id: str | None = None,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        expires_at: datetime.datetime | None = None,
        metadata: dict[str, typing.Any] | None = None,
    ) -> str:
        """Register a Host-owned artifact backed by a bounded local file path.

        The public metadata intentionally excludes the real host path. Reads go
        through read_artifact(), which revalidates the path against host_root.
        """
        real_path, real_root = self._validate_file_artifact_path(host_path, host_root)
        if not os.path.isfile(real_path):
            raise ValueError('file artifact path must point to a file')

        public_metadata = dict(metadata or {})
        public_metadata[_FILE_ARTIFACT_METADATA_KEY] = {
            'path': real_path,
            'root': real_root,
        }

        if size_bytes is None:
            size_bytes = os.path.getsize(real_path)

        return await self.register_artifact(
            artifact_id=artifact_id,
            artifact_type=artifact_type,
            source=source,
            storage_key=f'file:{uuid.uuid4().hex}',
            storage_type='file',
            mime_type=mime_type,
            name=name or os.path.basename(real_path),
            size_bytes=size_bytes,
            sha256=sha256,
            conversation_id=conversation_id,
            run_id=run_id,
            runner_id=runner_id,
            bot_id=bot_id,
            workspace_id=workspace_id,
            expires_at=expires_at,
            metadata=public_metadata,
            content=None,
        )

    async def register_artifact(
        self,
        artifact_id: str | None,
        artifact_type: str,
        source: str,
        storage_key: str | None = None,
        storage_type: str = 'binary_storage',
        mime_type: str | None = None,
        name: str | None = None,
        size_bytes: int | None = None,
        sha256: str | None = None,
        conversation_id: str | None = None,
        run_id: str | None = None,
        runner_id: str | None = None,
        bot_id: str | None = None,
        workspace_id: str | None = None,
        expires_at: datetime.datetime | None = None,
        metadata: dict[str, typing.Any] | None = None,
        content: bytes | None = None,
    ) -> str:
        """Register a new artifact.

        If content is provided and storage_key is None, stores content
        in BinaryStorage automatically.

        Args:
            artifact_id: Unique artifact ID (generated if None)
            artifact_type: Type of artifact (image, file, voice, tool_result, etc.)
            source: Source of artifact (platform, runner, tool, system)
            storage_key: Key in BinaryStorage or external reference
            storage_type: Storage type (binary_storage, file, url)
            mime_type: MIME type
            name: Original file name
            size_bytes: Size in bytes
            sha256: SHA256 hash
            conversation_id: Conversation ID
            run_id: Run ID that created this
            runner_id: Runner ID that created this
            bot_id: Bot UUID
            workspace_id: Workspace ID
            expires_at: Expiration time
            metadata: Additional metadata
            content: Optional content to store in BinaryStorage

        Returns:
            The artifact_id
        """
        if artifact_id is None:
            artifact_id = str(uuid.uuid4())

        # If content provided, store in BinaryStorage
        if content is not None and storage_key is None:
            storage_key = f"artifact:{artifact_id}"
            storage_type = 'binary_storage'
            if size_bytes is None:
                size_bytes = len(content)

        async with self._session_factory() as session:
            # Store content in BinaryStorage if provided
            if content is not None:
                binary_storage = BinaryStorage(
                    unique_key=f'artifact:{artifact_id}',
                    key=storage_key,
                    owner_type='artifact',
                    owner='host',
                    value=content,
                )
                session.add(binary_storage)

            # Store artifact metadata
            artifact = AgentArtifact(
                artifact_id=artifact_id,
                artifact_type=artifact_type,
                mime_type=mime_type,
                name=name,
                size_bytes=size_bytes,
                sha256=sha256,
                source=source,
                storage_key=storage_key,
                storage_type=storage_type,
                conversation_id=conversation_id,
                run_id=run_id,
                runner_id=runner_id,
                bot_id=bot_id,
                workspace_id=workspace_id,
                created_at=datetime.datetime.utcnow(),
                expires_at=expires_at,
                metadata_json=json.dumps(metadata) if metadata else None,
            )
            session.add(artifact)
            await session.commit()

        return artifact_id

    async def get_metadata(
        self,
        artifact_id: str,
    ) -> dict[str, typing.Any] | None:
        """Get artifact metadata (public fields only, no internal storage info).

        Args:
            artifact_id: Artifact ID

        Returns:
            Artifact metadata dict compatible with SDK ArtifactMetadata, or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(AgentArtifact).where(
                    AgentArtifact.artifact_id == artifact_id
                )
            )
            row = result.scalars().first()
            if row is None:
                return None
            if self._is_expired(row):
                return None
            return self._row_to_public_dict(row)

    async def _get_internal_record(
        self,
        artifact_id: str,
    ) -> AgentArtifact | None:
        """Get full artifact record including internal fields.

        Used internally by read_artifact to access storage_key/storage_type.

        Args:
            artifact_id: Artifact ID

        Returns:
            AgentArtifact ORM instance, or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(AgentArtifact).where(
                    AgentArtifact.artifact_id == artifact_id
                )
            )
            record = result.scalars().first()
            if record is not None and self._is_expired(record):
                return None
            return record

    async def read_artifact(
        self,
        artifact_id: str,
        offset: int = 0,
        limit: int | None = None,
    ) -> dict[str, typing.Any] | None:
        """Read artifact content.

        For small artifacts, returns content_base64 directly.
        For large artifacts, returns file_key for chunked transfer.

        Args:
            artifact_id: Artifact ID
            offset: Byte offset to start reading from (must be >= 0)
            limit: Maximum bytes to read (must be > 0 if provided)

        Returns:
            ArtifactReadResult dict, or None if not found

        Raises:
            ValueError: If offset < 0 or limit <= 0
        """
        # Validate offset and limit
        if offset < 0:
            raise ValueError("offset must be >= 0")

        if limit is not None and limit <= 0:
            raise ValueError("limit must be > 0")

        # Get internal record (includes storage_key/storage_type)
        record = await self._get_internal_record(artifact_id)
        if record is None:
            return None

        storage_type = record.storage_type or 'binary_storage'
        storage_key = record.storage_key
        size_bytes = record.size_bytes or 0

        # Cap limit at hard limit
        if limit is None:
            limit = self.MAX_INLINE_READ_BYTES
        limit = min(limit, self.MAX_RANGE_READ_BYTES)

        # For binary_storage, read content
        if storage_type == 'binary_storage' and storage_key:
            content = await self._read_binary_storage(storage_key)
            if content is None:
                return None

            # Apply offset and limit
            if offset > 0:
                content = content[offset:]
            if limit and len(content) > limit:
                content = content[:limit]
                has_more = True
            else:
                has_more = False

            return {
                'artifact_id': artifact_id,
                'mime_type': record.mime_type,
                'size_bytes': size_bytes,
                'offset': offset,
                'length': len(content),
                'content_base64': base64.b64encode(content).decode('utf-8'),
                'file_key': None,
                'has_more': has_more,
            }

        if storage_type == 'file':
            return self._read_file_storage(record, artifact_id, offset, limit)

        # For other storage types, return storage reference
        # (caller can use file_key for chunked transfer)
        return {
            'artifact_id': artifact_id,
            'mime_type': record.mime_type,
            'size_bytes': size_bytes,
            'offset': offset,
            'length': None,
            'content_base64': None,
            'file_key': storage_key,
            'has_more': False,
        }

    async def cleanup_expired_artifacts(
        self,
        *,
        now: datetime.datetime | None = None,
    ) -> int:
        """Delete expired artifact metadata and Host-owned binary blobs.

        Returns the number of artifact metadata rows removed. External/file
        storage references are only dereferenced from LangBot metadata; their
        backing lifecycle remains owned by the storage provider.
        """
        if now is None:
            now = datetime.datetime.utcnow()

        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(AgentArtifact).where(
                    AgentArtifact.expires_at.is_not(None),
                    AgentArtifact.expires_at <= now,
                )
            )
            expired = result.scalars().all()
            if not expired:
                return 0

            binary_storage_keys = [
                artifact.storage_key
                for artifact in expired
                if artifact.storage_type == 'binary_storage' and artifact.storage_key
            ]
            if binary_storage_keys:
                await session.execute(
                    sqlalchemy.delete(BinaryStorage).where(
                        BinaryStorage.unique_key.in_(binary_storage_keys)
                    )
                )

            await session.execute(
                sqlalchemy.delete(AgentArtifact).where(
                    AgentArtifact.id.in_([artifact.id for artifact in expired])
                )
            )
            await session.commit()
            return len(expired)

    async def _read_binary_storage(self, key: str) -> bytes | None:
        """Read content from BinaryStorage.

        Uses unique_key for isolation to prevent cross-artifact access.

        Args:
            key: The unique_key used when storing the artifact

        Returns:
            Content bytes, or None if not found
        """
        async with self._session_factory() as session:
            result = await session.execute(
                sqlalchemy.select(BinaryStorage).where(BinaryStorage.unique_key == key)
            )
            row = result.scalars().first()
            if row is None:
                return None
            return row.value

    def _read_file_storage(
        self,
        record: AgentArtifact,
        artifact_id: str,
        offset: int,
        limit: int,
    ) -> dict[str, typing.Any] | None:
        metadata = self._load_metadata(record.metadata_json)
        file_info = metadata.get(_FILE_ARTIFACT_METADATA_KEY)
        if not isinstance(file_info, dict):
            return None

        host_path = file_info.get('path')
        host_root = file_info.get('root')
        if not isinstance(host_path, str) or not isinstance(host_root, str):
            return None

        real_path, _ = self._validate_file_artifact_path(host_path, host_root)
        if not os.path.isfile(real_path):
            return None

        file_size = os.path.getsize(real_path)
        if offset >= file_size:
            content = b''
        else:
            with open(real_path, 'rb') as f:
                f.seek(offset)
                content = f.read(limit)

        return {
            'artifact_id': artifact_id,
            'mime_type': record.mime_type,
            'size_bytes': file_size,
            'offset': offset,
            'length': len(content),
            'content_base64': base64.b64encode(content).decode('utf-8'),
            'file_key': None,
            'has_more': offset + len(content) < file_size,
        }

    @staticmethod
    def _validate_file_artifact_path(host_path: str, host_root: str) -> tuple[str, str]:
        real_path = os.path.realpath(host_path)
        real_root = os.path.realpath(host_root)
        if not real_root:
            raise ValueError('file artifact root is required')
        if not (real_path == real_root or real_path.startswith(real_root + os.sep)):
            raise ValueError('file artifact path escapes allowed root')
        return real_path, real_root

    @staticmethod
    def _load_metadata(metadata_json: str | None) -> dict[str, typing.Any]:
        if not metadata_json:
            return {}
        try:
            metadata = json.loads(metadata_json)
        except Exception:
            return {}
        return metadata if isinstance(metadata, dict) else {}

    @staticmethod
    def _public_metadata(metadata_json: str | None) -> dict[str, typing.Any]:
        metadata = ArtifactStore._load_metadata(metadata_json)
        metadata.pop(_FILE_ARTIFACT_METADATA_KEY, None)
        return metadata

    @staticmethod
    def _is_expired(
        row: AgentArtifact,
        now: datetime.datetime | None = None,
    ) -> bool:
        if row.expires_at is None:
            return False
        if now is None:
            now = datetime.datetime.utcnow()
        return row.expires_at <= now

    def _row_to_public_dict(self, row: AgentArtifact) -> dict[str, typing.Any]:
        """Convert an AgentArtifact row to public dict.

        Returns only fields that match SDK ArtifactMetadata entity.
        Host-only fields (bot_id, workspace_id, storage_key, storage_type) are excluded.
        """
        return {
            'artifact_id': row.artifact_id,
            'artifact_type': row.artifact_type,
            'mime_type': row.mime_type,
            'name': row.name,
            'size_bytes': row.size_bytes,
            'sha256': row.sha256,
            'source': row.source,
            'conversation_id': row.conversation_id,
            'run_id': row.run_id,
            'runner_id': row.runner_id,
            'created_at': int(row.created_at.timestamp()) if row.created_at else None,
            'expires_at': int(row.expires_at.timestamp()) if row.expires_at else None,
            'metadata': self._public_metadata(row.metadata_json),
        }
