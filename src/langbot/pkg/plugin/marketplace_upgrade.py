"""Operator-requested upgrade of Marketplace plugins across every Workspace.

Cloud tenants install official plugins from the Marketplace, but upgrades are
only offered per Workspace in the WebUI. When an operator lists plugins under
``plugin.marketplace_upgrade.plugins``, this sweep upgrades every installation
of those plugins that is behind the Marketplace's latest version, using the
same ``upgrade_plugin`` path as the WebUI.

Upgrading to a version without a permission declaration leaves the plugin
disabled until a member confirms. With ``confirm_permissions`` enabled, the
sweep confirms the declared permissions as an operator (owner role, the same
principal shape as a support-admin session) for installations that were
enabled before the sweep. Installations the tenant disabled stay disabled.
"""

from __future__ import annotations

import asyncio
import dataclasses
import json
import typing
import uuid

import httpx

from ..api.authz import permissions_for_role
from ..api.context import PrincipalContext, PrincipalType, RequestContext, WorkspaceContext

if typing.TYPE_CHECKING:
    from ..core.app import Application

OPERATOR_SESSION_ID = 'operator:marketplace-upgrade'
_METADATA_MAX_BYTES = 1024 * 1024


@dataclasses.dataclass(frozen=True, slots=True)
class MarketplaceUpgradeConfig:
    plugins: tuple[str, ...]
    concurrency: int = 2
    start_delay_seconds: float = 120.0
    confirm_permissions: bool = True
    # Optional canary allowlist; empty means every active Workspace.
    workspaces: tuple[str, ...] = ()

    @classmethod
    def from_instance_config(cls, data: dict) -> MarketplaceUpgradeConfig | None:
        section = (data.get('plugin') or {}).get('marketplace_upgrade') or {}
        if not isinstance(section, dict):
            return None
        raw = section.get('plugins') or []
        if isinstance(raw, str):
            raw = raw.split(',')
        plugins = tuple(dict.fromkeys(p.strip() for p in raw if isinstance(p, str) and p.strip().count('/') == 1))
        if not plugins:
            return None
        raw_workspaces = section.get('workspaces') or []
        if isinstance(raw_workspaces, str):
            raw_workspaces = raw_workspaces.split(',')
        workspaces = tuple(dict.fromkeys(w.strip() for w in raw_workspaces if isinstance(w, str) and w.strip()))
        return cls(
            plugins=plugins,
            concurrency=max(1, int(section.get('concurrency') or 2)),
            start_delay_seconds=max(0.0, float(section.get('start_delay_seconds') or 0)),
            confirm_permissions=bool(section.get('confirm_permissions', True)),
            workspaces=workspaces,
        )


def operator_request_context(binding: typing.Any) -> RequestContext:
    """Owner-level operator context for one Workspace."""

    return RequestContext(
        instance_uuid=str(binding.instance_uuid),
        placement_generation=int(binding.placement_generation),
        request_id=str(uuid.uuid4()),
        auth_type='operator',
        principal=PrincipalContext(
            principal_type=PrincipalType.SUPPORT_ADMIN,
            support_session_id=OPERATOR_SESSION_ID,
        ),
        workspace=WorkspaceContext(
            workspace_uuid=str(binding.workspace_uuid),
            membership_uuid=None,
            role='owner',
            permissions=permissions_for_role('owner'),
        ),
    )


async def fetch_latest_versions(space_url: str, plugin_ids: typing.Iterable[str]) -> dict[str, str]:
    latest: dict[str, str] = {}
    async with httpx.AsyncClient(trust_env=True, timeout=15) as client:
        for plugin_id in plugin_ids:
            response = await client.get(f'{space_url}/api/v1/marketplace/plugins/{plugin_id}')
            if response.status_code != 200 or len(response.content) > _METADATA_MAX_BYTES:
                continue
            try:
                version = response.json()['data']['plugin']['latest_version']
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
            if isinstance(version, str) and version:
                latest[plugin_id] = version
    return latest


class MarketplaceUpgradeSweep:
    def __init__(self, ap: Application, config: MarketplaceUpgradeConfig) -> None:
        self.ap = ap
        self.config = config
        self.summary: dict[str, int] = {
            'workspaces': 0,
            'upgraded': 0,
            'confirmed': 0,
            'up_to_date': 0,
            'failed': 0,
        }

    async def run(self) -> dict[str, int]:
        space_url = self.ap.instance_config.data.get('space', {}).get('url', 'https://space.langbot.app').rstrip('/')
        latest = await fetch_latest_versions(space_url, self.config.plugins)
        missing = sorted(set(self.config.plugins) - set(latest))
        if missing:
            self.ap.logger.warning(f'Marketplace upgrade: no Marketplace version for {", ".join(missing)}')
        if not latest:
            return self.summary
        bindings = await self.ap.workspace_service.list_active_execution_bindings()
        if self.config.workspaces:
            allowed = set(self.config.workspaces)
            bindings = [b for b in bindings if str(b.workspace_uuid) in allowed]
        self.summary['workspaces'] = len(bindings)
        self.ap.logger.info(
            f'Marketplace upgrade: checking {len(bindings)} Workspaces for '
            + ', '.join(f'{k}@{v}' for k, v in sorted(latest.items()))
        )
        semaphore = asyncio.Semaphore(self.config.concurrency)

        async def guarded(binding):
            async with semaphore:
                await self._sweep_workspace(binding, latest)

        # Each task gets its own copy of the connector's Workspace contextvar.
        await asyncio.gather(*(asyncio.create_task(guarded(b)) for b in bindings))
        self.ap.logger.info(f'Marketplace upgrade finished: {self.summary}')
        return self.summary

    async def _sweep_workspace(self, binding: typing.Any, latest: dict[str, str]) -> None:
        connector = self.ap.plugin_connector
        context = operator_request_context(binding)
        persistence_mgr = self.ap.persistence_mgr
        tenant_scope = getattr(persistence_mgr, 'tenant_scope', None)
        scope = tenant_scope(context.workspace_uuid) if callable(tenant_scope) else _null_scope()
        try:
            async with scope:
                _, settings = await connector._prepare_workspace_context(context)
                for setting in list(settings or ()):
                    plugin_id = f'{setting.plugin_author}/{setting.plugin_name}'
                    if plugin_id not in latest or setting.install_source != 'marketplace':
                        continue
                    await self._upgrade_one(context, setting, plugin_id, latest[plugin_id])
        except Exception as exc:
            self.summary['failed'] += 1
            self.ap.logger.warning(f'Marketplace upgrade: Workspace {context.workspace_uuid} skipped: {exc!r}')

    async def _upgrade_one(self, context: RequestContext, setting: typing.Any, plugin_id: str, version: str) -> None:
        from ..api.application.plugin_permissions import auto_confirm_declared, permission_status

        connector = self.ap.plugin_connector
        author, name = plugin_id.split('/', 1)
        was_enabled = bool(setting.enabled)
        installed = (setting.install_info or {}).get('plugin_version')
        try:
            if installed == version:
                self.summary['up_to_date'] += 1
            else:
                await connector.upgrade_plugin(author, name)
                self.summary['upgraded'] += 1
                self.ap.logger.info(
                    f'Marketplace upgrade: {context.workspace_uuid} {plugin_id} {installed} -> {version}'
                )
            if not (self.config.confirm_permissions and was_enabled):
                return
            _, current = await connector._setting_for_plugin(author, name)
            if current.enabled and not permission_status(self.ap, current)['pending_confirmation']:
                return
            await auto_confirm_declared(self.ap, context, current)
            self.summary['confirmed'] += 1
        except Exception as exc:
            self.summary['failed'] += 1
            self.ap.logger.warning(f'Marketplace upgrade: {context.workspace_uuid} {plugin_id} failed: {exc!r}')


class _null_scope:
    async def __aenter__(self):
        return None

    async def __aexit__(self, *exc):
        return False


async def run_configured_sweep(ap: Application) -> dict[str, int] | None:
    config = MarketplaceUpgradeConfig.from_instance_config(ap.instance_config.data)
    if config is None:
        return None
    if config.start_delay_seconds:
        await asyncio.sleep(config.start_delay_seconds)
    return await MarketplaceUpgradeSweep(ap, config).run()
