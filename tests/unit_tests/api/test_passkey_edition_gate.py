"""Passkey gating (OSS-only) and server-side WebAuthn origin resolution.

Regression coverage for LANG-145:
- WebAuthn RP ID / origin must come from server config, never from the request,
  otherwise a sibling host can obtain a valid assertion for a victim credential.
- Passkeys are an OSS-only feature: every passkey route must refuse on a cloud
  deployment (multi-tenant Cloud or standalone cloud edition).
"""

from types import SimpleNamespace

import pytest

from langbot.pkg.api.http.controller.groups import user as user_module
from langbot.pkg.api.http.controller.groups.user import UserRouterGroup
from langbot.pkg.utils import constants


def _router(instance_config=None, deployment_mode=None):
    """Build just enough of the router group to call its helpers."""
    group = UserRouterGroup.__new__(UserRouterGroup)
    group.ap = SimpleNamespace(
        instance_config=SimpleNamespace(data=instance_config or {}),
        deployment=SimpleNamespace(mode=deployment_mode) if deployment_mode else None,
    )
    return group


def test_origin_and_rp_id_come_from_server_config(monkeypatch):
    monkeypatch.setattr(constants, 'edition', 'community')
    group = _router({'api': {'webui_url': 'https://bot.langbot.app', 'webhook_prefix': 'https://example.test'}})

    origin, rp_id = group._resolve_server_origin()

    assert origin == 'https://bot.langbot.app'
    assert rp_id == 'bot.langbot.app'


def test_origin_falls_back_to_webhook_prefix(monkeypatch):
    monkeypatch.setattr(constants, 'edition', 'community')
    group = _router({'api': {'webui_url': '', 'webhook_prefix': 'https://bot2.langbot.app'}})

    origin, rp_id = group._resolve_server_origin()

    assert origin == 'https://bot2.langbot.app'
    assert rp_id == 'bot2.langbot.app'


def test_origin_never_uses_loopback_of_attacker_supplied_host(monkeypatch):
    """With nothing configured the RP falls back to loopback, not the request."""
    monkeypatch.setattr(constants, 'edition', 'community')
    group = _router({'api': {'webui_url': '', 'webhook_prefix': '', 'port': 5300}})

    origin, rp_id = group._resolve_server_origin()

    assert origin == 'http://127.0.0.1:5300'
    assert rp_id == 'localhost'


def test_client_supplied_origin_helper_no_longer_exists():
    """The request-derived helper must be gone, not merely unused."""
    assert not hasattr(UserRouterGroup, '_extract_origin_and_rp_id')


@pytest.mark.parametrize(
    'edition,deployment_mode,expected',
    [
        ('community', None, True),
        ('oss', None, True),
        ('community', 'oss', True),
        ('cloud', None, False),
        ('community', 'cloud', False),
        ('cloud', 'cloud', False),
    ],
)
def test_passkey_supported_only_on_oss(monkeypatch, edition, deployment_mode, expected):
    monkeypatch.setattr(constants, 'edition', edition)
    group = _router(deployment_mode=deployment_mode)

    assert group._passkey_supported() is expected


def test_refusal_builds_only_when_unsupported(monkeypatch):
    """The denial path is taken on cloud and skipped on OSS.

    ``_passkey_disabled_response`` builds a Quart response, which needs an app
    context, so the decision itself is asserted here through the gate that
    drives it; the wiring of every route to that denial is covered below.
    """
    monkeypatch.setattr(constants, 'edition', 'cloud')
    assert _router()._passkey_supported() is False

    monkeypatch.setattr(constants, 'edition', 'community')
    assert _router()._passkey_supported() is True


def test_every_passkey_route_is_gated():
    """Guards against a new passkey route being added without the edition gate."""
    import inspect

    source = inspect.getsource(user_module)
    passkey_routes = source.count("@self.route('/passkey")
    assert passkey_routes >= 7, f'expected at least 7 passkey routes, found {passkey_routes}'
    assert source.count('_passkey_disabled_response()') >= passkey_routes
