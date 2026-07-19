from __future__ import annotations

import dataclasses
import datetime
import hashlib
import secrets
import typing
import uuid

import sqlalchemy

from ....entity.persistence import apikey
from ....workspace.errors import WorkspaceNotFoundError
from ..authz import Permission, PermissionDeniedError
from .tenant import TenantContext, require_workspace_uuid, scope_statement

if typing.TYPE_CHECKING:
    from ....core.app import Application


@dataclasses.dataclass(frozen=True, slots=True)
class ApiKeyIdentity:
    """Trusted Workspace identity derived from an API-key secret."""

    instance_uuid: str
    workspace_uuid: str
    placement_generation: int
    api_key_uuid: str
    permissions: frozenset[str]


class ApiKeyService:
    """Manage hashed, Workspace-bound API keys."""

    def __init__(self, ap: Application) -> None:
        self.ap = ap

    @staticmethod
    def _hash_secret(secret: str) -> str:
        return hashlib.sha256(secret.encode('utf-8')).hexdigest()

    @staticmethod
    def _utcnow() -> datetime.datetime:
        return datetime.datetime.now(datetime.UTC).replace(tzinfo=None)

    @staticmethod
    def _normalize_scopes(
        scopes: typing.Iterable[str] | None,
        *,
        default: typing.Iterable[str] = (),
    ) -> list[str]:
        requested = list(default if scopes is None else scopes)
        valid = {permission.value for permission in Permission}
        normalized: list[str] = []
        for scope in requested:
            if not isinstance(scope, str):
                raise ValueError('API key scopes must be strings')
            value = scope.strip()
            if value not in valid:
                raise ValueError(f'Unknown API key scope: {value}')
            if value not in normalized:
                normalized.append(value)
        return normalized

    def _serialize(self, row: typing.Any) -> dict[str, typing.Any]:
        value = self.ap.persistence_mgr.serialize_model(apikey.ApiKey, row)
        value.pop('key_hash', None)
        # The secret is deliberately unrecoverable after creation.
        value['secret_available'] = False
        return value

    async def get_api_keys(self, context: TenantContext) -> list[dict[str, typing.Any]]:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(apikey.ApiKey).order_by(apikey.ApiKey.created_at, apikey.ApiKey.id),
                apikey.ApiKey,
                context,
            )
        )
        return [self._serialize(key) for key in result.all()]

    async def create_api_key(
        self,
        context: TenantContext,
        name: str,
        description: str = '',
        *,
        scopes: typing.Iterable[str] | None = None,
        expires_at: datetime.datetime | None = None,
    ) -> dict[str, typing.Any]:
        workspace_uuid = require_workspace_uuid(context)
        normalized_name = name.strip()
        if not normalized_name:
            raise ValueError('Name is required')
        if expires_at is not None:
            if expires_at.tzinfo is not None:
                expires_at = expires_at.astimezone(datetime.UTC).replace(tzinfo=None)
            if expires_at <= self._utcnow():
                raise ValueError('API key expiry must be in the future')

        default_scopes = getattr(getattr(context, 'workspace', None), 'permissions', frozenset())
        normalized_scopes = self._normalize_scopes(scopes, default=default_scopes)
        allowed_scopes = frozenset(default_scopes)
        unauthorized_scopes = sorted(set(normalized_scopes) - allowed_scopes)
        if unauthorized_scopes:
            # API-key management delegates the caller's authority; it must not
            # become a path for minting a stronger principal.
            raise PermissionDeniedError(unauthorized_scopes[0])
        secret = f'lbk_{secrets.token_urlsafe(32)}'
        key_uuid = str(uuid.uuid4())
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(apikey.ApiKey).values(
                uuid=key_uuid,
                workspace_uuid=workspace_uuid,
                created_by_account_uuid=getattr(context, 'account_uuid', None),
                name=normalized_name,
                key_hash=self._hash_secret(secret),
                scopes=normalized_scopes,
                status=apikey.ApiKeyStatus.ACTIVE.value,
                expires_at=expires_at,
                description=description.strip(),
            )
        )
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(apikey.ApiKey).where(apikey.ApiKey.uuid == key_uuid),
                apikey.ApiKey,
                workspace_uuid,
            )
        )
        created = result.first()
        if created is None:
            raise RuntimeError('Created API key could not be loaded')
        value = self._serialize(created)
        value['key'] = secret
        value['secret_available'] = True
        return value

    async def get_api_key(self, context: TenantContext, key_id: int) -> dict[str, typing.Any] | None:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.select(apikey.ApiKey).where(apikey.ApiKey.id == key_id),
                apikey.ApiKey,
                context,
            )
        )
        key = result.first()
        return None if key is None else self._serialize(key)

    async def authenticate_api_key(self, secret: str) -> ApiKeyIdentity | None:
        """Authenticate a secret and derive its Workspace without trusting headers."""

        if not isinstance(secret, str) or not secret.strip():
            return None

        global_secret = self.ap.instance_config.data.get('api', {}).get('global_api_key', '')
        if global_secret and secrets.compare_digest(secret, global_secret):
            workspace_service = getattr(self.ap, 'workspace_service', None)
            if workspace_service is None or workspace_service.policy.multi_workspace_enabled:
                return None
            binding = await workspace_service.get_local_execution_binding()
            return ApiKeyIdentity(
                instance_uuid=binding.instance_uuid,
                workspace_uuid=binding.workspace_uuid,
                placement_generation=binding.placement_generation,
                api_key_uuid='global-oss-api-key',
                permissions=frozenset(permission.value for permission in Permission),
            )

        if not secret.startswith('lbk_'):
            return None
        secret_hash = self._hash_secret(secret)
        current_session = getattr(self.ap.persistence_mgr, 'current_session', lambda: None)
        discovery_uow = getattr(self.ap.persistence_mgr, 'api_key_discovery_uow', None)
        if current_session() is None and callable(discovery_uow):
            async with discovery_uow(secret_hash) as discovery:
                key = await discovery.session.scalar(
                    sqlalchemy.select(apikey.ApiKey).where(apikey.ApiKey.key_hash == secret_hash)
                )
        else:
            result = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.select(apikey.ApiKey).where(apikey.ApiKey.key_hash == secret_hash)
            )
            key = result.first()
        if key is None:
            return None
        discovered_workspace_uuid = key.workspace_uuid
        discovered_key_id = key.id
        now = self._utcnow()

        async def bind_and_record_use() -> tuple[typing.Any, typing.Any] | None:
            # Re-read inside the tenant transaction. A revoke/expiry racing
            # discovery must not result in an authenticated identity.
            active_session = current_session()
            if active_session is not None:
                scoped_key = await active_session.scalar(
                    sqlalchemy.select(apikey.ApiKey).where(
                        apikey.ApiKey.id == discovered_key_id,
                        apikey.ApiKey.workspace_uuid == discovered_workspace_uuid,
                        apikey.ApiKey.key_hash == secret_hash,
                    )
                )
            else:  # compatibility for isolated service tests
                scoped_result = await self.ap.persistence_mgr.execute_async(
                    sqlalchemy.select(apikey.ApiKey).where(
                        apikey.ApiKey.id == discovered_key_id,
                        apikey.ApiKey.workspace_uuid == discovered_workspace_uuid,
                        apikey.ApiKey.key_hash == secret_hash,
                    )
                )
                scoped_key = scoped_result.first()
            if scoped_key is None or scoped_key.status != apikey.ApiKeyStatus.ACTIVE.value:
                return None
            if scoped_key.expires_at is not None and scoped_key.expires_at <= now:
                return None

            binding = await self.ap.workspace_service.get_execution_binding(discovered_workspace_uuid)
            updated = await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(apikey.ApiKey)
                .where(
                    apikey.ApiKey.id == scoped_key.id,
                    apikey.ApiKey.workspace_uuid == discovered_workspace_uuid,
                    apikey.ApiKey.key_hash == secret_hash,
                    apikey.ApiKey.status == apikey.ApiKeyStatus.ACTIVE.value,
                )
                .values(last_used_at=now)
                .returning(apikey.ApiKey.id)
            )
            # Authentication and revocation race on this atomic predicate. If
            # revoke won, no active row is returned and the stale object read
            # above must never become an authenticated identity.
            if updated.scalar_one_or_none() is None:
                return None
            return binding, scoped_key

        tenant_uow = getattr(self.ap.persistence_mgr, 'tenant_uow', None)
        if current_session() is None and callable(tenant_uow):
            async with tenant_uow(discovered_workspace_uuid):
                bound = await bind_and_record_use()
        else:
            bound = await bind_and_record_use()
        if bound is None:
            return None
        binding, scoped_key = bound
        raw_scopes = list(scoped_key.scopes or [])
        permissions = (
            frozenset(permission.value for permission in Permission)
            if '*' in raw_scopes
            else frozenset(self._normalize_scopes(raw_scopes))
        )
        return ApiKeyIdentity(
            instance_uuid=binding.instance_uuid,
            workspace_uuid=binding.workspace_uuid,
            placement_generation=binding.placement_generation,
            api_key_uuid=scoped_key.uuid,
            permissions=permissions,
        )

    async def verify_api_key(self, secret: str) -> bool:
        try:
            return await self.authenticate_api_key(secret) is not None
        except Exception:
            return False

    async def delete_api_key(self, context: TenantContext, key_id: int) -> None:
        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(apikey.ApiKey)
                .where(apikey.ApiKey.id == key_id)
                .values(status=apikey.ApiKeyStatus.REVOKED.value),
                apikey.ApiKey,
                context,
            )
        )
        if getattr(result, 'rowcount', 0) == 0:
            raise WorkspaceNotFoundError('API key not found')

    async def update_api_key(
        self,
        context: TenantContext,
        key_id: int,
        name: str | None = None,
        description: str | None = None,
    ) -> None:
        update_data: dict[str, typing.Any] = {}
        if name is not None:
            normalized_name = name.strip()
            if not normalized_name:
                raise ValueError('Name is required')
            update_data['name'] = normalized_name
        if description is not None:
            update_data['description'] = description.strip()
        if not update_data:
            return

        result = await self.ap.persistence_mgr.execute_async(
            scope_statement(
                sqlalchemy.update(apikey.ApiKey).where(apikey.ApiKey.id == key_id).values(**update_data),
                apikey.ApiKey,
                context,
            )
        )
        if getattr(result, 'rowcount', 0) == 0:
            raise WorkspaceNotFoundError('API key not found')
