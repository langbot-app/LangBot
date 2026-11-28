"""Matching Docker/Cloud status avoids unrelated probes while keeping readiness and placement fences."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.box import errors as sdk_box_errors
from langbot_plugin.box.models import SandboxAdmissionPolicy
from langbot_plugin.box.runtime import BoxRuntime
from langbot_plugin.box.errors import BoxValidationError
from langbot_plugin.skill_store import SkillStore

from langbot.pkg.box import settings
from langbot.pkg.box.service import BoxService
from tests.unit_tests.box.test_box_service import _CONTEXT, FakeBackend, _InProcessBoxRuntimeClient, make_app


def status_service(monkeypatch, selected, backend, mode='network', *, cloud_managed=False):
    if mode == 'network' and (
        not hasattr(sdk_box_errors, 'BoxArtifactNotPreparedError')
        or not callable(getattr(SkillStore, 'list_publication_manifest_resources', None))
    ):
        pytest.skip('requires network Skill execution capabilities from the in-tree SDK')
    get_settings_mock = AsyncMock(
        return_value={'backend': selected, 'e2b': None, 'limits': {'config': {'max_sessions': 2}}}
    )
    monkeypatch.setattr(settings, 'get_settings', get_settings_mock)
    client = Mock()
    client.get_status = AsyncMock(
        return_value={
            'backend': backend,
            'active_sessions': 1,
            'capacity': {'limit': 5, 'used': 1, 'remaining': 4},
        }
    )
    app = make_app(Mock(), enabled=True)
    app.instance_config.data['box']['file_transfer_mode'] = mode
    service = BoxService(app, client=client)
    service._available = True
    if cloud_managed:
        service._cloud_managed = True
        service._admission_policy = SandboxAdmissionPolicy(required_backend='nsjail')
        service._require_validated_workspace_sandbox = AsyncMock()
    service._validated_execution_context = AsyncMock(return_value=_CONTEXT)
    service.get_workspace_backend_settings = AsyncMock(
        return_value={
            'backends': [{'name': selected, 'available': False, 'reason': 'readiness_failed'}],
        }
    )
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['legacy', 'network'])
@pytest.mark.parametrize('available', [True, False])
async def test_matching_docker_uses_fresh_status_without_unrelated_probes(monkeypatch, mode, available):
    backend = {'name': 'docker', 'available': available}
    service = status_service(monkeypatch, 'docker', backend, mode=mode)
    result = await service.get_status(_CONTEXT)
    assert result['available'] is available
    assert result['backend'] == backend
    assert result['capacity'] == {'limit': 2, 'used': 1, 'remaining': 1}
    service.get_workspace_backend_settings.assert_not_awaited()
    assert service._validated_execution_context.await_count == 2
    assert settings.get_settings.await_count == 1
    if not available:
        assert 'Configured sandbox backend "docker" is unavailable' in result['connector_error']
    logged = [call.args[0] for call in service.ap.logger.info.call_args_list]
    assert any('box_status_timing ' in line and 'probe_mode=matched_runtime' in line for line in logged)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['legacy', 'network'])
async def test_matching_docker_still_rejects_post_rpc_placement_cutover(monkeypatch, mode):
    service = status_service(monkeypatch, 'docker', {'name': 'docker', 'available': True}, mode=mode)
    service._validated_execution_context.side_effect = [_CONTEXT, BoxValidationError('stale placement')]
    with pytest.raises(BoxValidationError, match='stale placement'):
        await service.get_status(_CONTEXT)
    service.get_workspace_backend_settings.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['legacy', 'network'])
@pytest.mark.parametrize(
    'selected,backend',
    [
        ('e2b', {'name': 'e2b', 'available': True}),
        ('nsjail', {'name': 'nsjail', 'available': True}),
        ('docker', {'name': 'host', 'available': True}),
        ('docker', {'name': 'docker', 'available': 'truthy-not-bool'}),
        ('docker', None),
        ('docker', 'invalid status'),
        ('unknown-backend', {'name': 'docker', 'available': True}),
    ],
)
async def test_overrides_and_other_backends_retain_full_readiness_checks(monkeypatch, selected, backend, mode):
    service = status_service(monkeypatch, selected, backend, mode=mode)
    result = await service.get_status(_CONTEXT)
    assert result['available'] is False
    assert result['backend'] == {'name': selected, 'available': False, 'reason': 'readiness_failed'}
    service.get_workspace_backend_settings.assert_awaited_once_with(_CONTEXT)
    assert settings.get_settings.await_count == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('available', [True, False])
async def test_cloud_managed_reuses_required_backend_and_blocks_disallowed_without_enumeration(monkeypatch, available):
    service = status_service(
        monkeypatch, 'nsjail', {'name': 'nsjail', 'available': available}, mode='network', cloud_managed=True
    )
    result = await service.get_status(_CONTEXT)
    assert result['available'] is available
    assert result['backend'] == {'name': 'nsjail', 'available': available}
    service.get_workspace_backend_settings.assert_not_awaited()
    assert service._validated_execution_context.await_count == 2

    disallowed = status_service(
        monkeypatch, 'docker', {'name': 'nsjail', 'available': True}, mode='network', cloud_managed=True
    )
    disallowed_result = await disallowed.get_status(_CONTEXT)
    assert disallowed_result['available'] is False
    assert disallowed_result['backend'] == {'name': 'docker', 'available': False, 'reason': 'policy_restricted'}
    disallowed.get_workspace_backend_settings.assert_not_awaited()
    assert disallowed._validated_execution_context.await_count == 2


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['legacy', 'network'])
async def test_default_multi_backend_runtime_never_probes_unused_nsjail_for_docker_status(monkeypatch, tmp_path, mode):
    if mode == 'network' and (
        not hasattr(sdk_box_errors, 'BoxArtifactNotPreparedError')
        or not callable(getattr(SkillStore, 'list_publication_manifest_resources', None))
    ):
        pytest.skip('requires network Skill execution capabilities from the in-tree SDK')

    logger = Mock()
    docker = FakeBackend(logger, available=True)
    docker.name = 'docker'
    nsjail = FakeBackend(logger, available=False)
    nsjail.name = 'nsjail'
    nsjail_probes = 0

    async def slow_nsjail_probe():
        nonlocal nsjail_probes
        nsjail_probes += 1
        return False

    nsjail.probe_available = slow_nsjail_probe
    runtime = BoxRuntime(logger=logger, backends=[docker, nsjail], session_ttl_sec=0, data_dir=tmp_path / 'identity')
    runtime._box_config = {'backend': 'docker'}

    class RuntimeClient(_InProcessBoxRuntimeClient):
        async def get_backends(self, *, refresh=False, **options):
            return await self._runtime.get_backends(refresh=refresh)

    app = make_app(logger, [str(tmp_path)], host_root=str(tmp_path), enabled=True)
    app.instance_config.data['box']['file_transfer_mode'] = mode
    service = BoxService(app, client=RuntimeClient(logger, runtime))
    await service.initialize()

    selected_state = {'backend': 'docker', 'e2b': None, 'limits': None}
    monkeypatch.setattr(settings, 'get_settings', AsyncMock(side_effect=lambda *args, **kwargs: dict(selected_state)))

    healthy = await service.get_status(_CONTEXT)
    assert healthy['available'] is True
    assert healthy['backend'] == {'name': 'docker', 'available': True}
    assert nsjail_probes == 0
    assert service._runtime_backend_info == {'name': 'docker', 'available': True}

    # Live daemon outage is reported immediately and invalidates cached runtime backend info.
    docker.available = False
    degraded = await service.get_status(_CONTEXT)
    assert degraded['available'] is False
    assert degraded['backend'] == {'name': 'docker', 'available': False}
    assert 'Configured sandbox backend "docker" is unavailable' in degraded['connector_error']
    assert nsjail_probes == 0
    assert service._runtime_backend_info is None

    # Explicit nsjail selection still performs full readiness probe and fails cleanly.
    selected_state['backend'] = 'nsjail'
    nsjail_status = await service.get_status(_CONTEXT)
    assert nsjail_status['available'] is False
    assert nsjail_status['backend']['name'] == 'nsjail'
    assert 'Configured sandbox backend "nsjail" is unavailable' in nsjail_status['connector_error']
    assert nsjail_probes == 1


@pytest.mark.asyncio
async def test_managed_process_capability_cache_reuses_valid_entries_and_invalidates_on_reconnect():
    logger = Mock()
    client = Mock()
    client.initialize = AsyncMock()
    client.get_backends = AsyncMock(
        side_effect=[
            [
                {'name': 'docker', 'available': True, 'managed_processes': True},
                {'name': 'e2b', 'available': False, 'managed_processes': False},
                {'name': 'nsjail', 'available': False, 'reason': 'probe_timeout'},
            ],
            [
                {'name': 'docker', 'available': True, 'managed_processes': True},
                {'name': 'nsjail', 'available': True, 'managed_processes': True},
            ],
            [
                {'name': 'docker', 'available': True, 'managed_processes': False},
            ],
        ]
    )
    service = BoxService(make_app(logger, enabled=True), client=client)
    await service.initialize()

    assert await service.backend_supports_managed_processes('docker') is True
    assert await service.backend_supports_managed_processes('docker') is True
    assert await service.backend_supports_managed_processes('e2b') is False
    assert client.get_backends.await_count == 1

    # Transient probe timeout omitted managed_processes; must not poison the cache as False.
    assert await service.backend_supports_managed_processes('nsjail') is True
    assert client.get_backends.await_count == 2

    # Re-initializing clears the per-connection cache so new Runtime capabilities are observed.
    await service.initialize()
    assert await service.backend_supports_managed_processes('docker') is False
    assert client.get_backends.await_count == 3


@pytest.mark.asyncio
async def test_set_backend_reads_existing_settings_once_when_updating_e2b_and_limits(monkeypatch):
    read_mock = AsyncMock(return_value={'backend': 'e2b', 'e2b': None, 'limits': None})
    monkeypatch.setattr(settings, 'get_settings', read_mock)
    executed = []

    class DummyUow:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def execute(self, statement):
            executed.append(statement)

    ap = SimpleNamespace(
        persistence_mgr=SimpleNamespace(
            tenant_uow=lambda workspace_uuid: DummyUow(),
            get_db_engine=lambda: SimpleNamespace(dialect=SimpleNamespace(name='sqlite')),
        )
    )
    await settings.set_backend(
        ap,
        'ws-1',
        'e2b',
        e2b_config={'api_url': 'https://e2b.example', 'api_key': 'secret'},
        limits={'max_sessions': 2},
    )
    assert read_mock.await_count == 1
    assert len(executed) == 3
