from __future__ import annotations

import dataclasses
import enum


class PrincipalType(enum.StrEnum):
    """Kinds of authenticated principals accepted by LangBot."""

    ACCOUNT = 'account'
    API_KEY = 'api_key'
    SYSTEM = 'system'
    PUBLIC_BOT = 'public_bot'


@dataclasses.dataclass(frozen=True, slots=True)
class PrincipalContext:
    """Authenticated identity before Workspace authorization is applied."""

    principal_type: PrincipalType
    account_uuid: str | None = None
    api_key_uuid: str | None = None


@dataclasses.dataclass(frozen=True, slots=True)
class WorkspaceContext:
    """Workspace membership and effective permissions for one request."""

    workspace_uuid: str
    membership_uuid: str | None
    role: str | None
    permissions: frozenset[str]
    membership_revision: int = 0


@dataclasses.dataclass(frozen=True, slots=True)
class RequestContext:
    """Trusted authorization context passed to HTTP services."""

    instance_uuid: str
    placement_generation: int
    request_id: str
    auth_type: str
    principal: PrincipalContext
    workspace: WorkspaceContext
    entitlement_revision: int = 0

    @property
    def workspace_uuid(self) -> str:
        """Return the selected Workspace UUID."""

        return self.workspace.workspace_uuid

    @property
    def account_uuid(self) -> str | None:
        """Return the Account UUID when the principal is an Account."""

        return self.principal.account_uuid


@dataclasses.dataclass(frozen=True, slots=True)
class ExecutionContext:
    """Workspace context propagated to asynchronous and runtime work."""

    instance_uuid: str
    workspace_uuid: str
    placement_generation: int
    bot_uuid: str | None = None
    pipeline_uuid: str | None = None
    query_uuid: str | None = None
    trigger_principal: PrincipalContext | None = None

    @classmethod
    def from_request(
        cls,
        ctx: RequestContext,
        *,
        bot_uuid: str | None = None,
        pipeline_uuid: str | None = None,
        query_uuid: str | None = None,
    ) -> ExecutionContext:
        """Create a runtime context without losing the tenant generation."""

        return cls(
            instance_uuid=ctx.instance_uuid,
            workspace_uuid=ctx.workspace_uuid,
            placement_generation=ctx.placement_generation,
            bot_uuid=bot_uuid,
            pipeline_uuid=pipeline_uuid,
            query_uuid=query_uuid,
            trigger_principal=ctx.principal,
        )
