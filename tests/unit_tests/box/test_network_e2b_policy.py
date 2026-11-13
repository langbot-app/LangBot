"""Keep network E2B file ownership independent of host workspace mirrors."""

from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.box.client import ActionRPCBoxClient, BoxRuntimeClient
from langbot_plugin.box.errors import BoxValidationError
from langbot_plugin.box.models import BoxExecutionResult, BoxExecutionStatus, BoxHostMountMode
from langbot.pkg.box.runner import RunBoxBinding
from langbot.pkg.box.service import BoxService
from tests.unit_tests.box.test_box_service import _CONTEXT, make_app, make_query

pytestmark = pytest.mark.skipif(
    not callable(getattr(ActionRPCBoxClient, 'upload_file', None)),
    reason='requires the in-tree or released Box network file-transfer SDK',
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
    skill = tmp_path / 'skill'
    skill.mkdir()
    mounts = [{'host_path': str(skill), 'mount_path': '/opt/pinned-skill', 'mode': 'ro'}]

    async def create(spec, *, action_context):
        return {'session_id': spec.session_id}

    client.create_session = AsyncMock(side_effect=create)
    created = await service.create_session(
        _CONTEXT,
        {'session_id': 'network-e2b'},
        selected_backend='e2b',
        selected_e2b_config={},
        selected_limits={},
        trusted_read_only_mounts=mounts,
    )
    initial = client.create_session.await_args.args[0]
    query = make_query()
    object.__setattr__(
        query,
        '_box_binding',
        RunBoxBinding('network-run', created['session_id'], {'backend': 'e2b'}, 'network-run', read_only_mounts=mounts),
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
        assert len(spec.extra_mounts) == 1
        assert spec.extra_mounts[0].host_path == str(skill)
        assert spec.extra_mounts[0].mode is BoxHostMountMode.READ_ONLY
    assert initial.session_id == executed.session_id


@pytest.mark.parametrize(
    'mode,backend',
    [('legacy', 'e2b'), ('network', 'docker'), ('network', 'nsjail')],
)
def test_other_backends_and_legacy_keep_workspace_mount(tmp_path, mode, backend):
    service, _ = make_service(tmp_path, mode)
    spec = service.build_spec({'session_id': 'existing', 'backend': backend})
    assert spec.host_path == str(tmp_path / 'default')
    assert spec.host_path_mode is BoxHostMountMode.READ_WRITE


def test_network_e2b_does_not_replace_cloud_policy_mount(tmp_path):
    service, _ = make_service(tmp_path, 'network')
    service._cloud_managed = True
    spec = service.build_spec({'session_id': 'global', 'backend': 'e2b'})
    assert spec.host_path == str(tmp_path / 'default')
    assert spec.host_path_mode is BoxHostMountMode.READ_WRITE


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
