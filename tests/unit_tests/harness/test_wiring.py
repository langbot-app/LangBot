"""The WebSocket route stays dead unless startup installs its dependencies."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.harness import wiring
from langbot.pkg.harness.crypto.transport import HarnessTransportFactory
from langbot.pkg.utils import constants


def _ap(**overrides):
    config = overrides.pop(
        'config',
        {
            'harness': {
                'enabled': True,
                'instance_origin': 'https://bot.example.test',
                'client_origin': 'https://client.example.test',
            },
            'system': {'jwt': {'secret': 'secret'}},
        },
    )
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data=config),
        deployment=SimpleNamespace(mode='oss'),
        persistence_mgr=SimpleNamespace(get_db_engine=lambda: None),
        logger=SimpleNamespace(warning=lambda *a: None),
    )
    ap.__dict__.update(overrides)
    return ap


@pytest.fixture(autouse=True)
def instance_identity(monkeypatch):
    monkeypatch.setattr(constants, 'instance_id', 'instance')


@pytest.mark.asyncio
async def test_install_attaches_route_dependencies(monkeypatch):
    """install() is what turns the route's 1013 into a real handshake."""
    ap = _ap()
    ensure = AsyncMock(return_value='harness-initial-v1')
    monkeypatch.setattr(wiring.HarnessBindings, 'ensure_instance_key', ensure)

    await wiring.install(ap)

    assert isinstance(ap.harness_transport_factory, HarnessTransportFactory)
    # The default account/OAuth handshake is the client contract.
    assert not hasattr(ap, 'harness_context_resolver')
    ensure.assert_awaited_once()


@pytest.mark.asyncio
async def test_install_survives_disabled_harness(monkeypatch):
    """Disabling Harness also disables the WebSocket transport."""
    ap = _ap(config={'harness': {'enabled': False}, 'system': {'jwt': {'secret': 'secret'}}})
    ensure = AsyncMock(return_value=None)
    monkeypatch.setattr(wiring.HarnessBindings, 'ensure_instance_key', ensure)

    await wiring.install(ap)

    assert not hasattr(ap, 'harness_transport_factory')
    ensure.assert_not_awaited()


@pytest.mark.asyncio
async def test_identity_failure_does_not_abort_startup(monkeypatch):
    """Startup must not depend on the database being reachable for Harness."""
    ap = _ap()
    monkeypatch.setattr(wiring.HarnessBindings, 'ensure_instance_key', AsyncMock(side_effect=RuntimeError('db down')))

    await wiring.install(ap)

    assert isinstance(ap.harness_transport_factory, HarnessTransportFactory)


@pytest.mark.asyncio
async def test_client_key_lookup_reads_enrolled_device(monkeypatch):
    """The factory resolves pinned keys through the OAuth device store."""
    lookup = AsyncMock(return_value={'x25519_pub': 'x', 'ed25519_pub': 'e'})
    monkeypatch.setattr(wiring.HarnessOAuthService, 'lookup_device', lookup)

    result = await wiring._client_key_lookup(_ap(), 'harness-id', 'device-kid')

    assert result == {'x25519_pub': 'x', 'ed25519_pub': 'e'}
    lookup.assert_awaited_once_with('harness-id', 'device-kid')
