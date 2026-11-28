from __future__ import annotations

import contextvars
import types
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from langbot.pkg.api.context import PrincipalType
from langbot.pkg.plugin import marketplace_upgrade as mu

WS = ['ws-1', 'ws-2']


def setting(ws, name='LocalAgent', version='0.2.4', enabled=True, source='marketplace', author='langbot-team'):
    return types.SimpleNamespace(
        workspace_uuid=ws,
        plugin_author=author,
        plugin_name=name,
        install_source=source,
        install_info={'plugin_version': version},
        enabled=enabled,
        permission_declaration=None,
        permission_snapshot=None,
    )


class FakeConnector:
    def __init__(self, per_ws):
        self.per_ws = per_ws
        self.current = contextvars.ContextVar('ws', default=None)
        self.upgraded: list[tuple[str, str]] = []
        self.after_upgrade: dict[tuple[str, str], object] = {}

    async def _prepare_workspace_context(self, context):
        self.current.set(context.workspace_uuid)
        return None, self.per_ws[context.workspace_uuid]

    async def upgrade_plugin(self, author, name):
        self.upgraded.append((self.current.get(), f'{author}/{name}'))

    async def _setting_for_plugin(self, author, name):
        ws = self.current.get()
        return None, self.after_upgrade.get((ws, name)) or setting(ws, name, enabled=False)


def make_ap(per_ws, plugins=('langbot-team/LocalAgent',), confirm=True):
    ap = MagicMock()
    ap.instance_config.data = {
        'space': {'url': 'https://space.example'},
        'plugin': {'marketplace_upgrade': {'plugins': list(plugins), 'confirm_permissions': confirm}},
    }
    ap.plugin_connector = FakeConnector(per_ws)
    ap.workspace_service.list_active_execution_bindings = AsyncMock(
        return_value=[
            types.SimpleNamespace(instance_uuid='inst', workspace_uuid=ws, placement_generation=1) for ws in per_ws
        ]
    )
    ap.persistence_mgr = types.SimpleNamespace()  # no tenant_scope: OSS-style null scope
    return ap


@pytest.fixture(autouse=True)
def no_retry_delay(monkeypatch):
    monkeypatch.setattr(mu.MarketplaceUpgradeSweep, 'RETRY_DELAYS_SECONDS', (0.0, 0.0))


def pending_unless_snapshot(ap, s):
    return {'pending_confirmation': s.permission_snapshot is None}


def config(ap):
    return mu.MarketplaceUpgradeConfig.from_instance_config(ap.instance_config.data)


def test_config_disabled_without_plugins():
    assert (
        mu.MarketplaceUpgradeConfig.from_instance_config({'plugin': {'marketplace_upgrade': {'plugins': []}}}) is None
    )
    assert mu.MarketplaceUpgradeConfig.from_instance_config({}) is None


def test_config_accepts_comma_string_and_drops_invalid_ids():
    cfg = mu.MarketplaceUpgradeConfig.from_instance_config(
        {'plugin': {'marketplace_upgrade': {'plugins': 'a/B, bad , a/B,c/D', 'concurrency': -3}}}
    )
    assert cfg.plugins == ('a/B', 'c/D')
    assert cfg.concurrency == 1


def test_operator_context_is_owner_support_admin():
    ctx = mu.operator_request_context(
        types.SimpleNamespace(instance_uuid='i', workspace_uuid='w', placement_generation=3)
    )
    assert ctx.principal.principal_type is PrincipalType.SUPPORT_ADMIN
    assert ctx.principal.support_session_id == mu.OPERATOR_SESSION_ID
    assert ctx.workspace.role == 'owner'
    assert ctx.workspace_uuid == 'w' and ctx.placement_generation == 3


async def test_upgrades_outdated_and_confirms_pending():
    ap = make_ap(
        {
            'ws-1': [setting('ws-1'), setting('ws-1', name='Other', author='someone')],
            'ws-2': [setting('ws-2', version='0.2.8')],
        }
    )
    confirm = AsyncMock()
    with (
        patch.object(mu, 'fetch_latest_versions', AsyncMock(return_value={'langbot-team/LocalAgent': '0.2.8'})),
        patch('langbot.pkg.api.application.plugin_permissions.auto_confirm_declared', confirm),
        patch(
            'langbot.pkg.api.application.plugin_permissions.permission_status',
            lambda ap, s: {'pending_confirmation': not s.enabled},
        ),
    ):
        summary = await mu.MarketplaceUpgradeSweep(ap, config(ap)).run()

    assert ap.plugin_connector.upgraded == [('ws-1', 'langbot-team/LocalAgent')]
    assert summary['upgraded'] == 1 and summary['up_to_date'] == 1 and summary['failed'] == 0
    # Both current settings are reported disabled and pending by the fake, so
    # each is confirmed in its own Workspace context.
    assert summary['confirmed'] == 2
    assert sorted(call.args[1].workspace_uuid for call in confirm.await_args_list) == WS


async def test_tenant_disabled_install_is_upgraded_but_not_enabled():
    ap = make_ap({'ws-1': [setting('ws-1', enabled=False)]})
    switched_off = setting('ws-1', enabled=False)
    switched_off.permission_snapshot = {'workspace_operations': [], 'capabilities': []}
    ap.plugin_connector.after_upgrade[('ws-1', 'LocalAgent')] = switched_off
    confirm = AsyncMock()
    with (
        patch.object(mu, 'fetch_latest_versions', AsyncMock(return_value={'langbot-team/LocalAgent': '0.2.8'})),
        patch('langbot.pkg.api.application.plugin_permissions.auto_confirm_declared', confirm),
        patch('langbot.pkg.api.application.plugin_permissions.permission_status', pending_unless_snapshot),
    ):
        summary = await mu.MarketplaceUpgradeSweep(ap, config(ap)).run()
    assert summary['upgraded'] == 1
    confirm.assert_not_awaited()


async def test_up_to_date_install_left_pending_is_confirmed_on_rerun():
    # A previous run upgraded the install but its confirmation failed, leaving
    # it disabled and pending; the next run confirms it.
    ap = make_ap({'ws-1': [setting('ws-1', version='0.2.8', enabled=False)]})
    confirm = AsyncMock()
    with (
        patch.object(mu, 'fetch_latest_versions', AsyncMock(return_value={'langbot-team/LocalAgent': '0.2.8'})),
        patch('langbot.pkg.api.application.plugin_permissions.auto_confirm_declared', confirm),
        patch('langbot.pkg.api.application.plugin_permissions.permission_status', pending_unless_snapshot),
    ):
        summary = await mu.MarketplaceUpgradeSweep(ap, config(ap)).run()
    assert ap.plugin_connector.upgraded == []
    assert summary['up_to_date'] == 1 and summary['confirmed'] == 1
    confirm.assert_awaited_once()


async def test_transient_failures_are_retried():
    ap = make_ap({'ws-1': [setting('ws-1')]})
    original = ap.plugin_connector.upgrade_plugin
    attempts = []

    async def flaky(author, name):
        attempts.append(1)
        if len(attempts) < 3:
            raise RuntimeError('Blocking executor capacity reached')
        await original(author, name)

    ap.plugin_connector.upgrade_plugin = flaky
    confirm = AsyncMock(side_effect=[RuntimeError('dns'), None])
    with (
        patch.object(mu, 'fetch_latest_versions', AsyncMock(return_value={'langbot-team/LocalAgent': '0.2.8'})),
        patch('langbot.pkg.api.application.plugin_permissions.auto_confirm_declared', confirm),
        patch('langbot.pkg.api.application.plugin_permissions.permission_status', pending_unless_snapshot),
    ):
        summary = await mu.MarketplaceUpgradeSweep(ap, config(ap)).run()
    assert len(attempts) == 3
    assert confirm.await_count == 2
    assert summary == {'workspaces': 1, 'upgraded': 1, 'confirmed': 1, 'up_to_date': 0, 'failed': 0}


async def test_confirmation_can_be_turned_off():
    ap = make_ap({'ws-1': [setting('ws-1')]}, confirm=False)
    confirm = AsyncMock()
    with (
        patch.object(mu, 'fetch_latest_versions', AsyncMock(return_value={'langbot-team/LocalAgent': '0.2.8'})),
        patch('langbot.pkg.api.application.plugin_permissions.auto_confirm_declared', confirm),
    ):
        await mu.MarketplaceUpgradeSweep(ap, config(ap)).run()
    confirm.assert_not_awaited()


async def test_failure_in_one_install_does_not_stop_others():
    ap = make_ap({'ws-1': [setting('ws-1')], 'ws-2': [setting('ws-2')]})
    original = ap.plugin_connector.upgrade_plugin

    async def flaky(author, name):
        if ap.plugin_connector.current.get() == 'ws-1':
            raise RuntimeError('runtime busy')
        await original(author, name)

    ap.plugin_connector.upgrade_plugin = flaky
    with (
        patch.object(mu, 'fetch_latest_versions', AsyncMock(return_value={'langbot-team/LocalAgent': '0.2.8'})),
        patch('langbot.pkg.api.application.plugin_permissions.auto_confirm_declared', AsyncMock()),
        patch(
            'langbot.pkg.api.application.plugin_permissions.permission_status',
            lambda ap, s: {'pending_confirmation': True},
        ),
    ):
        summary = await mu.MarketplaceUpgradeSweep(ap, config(ap)).run()
    assert summary['failed'] == 1
    assert ap.plugin_connector.upgraded == [('ws-2', 'langbot-team/LocalAgent')]


async def test_no_marketplace_versions_skips_workspaces():
    ap = make_ap({'ws-1': [setting('ws-1')]})
    with patch.object(mu, 'fetch_latest_versions', AsyncMock(return_value={})):
        summary = await mu.MarketplaceUpgradeSweep(ap, config(ap)).run()
    assert summary['workspaces'] == 0
    ap.workspace_service.list_active_execution_bindings.assert_not_awaited()


@pytest.mark.parametrize('plugins', [[], None])
async def test_run_configured_sweep_noop_when_unconfigured(plugins):
    ap = MagicMock()
    ap.instance_config.data = {'plugin': {'marketplace_upgrade': {'plugins': plugins}}}
    assert await mu.run_configured_sweep(ap) is None


async def test_workspace_allowlist_limits_the_sweep():
    ap = make_ap({'ws-1': [setting('ws-1')], 'ws-2': [setting('ws-2')]})
    ap.instance_config.data['plugin']['marketplace_upgrade']['workspaces'] = 'ws-2'
    with (
        patch.object(mu, 'fetch_latest_versions', AsyncMock(return_value={'langbot-team/LocalAgent': '0.2.8'})),
        patch('langbot.pkg.api.application.plugin_permissions.auto_confirm_declared', AsyncMock()),
    ):
        summary = await mu.MarketplaceUpgradeSweep(ap, config(ap)).run()
    assert summary['workspaces'] == 1
    assert ap.plugin_connector.upgraded == [('ws-2', 'langbot-team/LocalAgent')]


async def test_whole_sweep_is_retried_when_startup_is_saturated(monkeypatch):
    monkeypatch.setattr(mu, 'RUN_RETRY_DELAYS_SECONDS', (0.0, 0.0))
    ap = make_ap({'ws-1': [setting('ws-1')]})
    ap.instance_config.data['plugin']['marketplace_upgrade']['start_delay_seconds'] = 0
    fetch = AsyncMock(
        side_effect=[RuntimeError('Blocking executor capacity reached'), {'langbot-team/LocalAgent': '0.2.8'}]
    )
    with (
        patch.object(mu, 'fetch_latest_versions', fetch),
        patch('langbot.pkg.api.application.plugin_permissions.auto_confirm_declared', AsyncMock()),
    ):
        summary = await mu.run_configured_sweep(ap)
    assert fetch.await_count == 2
    assert summary['upgraded'] == 1


async def test_sweep_gives_up_after_all_retries(monkeypatch):
    monkeypatch.setattr(mu, 'RUN_RETRY_DELAYS_SECONDS', (0.0,))
    ap = make_ap({'ws-1': [setting('ws-1')]})
    ap.instance_config.data['plugin']['marketplace_upgrade']['start_delay_seconds'] = 0
    fetch = AsyncMock(side_effect=RuntimeError('dns'))
    with patch.object(mu, 'fetch_latest_versions', fetch), pytest.raises(RuntimeError):
        await mu.run_configured_sweep(ap)
    assert fetch.await_count == 2
