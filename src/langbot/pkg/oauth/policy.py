"""Live Workspace, scope and Harness-binding authorization for OAuth."""

import sqlalchemy as sa

from ..api.authz import permissions_for_role
from ..entity.persistence.harness_oauth import HarnessDevice
from ..entity.persistence.harness_registration import HarnessBinding, HarnessRegistrationLink
from .entities import OAuthClient

SCOPE_PERMISSIONS = {
    'workspace.view': 'workspace.view',
    'resource.view': 'resource.view',
    'resource.manage': 'resource.manage',
    'member.view': 'member.view',
    'agent.run': 'runtime.operate',
}


class OAuthPolicy:
    def __init__(self, ap):
        self.ap = ap
        self.engine = ap.persistence_mgr.get_db_engine()

    async def pending_device(self, binding_id: str, device_id: str, instance_uuid: str) -> bool:
        async with self.engine.connect() as conn:
            return bool(
                await conn.scalar(
                    sa.select(HarnessDevice.id)
                    .join(HarnessRegistrationLink, HarnessRegistrationLink.id == HarnessDevice.binding_id)
                    .where(
                        HarnessDevice.id == device_id,
                        HarnessDevice.binding_id == binding_id,
                        HarnessDevice.revoked_at.is_(None),
                        HarnessRegistrationLink.instance_uuid == instance_uuid,
                        HarnessRegistrationLink.consumed_at.is_not(None),
                        HarnessRegistrationLink.revoked_at.is_(None),
                    )
                )
            )

    async def live_device_binding(
        self, binding_id: str, device_id: str, instance_uuid: str, client_id: str | None = None
    ) -> bool:
        async with self.engine.connect() as conn:
            active = bool(
                await conn.scalar(
                    sa.select(HarnessDevice.id)
                    .join(HarnessBinding, HarnessBinding.id == HarnessDevice.binding_id)
                    .where(
                        HarnessBinding.id == binding_id,
                        HarnessBinding.instance_uuid == instance_uuid,
                        HarnessBinding.revoked_at.is_(None),
                        HarnessDevice.id == device_id,
                        HarnessDevice.revoked_at.is_(None),
                    )
                )
            )
            if not active or client_id is None:
                return active
            return bool(
                await conn.scalar(
                    sa.select(OAuthClient.id).where(
                        OAuthClient.id == client_id,
                        OAuthClient.binding_id == binding_id,
                        OAuthClient.device_id == device_id,
                        OAuthClient.revoked_at.is_(None),
                    )
                )
            )

    async def effective_permissions(
        self,
        account_uuid: str,
        workspace_uuid: str,
        scopes: list[str],
        binding_id: str,
        device_id: str,
        instance_uuid: str,
        client_id: str | None = None,
    ) -> frozenset[str]:
        """Intersect live active membership permissions, token scopes and binding."""
        if not await self.live_device_binding(binding_id, device_id, instance_uuid, client_id):
            return frozenset()
        try:
            access = await self.ap.workspace_collaboration_service.resolve_account_workspace(
                account_uuid, workspace_uuid
            )
        except Exception:
            return frozenset()
        if access.execution.instance_uuid != instance_uuid:
            return frozenset()
        role_permissions = permissions_for_role(access.membership.role)
        return frozenset(
            permission
            for scope in scopes
            if (permission := SCOPE_PERMISSIONS.get(scope)) is not None and permission in role_permissions
        )
