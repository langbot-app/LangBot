from __future__ import annotations

from dataclasses import dataclass

from .errors import WorkspaceLimitExceededError


@dataclass(frozen=True, slots=True)
class SingleWorkspacePolicy:
    """OSS edition policy: one local workspace with unrestricted membership count."""

    workspace_limit: int = 1
    members_enabled: bool = True
    invitations_enabled: bool = True
    fixed_rbac_enabled: bool = True
    multi_workspace_enabled: bool = False

    def require_workspace_creation_allowed(self, current_workspace_count: int) -> None:
        if current_workspace_count >= self.workspace_limit:
            raise WorkspaceLimitExceededError(f'This LangBot edition allows at most {self.workspace_limit} workspace')


@dataclass(frozen=True, slots=True)
class CloudWorkspacePolicy:
    """SaaS data-plane policy backed by closed control-plane projections.

    Core never creates a cloud Workspace or mutates its directory.  The policy
    only enables explicit selection among already projected Workspaces.
    """

    workspace_limit: int = 0
    members_enabled: bool = True
    invitations_enabled: bool = False
    fixed_rbac_enabled: bool = True
    multi_workspace_enabled: bool = True

    def require_workspace_creation_allowed(self, current_workspace_count: int) -> None:
        del current_workspace_count
        raise WorkspaceLimitExceededError('Cloud Workspaces are created by the SaaS control plane')


def open_core_workspace_policy() -> SingleWorkspacePolicy:
    """Return the only policy the open-source bootstrap may activate.

    ``system.edition`` and other local configuration are deliberately absent
    from this boundary.  A future closed Cloud bootstrap must first verify its
    signed InstanceManifest and then explicitly construct the cloud policy.
    """

    return SingleWorkspacePolicy()
