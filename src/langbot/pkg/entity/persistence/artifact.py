"""Artifact persistence entity for Host-owned artifact store."""
from __future__ import annotations

import sqlalchemy
import datetime

from .base import Base


class AgentArtifact(Base):
    """AgentArtifact stores metadata for large files, images, tool results, etc.

    This table only stores metadata. The actual blob content is stored in
    BinaryStorage or external storage, referenced by storage_key.

    Artifacts are accessed via artifact_metadata and artifact_read APIs
    with run_id authorization.
    """

    __tablename__ = 'agent_artifact'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    """Auto-increment ID for sequencing."""

    artifact_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    """Unique artifact identifier."""

    artifact_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    """Artifact type: 'image', 'file', 'voice', 'tool_result', 'platform_attachment', etc."""

    mime_type = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """MIME type of the content."""

    name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Original file name (if applicable)."""

    size_bytes = sqlalchemy.Column(sqlalchemy.BigInteger, nullable=True)
    """Size in bytes."""

    sha256 = sqlalchemy.Column(sqlalchemy.String(64), nullable=True)
    """SHA256 hash of content (for integrity verification)."""

    source = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    """Source of artifact: 'platform', 'runner', 'tool', 'system'."""

    # Storage reference (points to BinaryStorage or external storage)
    storage_key = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Key in BinaryStorage or external storage reference."""

    storage_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='binary_storage')
    """Storage type: 'binary_storage', 'file', 'url', etc."""

    # Context
    conversation_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Conversation this artifact belongs to."""

    run_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Run ID that created this artifact."""

    runner_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Runner ID that created this artifact."""

    bot_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Bot UUID that handled this artifact."""

    workspace_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Workspace ID for multi-tenant deployments."""

    # Lifecycle
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow)
    """When this artifact was created."""

    expires_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    """When this artifact expires (optional)."""

    metadata_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Additional metadata as JSON string."""
