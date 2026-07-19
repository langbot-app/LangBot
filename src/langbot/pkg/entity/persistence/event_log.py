"""EventLog persistence entity for storing auditable event facts."""
from __future__ import annotations

import sqlalchemy
import datetime

from .base import Base


class EventLog(Base):
    """EventLog stores auditable event records for AgentRunner.

    This is the fact source for events - messages, tool calls, system events, etc.
    Large payloads are stored separately; this table stores references and
    summaries.
    """

    __tablename__ = 'event_log'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    """Auto-increment ID for sequencing."""

    event_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    """Unique event identifier."""

    event_type = sqlalchemy.Column(sqlalchemy.String(100), nullable=False, index=True)
    """Event type (message.received, tool.call.started, etc.)."""

    event_time = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    """When the event occurred."""

    source = sqlalchemy.Column(sqlalchemy.String(50), nullable=False)
    """Event source (platform, webui, api, scheduler, system, pipeline_adapter)."""

    bot_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Bot UUID that handled this event."""

    workspace_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Workspace ID for multi-tenant deployments."""

    conversation_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Conversation ID this event belongs to."""

    thread_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Thread ID if platform supports threads."""

    # Actor information
    actor_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=True)
    """Actor type (user, system, runner)."""

    actor_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Actor identifier."""

    actor_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Actor display name."""

    # Subject information
    subject_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=True)
    """Subject type (message, tool_call, attachment, etc.)."""

    subject_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Subject identifier."""

    # Input information
    input_summary = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Brief summary of input (truncated text, max 1000 chars)."""

    input_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Full input JSON if reasonably sized (AgentInput as JSON string)."""

    # Raw event reference
    raw_ref = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Reference to raw event payload stored outside the inline event row."""

    run_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Run ID that processed this event."""

    runner_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Runner ID that processed this event."""

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow)
    """When this record was created."""

    metadata_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Additional metadata as JSON string."""
