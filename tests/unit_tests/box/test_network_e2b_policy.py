"""Keep network E2B file ownership independent of host workspace mirrors."""

from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.box.client import ActionRPCBoxClient, BoxRuntimeClient
from langbot_plugin.box.errors import BoxAdmissionError, BoxValidationError
from langbot_plugin.box.models import BoxExecutionResult, BoxExecutionStatus, BoxHostMountMode
from langbot.pkg.box.runner import RunBoxBinding
from langbot.pkg.box.service import BoxService
from tests.unit_tests.box.test_box_service import _CONTEXT, make_app, make_query

pytestmark = pytest.mark.skipif(
    any(not callable(getattr(ActionRPCBoxClient, name, None)) for name in ('prepare_artifact', 'cleanup_run_files')),
    reason='requires the in-tree or released Box network workspace APIs',
)


def make_service(tmp_path, mode):
    app = make_app(Mock(), [str(tmp_path)], host_root=str(tmp_path))
    app.instance_config.data['box']['file_transfer_mode'] = mode
    client = Mock(spec=BoxRuntimeClient)
    service = BoxService(app, client=client)
    service._available = True
    return service, client


@pytest.mark.asyncio
async def test_network_e2b_create_and_bound_execution_disable_only_writable_mirror(tmp_path):
    service, client = make_service(tmp_path, 'network')

    async def create(spec, *, action_context):
        return {'session_id': spec.session_id}

    client.create_session = AsyncMock(side_effect=create)
    created = await service.create_session(
        _CONTEXT,
        {'session_id': 'network-e2b'},
        selected_backend='e2b',
        selected_e2b_config={},
        selected_limits={},
    )
    initial = client.create_session.await_args.args[0]
    query = make_query()
    object.__setattr__(
        query,
        '_box_binding',
        RunBoxBinding('network-run', created['session_id'], {'backend': 'e2b'}, 'network-run'),
    )
    client.execute = AsyncMock(
        return_value=BoxExecutionResult(
            session_id=created['session_id'],
            backend_name='e2b',
            status=BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout='ok',
            stderr='',
            duration_ms=1,
        )
    )
    result = await service.execute_tool({'command': 'true'}, query)
    assert result['ok']
    executed = client.execute.await_args.args[0]
    for spec in (initial, executed):
        assert spec.host_path is None
        assert spec.host_path_mode is BoxHostMountMode.NONE
        assert spec.backend == 'e2b'
        assert not spec.extra_mounts
    assert initial.session_id == executed.session_id


@pytest.mark.parametrize(
    'mode,backend',
    [('legacy', 'e2b'), ('network', 'docker'), ('network', 'nsjail')],
)
def test_network_defers_workspace_to_runtime_and_legacy_keeps_mount(tmp_path, mode, backend):
    service, _ = make_service(tmp_path, mode)
    spec = service.build_spec({'session_id': 'existing', 'backend': backend})
    assert spec.host_path == (str(tmp_path / 'default') if mode == 'legacy' else None)
    assert spec.host_path_mode is BoxHostMountMode.READ_WRITE


def test_network_cloud_policy_does_not_require_a_core_workspace_mount(tmp_path):
    service, _ = make_service(tmp_path, 'network')
    service._cloud_managed = True
    spec = service.build_spec({'session_id': 'global', 'backend': 'e2b'})
    assert spec.host_path is None
    assert spec.host_path_mode is BoxHostMountMode.READ_WRITE


@pytest.mark.asyncio
@pytest.mark.parametrize('mount_field', ['host_path', 'extra_mounts', 'trusted_read_only_mounts'])
async def test_network_rejects_host_filesystem_mounts(tmp_path, mount_field):
    service, client = make_service(tmp_path, 'network')
    payload = {'session_id': 'network-e2b'}
    kwargs = {}
    mounts = [{'host_path': str(tmp_path), 'mount_path': '/workspace/package', 'mode': 'ro'}]
    if mount_field == 'trusted_read_only_mounts':
        kwargs[mount_field] = mounts
    else:
        payload[mount_field] = str(tmp_path) if mount_field == 'host_path' else mounts
    with pytest.raises(BoxAdmissionError, match='require legacy'):
        await service.create_session(
            _CONTEXT, payload, selected_backend='e2b', selected_e2b_config={}, selected_limits={}, **kwargs
        )
    client.create_session.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.parametrize('readonly', ['explicit', 'profile'])
async def test_network_export_rejects_readonly_workspace_before_transfer(tmp_path, readonly):
    service, client = make_service(tmp_path, 'network')
    query = make_query()
    if readonly == 'profile':
        service.ap.instance_config.data['box']['local']['profile'] = 'offline_readonly'
        service.profile = service._load_profile()
    else:
        query._box_binding.spec['host_path_mode'] = 'ro'
    with pytest.raises(BoxValidationError, match='requires a writable workspace'):
        await service.collect_selected_files(query, ['/tmp/private-output.bin'])
    client.execute.assert_not_called()
    client.download_file.assert_not_called()
    assert not query._box_binding.exported
