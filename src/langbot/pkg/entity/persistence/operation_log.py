"""Workspace operation log entity for member action traceability.

This table is the append-only fact source for "who did what to which
resource" inside one Workspace. It is deliberately separate from
:mod:`event_log` (Runner/runtime facts) and from monitoring tables
(LLM/tool telemetry) so that administrative traceability can be enabled,
queried and pruned without touching the hot runtime path.

Design constraints
------------------
* One row per recorded operation; no updates after insert (append-only).
* ``changes`` holds the before/after diff as a compact JSON string so the
  log answers the question "what was changed into what".
* Rows are tenant-owned: every row carries ``workspace_uuid`` and is
  covered by the shared Row Level Security contract.
"""

from __future__ import annotations

import sqlalchemy

from .base import Base


# Operation levels, ordered by increasing capture scope. They live in the
# entity module so both the persistence layer and the HTTP layer can import
# one single source of truth without a circular dependency.
OPERATION_LEVEL_NONE = 0
"""Record nothing (tracing disabled for the Workspace)."""

OPERATION_LEVEL_MUTATION = 1
"""Record create / update / delete / role changes only."""

OPERATION_LEVEL_READ = 2
"""Additionally record every read / view / list operation."""

OPERATION_LEVEL_NAMES = {
    OPERATION_LEVEL_NONE: 'off',
    OPERATION_LEVEL_MUTATION: 'mutation',
    OPERATION_LEVEL_READ: 'read',
}


class WorkspaceOperationLog(Base):
    """One traceable administrative operation inside a Workspace."""

    __tablename__ = 'workspace_operation_logs'

    id = sqlalchemy.Column(
        sqlalchemy.BigInteger().with_variant(sqlalchemy.Integer, 'sqlite'), primary_key=True, autoincrement=True
    )

    workspace_uuid = sqlalchemy.Column(
        sqlalchemy.String(36),
        sqlalchemy.ForeignKey('workspaces.uuid', ondelete='CASCADE'),
        nullable=False,
        index=True,
    )
    """Owning Workspace; also the tenant isolation key."""

    # --- Actor: who performed the operation -----------------------------
    actor_account_uuid = sqlalchemy.Column(sqlalchemy.String(36), nullable=True, index=True)
    """Account UUID of the actor, when the principal is an Account."""

    actor_name = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Human readable actor identifier captured at write time."""

    actor_role = sqlalchemy.Column(sqlalchemy.String(32), nullable=True)
    """Workspace role the actor held while performing the operation."""

    principal_type = sqlalchemy.Column(sqlalchemy.String(32), nullable=True)
    """Principal kind (account, api_key, support_admin, system)."""

    api_key_uuid = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """API key UUID when the operation was driven by an API key."""

    auth_type = sqlalchemy.Column(sqlalchemy.String(32), nullable=True)
    """Authentication mode used for the request."""

    # --- Request correlation --------------------------------------------
    request_id = sqlalchemy.Column(sqlalchemy.String(128), nullable=True, index=True)
    """Stable request id shared with logs and error responses."""

    http_method = sqlalchemy.Column(sqlalchemy.String(12), nullable=True)
    """HTTP verb of the traced request."""

    route = sqlalchemy.Column(sqlalchemy.String(512), nullable=True, index=True)
    """Registered Core route identity (never a raw user-supplied URL)."""

    # --- What happened ---------------------------------------------------
    action = sqlalchemy.Column(sqlalchemy.String(64), nullable=True, index=True)
    """Normalized action verb (create, update, delete, view, ...)."""

    resource_type = sqlalchemy.Column(sqlalchemy.String(64), nullable=True, index=True)
    """Resource family the operation targeted (member, resource, ...)."""

    resource_id = sqlalchemy.Column(sqlalchemy.String(255), nullable=True)
    """Identifier of the targeted resource, when known."""

    level = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, server_default='1', index=True)
    """Capture level that produced this row (1 = mutation, 2 = read)."""

    outcome = sqlalchemy.Column(sqlalchemy.String(16), nullable=False, server_default='ok')
    """Result bucket: ok, denied or error."""

    status_code = sqlalchemy.Column(sqlalchemy.Integer, nullable=True)
    """HTTP status code when the operation surfaced one."""

    # --- Payloads --------------------------------------------------------
    summary = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Short human readable description of the operation."""

    changes = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Before/after diff as a JSON string: what was changed into what."""

    detail = sqlalchemy.Column(sqlalchemy.Text, nullable=True)
    """Additional structured context as a JSON string."""

    # --- Tamper evidence (append-only hash chain) ------------------------
    record_hash = sqlalchemy.Column(sqlalchemy.String(64), nullable=True)
    """Keyed hash over this row's canonical content.

    Recomputed on read: a mismatch marks the card as tampered.
    """

    prev_hash = sqlalchemy.Column(sqlalchemy.String(64), nullable=True)
    """Previous record's ``record_hash`` in the same Workspace.

    Linking rows this way makes silent edits or deletions detectable.
    """

    dedupe_key = sqlalchemy.Column(sqlalchemy.String(64), nullable=True, index=True)
    """Hash used to collapse repeated read observations into one row."""

    # --- Client fingerprint ---------------------------------------------
    client_ip = sqlalchemy.Column(sqlalchemy.String(64), nullable=True)
    """Best-effort client address."""

    user_agent = sqlalchemy.Column(sqlalchemy.String(512), nullable=True)
    """Client user agent, truncated before insert."""

    duration_ms = sqlalchemy.Column(sqlalchemy.Integer, nullable=False, server_default='0')
    """Handler wall-clock duration in milliseconds."""

    created_at = sqlalchemy.Column(
        sqlalchemy.DateTime,
        nullable=False,
        server_default=sqlalchemy.func.now(),
        index=True,
    )
    """When the operation was recorded."""

    __table_args__ = (
        sqlalchemy.Index(
            'ix_workspace_operation_logs_workspace_created',
            'workspace_uuid',
            'created_at',
        ),
        sqlalchemy.Index(
            'ix_workspace_operation_logs_workspace_resource',
            'workspace_uuid',
            'resource_type',
            'created_at',
        ),
        sqlalchemy.Index(
            'ix_workspace_operation_logs_workspace_dedupe',
            'workspace_uuid',
            'dedupe_key',
            'created_at',
        ),
        sqlalchemy.CheckConstraint(
            'level IN (0, 1, 2)',
            name='ck_workspace_operation_logs_level',
        ),
        sqlalchemy.CheckConstraint(
            "outcome IN ('ok', 'denied', 'error')",
            name='ck_workspace_operation_logs_outcome',
        ),
    )
