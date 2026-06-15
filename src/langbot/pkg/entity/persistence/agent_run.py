"""Agent run ledger persistence entities."""

from __future__ import annotations

import datetime

import sqlalchemy

from .base import Base


class AgentRun(Base):
    """AgentRun stores Host-owned execution lifecycle facts."""

    __tablename__ = 'agent_run'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    """Auto-increment ID for pagination."""

    run_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    """Unique AgentRunner run identifier."""

    event_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Input event that triggered this run."""

    agent_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Future Host-owned agent identifier."""

    binding_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Binding that selected this runner."""

    runner_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    """Runner descriptor ID."""

    conversation_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Conversation this run belongs to."""

    thread_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Thread this run belongs to."""

    workspace_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Workspace this run belongs to."""

    bot_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Bot UUID this run belongs to."""

    status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, index=True)
    """Run lifecycle status."""

    status_reason = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Human-readable terminal or current status reason."""

    queue_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Host queue name this run is waiting in."""

    priority = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    """Higher values are claimed before lower values within a queue."""

    requested_runtime_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Specific runtime requested by the producer, if any."""

    claimed_by_runtime_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Runtime that currently owns the claim lease."""

    claim_token = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Opaque token required to renew or release the current claim."""

    claim_lease_expires_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True, index=True)
    """When the current claim lease expires."""

    dispatch_attempts = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, default=0)
    """Number of times this run has been claimed for dispatch."""

    last_claimed_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    """When this run was last claimed."""

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow)
    """When the run record was created."""

    started_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    """When execution started."""

    finished_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    """When execution reached a terminal status."""

    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    """When the run record was last updated."""

    deadline_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    """Execution deadline if one was assigned."""

    cancel_requested_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    """When cancellation was requested."""

    usage_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Final or latest aggregate token usage JSON."""

    cost_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Host-calculated cost JSON, if available."""

    authorization_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Run-scoped authorization snapshot JSON."""

    metadata_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Additional metadata JSON."""

    __table_args__ = (
        sqlalchemy.Index(
            'ix_agent_run_scope_status', 'bot_id', 'workspace_id', 'conversation_id', 'thread_id', 'status'
        ),
        sqlalchemy.Index('ix_agent_run_runner_status', 'runner_id', 'status'),
        sqlalchemy.Index('ix_agent_run_queue_claim', 'queue_name', 'status', 'priority', 'id'),
    )


class AgentRuntime(Base):
    """AgentRuntime stores Host-owned runtime heartbeat registry facts."""

    __tablename__ = 'agent_runtime'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    """Auto-increment ID."""

    runtime_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, unique=True, index=True)
    """Unique runtime or daemon identifier."""

    status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, index=True)
    """Runtime lifecycle status."""

    display_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Human-readable runtime display name."""

    endpoint = sqlalchemy.Column(sqlalchemy.String(1024), nullable=True)
    """Runtime endpoint, if it exposes one."""

    version = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Runtime version string."""

    capabilities_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Runtime capabilities JSON."""

    labels_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Runtime labels JSON."""

    metadata_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Additional metadata JSON."""

    last_heartbeat_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True, index=True)
    """When the runtime last sent a heartbeat."""

    heartbeat_deadline_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True, index=True)
    """When the runtime should be considered stale."""

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow)
    """When the runtime record was created."""

    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow
    )
    """When the runtime record was last updated."""


class AgentRunEvent(Base):
    """AgentRunEvent stores one result event emitted by a run."""

    __tablename__ = 'agent_run_event'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    """Auto-increment ID."""

    run_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    """Run that produced this event."""

    sequence = sqlalchemy.Column(sqlalchemy.Integer, nullable=False)
    """Monotonic sequence inside the run."""

    type = sqlalchemy.Column(sqlalchemy.String(100), nullable=False, index=True)
    """Result event type."""

    data_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Result event payload JSON."""

    usage_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Token usage JSON for this event, if provided."""

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow)
    """When this event was persisted."""

    source = sqlalchemy.Column(sqlalchemy.String(50), nullable=True)
    """Source that appended the event."""

    artifact_refs_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Artifact references associated with this event."""

    metadata_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Additional metadata JSON."""

    __table_args__ = (
        sqlalchemy.UniqueConstraint('run_id', 'sequence', name='uq_agent_run_event_run_sequence'),
        sqlalchemy.Index('ix_agent_run_event_run_sequence', 'run_id', 'sequence'),
    )
