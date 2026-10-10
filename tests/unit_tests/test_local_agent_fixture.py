"""Provisioning failures must not turn the required LocalAgent CI job green."""

from __future__ import annotations

import hashlib
import importlib.util
import io
from pathlib import Path
import json
from unittest.mock import Mock
import zipfile

import httpx
import pytest

from tests.e2e import test_local_runner_fake_provider as local_agent_e2e


@pytest.fixture
def provisioner():
    script = Path(__file__).resolve().parents[2] / 'scripts/test-local-agent-fixture.py'
    spec = importlib.util.spec_from_file_location('local_agent_fixture_provisioner', script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def package_and_lock():
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, 'w') as archive:
        archive.writestr('manifest.yaml', 'metadata:\n  author: langbot-team\n  name: LocalAgent\n  version: 0.2.1\n')
        archive.comment = b'preserve-certification-envelope'
    package = buffer.getvalue()
    return package, {
        'author': 'langbot-team',
        'name': 'LocalAgent',
        'version': '0.2.1',
        'url': 'https://space.langbot.app/test-fixture',
        'sha256': hashlib.sha256(package).hexdigest(),
    }


def test_verified_cached_package_needs_no_network(provisioner, package_and_lock, tmp_path, monkeypatch):
    package, lock = package_and_lock
    destination = tmp_path / 'LocalAgent.lbpkg'
    destination.write_bytes(package)
    download = Mock(side_effect=AssertionError('Verified cache should not access Space'))
    monkeypatch.setattr(provisioner, 'download_package', download)

    assert provisioner.fetch_package(destination, lock) == destination
    assert destination.read_bytes() == package
    download.assert_not_called()


def test_invalid_cache_is_replaced_without_repacking(provisioner, package_and_lock, tmp_path, monkeypatch):
    package, lock = package_and_lock
    destination = tmp_path / 'LocalAgent.lbpkg'
    destination.write_bytes(b'corrupt cache')
    monkeypatch.setattr(provisioner, 'download_package', lambda url: package)

    provisioner.fetch_package(destination, lock)

    assert destination.read_bytes() == package
    assert not destination.with_suffix('.tmp').exists()


def test_download_checksum_mismatch_does_not_install(provisioner, package_and_lock, tmp_path, monkeypatch):
    _, lock = package_and_lock
    destination = tmp_path / 'LocalAgent.lbpkg'
    monkeypatch.setattr(provisioner, 'download_package', lambda url: b'wrong artifact')

    with pytest.raises(ValueError, match='SHA256 mismatch'):
        provisioner.fetch_package(destination, lock)

    assert not destination.exists()


def test_manifest_identity_must_match_lock(provisioner, package_and_lock):
    package, lock = package_and_lock
    lock['version'] = 'different-version'

    with pytest.raises(ValueError, match='manifest version'):
        provisioner.validate_package(package, lock)


def test_space_unavailable_fails_after_bounded_retries(provisioner, package_and_lock, tmp_path, monkeypatch):
    _, lock = package_and_lock
    download = Mock(side_effect=httpx.ConnectError('unavailable'))
    monkeypatch.setattr(provisioner.httpx, 'stream', download)
    monkeypatch.setattr(provisioner.time, 'sleep', lambda seconds: None)

    with pytest.raises(RuntimeError, match='Cannot fetch LocalAgent fixture from Space'):
        provisioner.fetch_package(tmp_path / 'LocalAgent.lbpkg', lock)

    assert download.call_count == 3


def test_explicit_package_preserves_signed_archive(package_and_lock, tmp_path, monkeypatch):
    package, _ = package_and_lock
    source = tmp_path / 'download.lbpkg'
    source.write_bytes(package)
    monkeypatch.setenv('LANGBOT_E2E_LOCAL_AGENT_PACKAGE', str(source))

    staged = local_agent_e2e._package_local_agent_plugin(tmp_path)

    assert staged.read_bytes() == package


def test_required_job_cannot_fall_back_to_sibling_or_skip(tmp_path, monkeypatch):
    monkeypatch.delenv('LANGBOT_E2E_LOCAL_AGENT_PACKAGE', raising=False)
    monkeypatch.setenv('LANGBOT_E2E_REQUIRE_LOCAL_AGENT', '1')

    with pytest.raises(pytest.fail.Exception, match='requires LANGBOT_E2E_LOCAL_AGENT_PACKAGE'):
        local_agent_e2e._package_local_agent_plugin(tmp_path)


def test_explicit_missing_package_fails_even_for_optional_run(tmp_path, monkeypatch):
    monkeypatch.setenv('LANGBOT_E2E_LOCAL_AGENT_PACKAGE', str(tmp_path / 'missing.lbpkg'))
    monkeypatch.delenv('LANGBOT_E2E_REQUIRE_LOCAL_AGENT', raising=False)

    with pytest.raises(pytest.fail.Exception, match='Explicit LocalAgent package does not exist'):
        local_agent_e2e._package_local_agent_plugin(tmp_path)


def test_optional_local_run_can_skip_missing_fixture(tmp_path, monkeypatch):
    monkeypatch.delenv('LANGBOT_E2E_LOCAL_AGENT_PACKAGE', raising=False)
    monkeypatch.delenv('LANGBOT_E2E_REQUIRE_LOCAL_AGENT', raising=False)
    monkeypatch.setattr(local_agent_e2e, '_local_agent_repo', lambda: tmp_path / 'missing-source')

    with pytest.raises(pytest.skip.Exception, match='Optional LocalAgent fixture unavailable'):
        local_agent_e2e._package_local_agent_plugin(tmp_path)


def test_resolution_uses_space_order_and_refreshes_every_time(provisioner, monkeypatch):
    versions = [
        {'version': '0.3.0', 'checksum': 'a' * 64, 'plugin_id': 'langbot-team/LocalAgent', 'status': 'live'},
        {'version': '0.2.1', 'checksum': 'b' * 64, 'plugin_id': 'langbot-team/LocalAgent', 'status': 'live'},
    ]
    payload = {'code': 0, 'data': {'versions': versions}}
    download = Mock(return_value=json.dumps(payload).encode())
    monkeypatch.setattr(provisioner, 'download_package', download)

    first = provisioner.resolve_latest()
    versions[0]['version'] = '0.4.0'
    versions[0]['checksum'] = 'c' * 64
    download.return_value = json.dumps(payload).encode()
    second = provisioner.resolve_latest()

    assert first['version'] == '0.3.0'
    assert first['sha256'] == 'a' * 64
    assert second['version'] == '0.4.0'
    assert second['sha256'] == 'c' * 64
    assert second['url'].endswith('/langbot-team/LocalAgent/0.4.0')
    assert download.call_count == 2


@pytest.mark.parametrize(
    'field,value',
    [
        ('version', '../bad'),
        ('checksum', ''),
        ('plugin_id', 'other/LocalAgent'),
        ('status', 'removed'),
    ],
)
def test_resolution_rejects_unusable_latest_instead_of_using_old_release(provisioner, monkeypatch, field, value):
    latest = {'version': '0.3.0', 'checksum': 'a' * 64, 'plugin_id': 'langbot-team/LocalAgent', 'status': 'live'}
    latest[field] = value
    payload = json.dumps({'code': 0, 'data': {'versions': [latest]}}).encode()
    monkeypatch.setattr(provisioner, 'download_package', lambda *args, **kwargs: payload)

    with pytest.raises(ValueError):
        provisioner.resolve_latest()


def test_download_rejects_oversized_body(provisioner, monkeypatch):
    response = httpx.Response(200, content=b'oversized', request=httpx.Request('GET', 'https://space.langbot.app'))
    from contextlib import nullcontext

    monkeypatch.setattr(provisioner.httpx, 'stream', lambda *args, **kwargs: nullcontext(response))

    with pytest.raises(ValueError, match='exceeds'):
        provisioner.download_package('https://space.langbot.app', max_bytes=3)
