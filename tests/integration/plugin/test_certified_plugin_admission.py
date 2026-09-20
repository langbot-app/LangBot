"""Certified archive admission through the public Core installation API."""

from __future__ import annotations

import base64
import hashlib
import io
import zipfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
import yaml
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from langbot.pkg.api.http.context import ExecutionContext
from langbot.pkg.plugin.connector import PluginRuntimeConnector
from langbot_plugin.entities.io.context import InstallationBinding
from langbot_plugin.runtime.plugin.mgr import PluginInstallSource


pytestmark = pytest.mark.integration


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('deployment', 'archive_kind', 'administrator_force', 'expected_profile'),
    [
        ('cloud', 'signed_shared', False, 'shared-runtime-v1'),
        ('oss', 'signed_shared', False, 'shared-runtime-v1'),
        ('oss', 'legacy', False, 'dedicated'),
        ('oss', 'invalid_shared', True, 'dedicated'),
    ],
)
async def test_install_plugin_admits_archive_before_persistence_and_applies_selected_profile(
    deployment: str,
    archive_kind: str,
    administrator_force: bool,
    expected_profile: str,
) -> None:
    package, trusted_public_keys = _archive(archive_kind)
    connector, execution_context, binding = _connector(deployment, trusted_public_keys)

    await connector.install_plugin(
        PluginInstallSource.LOCAL,
        {
            'plugin_file': package,
            'administrator_force': administrator_force,
        },
    )

    connector._store_artifact_package.assert_awaited_once_with(
        execution_context,
        hashlib.sha256(package).hexdigest(),
        package,
    )
    persisted_info = connector._persist_installation_package.await_args.kwargs['install_info']
    assert persisted_info['_certification']['runtime_profile'] == expected_profile
    assert persisted_info['_certification']['normalized_digest'] == _normalized_digest(package)
    connector.handler.apply_plugin_installation.assert_awaited_once_with(
        binding,
        artifact_package=package,
        enabled=True,
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('archive_kind', ['legacy', 'invalid_shared'])
async def test_cloud_rejects_untrusted_archive_before_storage_persistence_or_runtime_apply(archive_kind: str) -> None:
    package, trusted_public_keys = _archive(archive_kind)
    connector, _execution_context, _binding = _connector('cloud', trusted_public_keys)

    with pytest.raises(ValueError, match='CERTIFIED_PLUGIN_CLOUD_CERTIFICATE_'):
        await connector.install_plugin(PluginInstallSource.LOCAL, {'plugin_file': package})

    connector._store_artifact_package.assert_not_awaited()
    connector._persist_installation_package.assert_not_awaited()
    connector.handler.apply_plugin_installation.assert_not_awaited()


@pytest.mark.asyncio
async def test_oss_requires_explicit_administrator_force_for_declared_invalid_archive() -> None:
    package, trusted_public_keys = _archive('invalid_shared')
    connector, _execution_context, _binding = _connector('oss', trusted_public_keys)

    with pytest.raises(ValueError, match='CERTIFIED_PLUGIN_OSS_FORCE_REQUIRED'):
        await connector.install_plugin(PluginInstallSource.LOCAL, {'plugin_file': package})

    connector._store_artifact_package.assert_not_awaited()
    connector._persist_installation_package.assert_not_awaited()
    connector.handler.apply_plugin_installation.assert_not_awaited()


def _connector(deployment: str, trusted_public_keys: dict[str, str]):
    package_digest = 'a' * 64
    execution_context = ExecutionContext(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
    )
    binding = InstallationBinding(
        instance_uuid='instance-a',
        workspace_uuid='workspace-a',
        placement_generation=1,
        installation_uuid='00000000-0000-4000-8000-000000000001',
        runtime_revision=1,
        artifact_digest=package_digest,
    )
    app = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'plugin': {
                    'enable': True,
                    'certification': {'trusted_public_keys': trusted_public_keys},
                }
            }
        ),
        deployment=SimpleNamespace(mode=deployment),
        logger=Mock(),
    )
    connector = PluginRuntimeConnector(app, AsyncMock())
    connector.handler = SimpleNamespace(
        register_installation_binding=Mock(),
        apply_plugin_installation=AsyncMock(return_value={'state': 'running'}),
    )
    connector._current_execution_context = AsyncMock(return_value=execution_context)
    connector._store_artifact_package = AsyncMock()
    connector._persist_installation_package = AsyncMock(return_value=(binding, None, False))
    connector._wait_for_installed_plugin_ready = AsyncMock()
    return connector, execution_context, binding


def _archive(kind: str) -> tuple[bytes, dict[str, str]]:
    manifest = {
        'metadata': {'author': 'certified', 'name': 'example', 'version': '1.0.0'},
        'execution': {'sharedRuntime': 'shared-runtime-v1'},
    }
    if kind == 'legacy':
        manifest.pop('execution')
    archive = io.BytesIO()
    with zipfile.ZipFile(archive, 'w') as package:
        package.writestr('manifest.yaml', yaml.safe_dump(manifest))
    raw_archive = archive.getvalue()
    if kind == 'legacy':
        return raw_archive, {}

    from langbot_plugin.certification import create_envelope, write_envelope

    signing_key = Ed25519PrivateKey.generate()
    signed_archive = write_envelope(
        raw_archive,
        create_envelope(
            raw_archive,
            'wrong-key' if kind == 'invalid_shared' else 'ephemeral',
            signing_key.sign,
        ),
    )
    trusted_key = signing_key.public_key().public_bytes(
        serialization.Encoding.Raw,
        serialization.PublicFormat.Raw,
    )
    return signed_archive, {'ephemeral': base64.b64encode(trusted_key).decode('ascii')}


def _normalized_digest(archive: bytes) -> str:
    from langbot_plugin.certification import normalized_zip_digest

    return normalized_zip_digest(archive)
