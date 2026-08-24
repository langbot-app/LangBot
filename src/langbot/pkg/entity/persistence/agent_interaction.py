"""Host-owned structured interaction persistence entities."""

from __future__ import annotations

import datetime

import sqlalchemy

from .base import Base


class AgentInteraction(Base):
    """Persist one interaction request and its eventual submission."""

    __tablename__ = 'agent_interaction'

    id = sqlalchemy.Column(sqlalchemy.Integer, primary_key=True, autoincrement=True)
    interaction_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False)
    run_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    binding_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    runner_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)
    processor_type = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, index=True)
    processor_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=False, index=True)

    bot_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    workspace_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    conversation_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)
    thread_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    actor_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True, index=True)

    status = sqlalchemy.Column(sqlalchemy.String(50), nullable=False, index=True)
    request_json = sqlalchemy.Column(sqlalchemy.Text, nullable=False)
    delivery_target_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    delivery_result_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    replaces_interaction_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    callback_token_hash = sqlalchemy.Column(sqlalchemy.String(64), nullable=False, unique=True, index=True)

    expires_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True, index=True)
    submitted_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=True)
    submission_json = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    status_reason = sqlalchemy.Column(sqlalchemy.Text, nullable=True)

    created_at = sqlalchemy.Column(sqlalchemy.DateTime, nullable=False, default=datetime.datetime.utcnow)
    updated_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        default=datetime.datetime.utcnow,
        onupdate=datetime.datetime.utcnow,
    )

    __table_args__ = (
        sqlalchemy.UniqueConstraint('run_id', 'interaction_id', name='uq_agent_interaction_run_interaction'),
        sqlalchemy.Index(
            'ix_agent_interaction_scope_status',
            'bot_id',
            'conversation_id',
            'actor_id',
            'status',
        ),
        sqlalchemy.Index('ix_agent_interaction_processor_status', 'processor_type', 'processor_id', 'status'),
    )
