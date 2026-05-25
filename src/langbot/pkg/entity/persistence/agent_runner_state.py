"""Agent runner state persistence entity for host-owned state."""
from __future__ import annotations

import sqlalchemy
import datetime

from .base import Base


class AgentRunnerState(Base):
    """AgentRunnerState stores host-owned state for AgentRunner protocol.

    State is:
    - Host-owned: Managed by LangBot, not by plugin instances
    - Scope-isolated: Separated by runner_id + binding_identity + scope
    - Policy-enforced: Controlled by StatePolicy (enable_state, state_scopes)

    Scope key design:
    - conversation: runner_id + binding_id + conversation_id [+ thread_id]
    - actor: runner_id + binding_id + actor_type + actor_id
    - subject: runner_id + binding_id + subject_type + subject_id
    - runner: runner_id + binding_id

    This table is the production store for AgentRunner state.
    """

    __tablename__ = 'agent_runner_state'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    """Auto-increment ID for sequencing."""

    # Identity
    runner_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    """Runner descriptor ID (plugin:author/name/runner)."""

    binding_identity = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    """Binding identity for isolation (binding_id or scope_type:scope_id)."""

    scope = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, index=True)
    """State scope: 'conversation', 'actor', 'subject', or 'runner'."""

    scope_key = sqlalchemy.Column(sqlalchemy.String(512), nullable=False, index=True)
    """Full scope key for unique lookup (includes all identity parts)."""

    state_key = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    """State key within scope (should use namespace prefix like external.*)."""

    value_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """State value as JSON string (size-limited by host)."""

    # Context fields for querying/filtering
    bot_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Bot UUID if applicable."""

    workspace_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Workspace ID for multi-tenant."""

    conversation_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Conversation ID for conversation scope."""

    thread_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Thread ID for thread-scoped conversation state."""

    actor_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=True)
    """Actor type for actor scope."""

    actor_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    """Actor ID for actor scope."""

    subject_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=True)
    """Subject type for subject scope."""

    subject_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Subject ID for subject scope."""

    # Lifecycle
    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow)
    """When this state entry was created."""

    updated_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow, onupdate=datetime.datetime.utcnow)
    """When this state entry was last updated."""

    # Unique constraint: scope_key + state_key
    __table_args__ = (
        sqlalchemy.UniqueConstraint('scope_key', 'state_key', name='uq_agent_runner_state_scope_key_state_key'),
        sqlalchemy.Index('ix_agent_runner_state_runner_binding', 'runner_id', 'binding_identity'),
        sqlalchemy.Index('ix_agent_runner_state_scope_key_lookup', 'scope_key'),
    )
