"""Backward-compatible HTTP import surface for transport-neutral contexts."""

from ..context import (
    ExecutionContext,
    PrincipalContext,
    PrincipalType,
    RequestContext,
    WorkspaceContext,
)

__all__ = [
    'ExecutionContext',
    'PrincipalContext',
    'PrincipalType',
    'RequestContext',
    'WorkspaceContext',
]
