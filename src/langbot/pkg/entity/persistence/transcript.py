"""Transcript persistence entity for conversation history projection."""
from __future__ import annotations

import sqlalchemy
import datetime

from .base import Base


class Transcript(Base):
    """Transcript stores conversation-oriented message projection for history API.

    This is a projection of EventLog, optimized for agent history retrieval.
    It includes message content and artifact refs, but not raw platform payloads.
    """

    __tablename__ = 'transcript'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    """Auto-increment ID for sequencing."""

    transcript_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    """Unique transcript item identifier."""

    event_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    """Reference to the source event in EventLog."""

    conversation_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    """Conversation this item belongs to."""

    thread_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Thread ID if platform supports threads."""

    role = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    """Message role: 'user', 'assistant', 'system', or 'tool'."""

    item_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, default='message')
    """Item type: 'message', 'tool_call', 'tool_result', 'system'."""

    # Content
    content = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Text content summary (may be truncated for large messages, max 4000 chars)."""

    content_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Full structured content as JSON string (Message model dump)."""

    # Artifact references
    artifact_refs_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Artifact references as JSON string (list of ArtifactRef)."""

    # Sequence for cursor-based pagination
    seq = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, index=True)
    """Monotonic cursor sequence for pagination."""

    # Context
    run_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Run ID that generated this item (for assistant messages)."""

    runner_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Runner ID that generated this item."""

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow)
    """When this item was created."""

    metadata_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Additional metadata as JSON string (sender_id, platform, etc.)."""

    # Indexes
    __table_args__ = (
        sqlalchemy.Index('ix_transcript_conversation_seq', 'conversation_id', 'seq'),
        sqlalchemy.Index('ix_transcript_conversation_created', 'conversation_id', 'created_at'),
    )
