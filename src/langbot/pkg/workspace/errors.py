from __future__ import annotations


class WorkspaceError(Exception):
    """Base error for workspace directory operations."""


class WorkspaceNotFoundError(WorkspaceError):
    """Raised when the instance does not have its required local workspace."""


class WorkspaceInvariantError(WorkspaceError):
    """Raised when persisted workspace state violates a tenancy invariant."""


class WorkspaceLimitExceededError(WorkspaceError):
    """Raised when OSS code attempts to create a second local workspace."""

    code = 'edition_limit'


class WorkspaceOwnerAlreadyExistsError(WorkspaceError):
    """Raised when another account already owns the singleton workspace."""


class WorkspaceExecutionUnavailableError(WorkspaceError):
    """Raised when a Workspace cannot accept work in its current execution state."""


class WorkspaceGenerationMismatchError(WorkspaceExecutionUnavailableError):
    """Raised when a caller holds a stale Workspace placement generation."""
