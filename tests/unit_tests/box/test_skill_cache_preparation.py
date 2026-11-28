import hashlib
import asyncio
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.box import models
from langbot_plugin.box import errors as sdk_errors
from langbot_plugin.box.errors import BoxAdmissionError, BoxError, BoxValidationError
from langbot.pkg.box.service import BoxService
from tests.unit_tests.box.test_box_service import _CONTEXT, make_app, make_query


def service(tmp_path, mode='legacy'):
    app = make_app(Mock(), [str(tmp_path)], host_root=str(tmp_path))
    app.instance_config.data['box']['file_transfer_mode'] = mode
    client = SimpleNamespace(
        prepare_artifact=AsyncMock(), cleanup_run_files=AsyncMock(), upload_file=AsyncMock(), download_file=AsyncMock()
    )
    result = BoxService(app, client=client)
    result._available = True
    app.box_service = result
    return result, client


@pytest.mark.parametrize('managed', [False, True])
def test_user_execution_cannot_select_cached_artifacts(tmp_path, managed):
    box, _ = service(tmp_path)
    box._cloud_managed = managed
    with pytest.raises(BoxAdmissionError, match='composed by the Host'):
        box._managed_policy_payload(_CONTEXT, {'artifact_mounts': [{'content_digest': 'sha256:' + 'a' * 64}]})


def test_network_mode_rejects_an_sdk_without_the_preflight_contract(tmp_path, monkeypatch):
    monkeypatch.delattr(sdk_errors, 'BoxArtifactNotPreparedError', raising=False)
    with pytest.raises(BoxValidationError, match='updated Core and Box SDK'):
        service(tmp_path, 'network')


def test_network_mode_rejects_an_sdk_without_manifest_listing(tmp_path, monkeypatch):
    from langbot_plugin.skill_store import SkillStore

    monkeypatch.delattr(SkillStore, 'list_publication_manifest_resources', raising=False)
    with pytest.raises(BoxValidationError, match='updated Core and Box SDK'):
        service(tmp_path, 'network')


@pytest.mark.asyncio
async def test_stale_placement_cannot_prepare_or_read_a_package(tmp_path):
    box, client = service(tmp_path)
    box.ap.skill_repository = SimpleNamespace(get_skill_package=AsyncMock())
    box.ap.workspace_service.get_execution_binding = AsyncMock(
        return_value=SimpleNamespace(instance_uuid='foreign-instance')
    )
    with pytest.raises(BoxValidationError, match='another LangBot instance'):
        await box.prepare_skill_artifact(_CONTEXT, 'private', 'sha256:' + 'a' * 64)
    box.ap.skill_repository.get_skill_package.assert_not_called()
    client.prepare_artifact.assert_not_called()


@pytest.mark.asyncio
@pytest.mark.skipif(not hasattr(models, 'BoxArtifactDescriptor'), reason='requires Runtime artifact-cache SDK')
@pytest.mark.parametrize('valid_receipt', [True, False])
async def test_prepare_reads_the_authoritative_pin_and_validates_receipt(tmp_path, valid_receipt):
    box, client = service(tmp_path)
    manifest = {'algorithm': 'sha256-tree-v1', 'files': [], 'total_bytes': 0}
    revision = (
        'sha256:'
        + hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()
        ).hexdigest()
    )
    content = b'archive bytes are verified by Runtime'
    package = {
        'content': content,
        'revision': revision,
        'manifest': manifest,
        'size': len(content),
        'sha256': hashlib.sha256(content).hexdigest(),
    }
    box.ap.skill_repository = SimpleNamespace(get_skill_package=AsyncMock(return_value=package))
    receipt = {
        'ready': True,
        'content_digest': revision,
        'mount_path': '/opt/langbot-artifacts/' + (revision[7:] if valid_receipt else 'b' * 64),
    }
    client.prepare_artifact.return_value = receipt
    if valid_receipt:
        assert await box.prepare_skill_artifact(_CONTEXT, 'pinned', revision) == receipt
        await box.prepare_skill_artifact(_CONTEXT, 'pinned', revision)
        assert box.ap.skill_repository.get_skill_package.await_count == 2
    else:
        with pytest.raises(BoxValidationError, match='receipt does not match'):
            await box.prepare_skill_artifact(_CONTEXT, 'pinned', revision)
    box.ap.skill_repository.get_skill_package.assert_awaited_with(_CONTEXT, 'pinned', revision, metadata_only=True)
    descriptor, transferred = client.prepare_artifact.await_args.args
    assert descriptor.content_digest == revision
    assert descriptor.manifest == manifest
    assert transferred == content
    assert client.prepare_artifact.await_args.kwargs['action_context'].workspace_uuid == _CONTEXT.workspace_uuid


def package_and_receipt():
    manifest = {'algorithm': 'sha256-tree-v1', 'files': [], 'total_bytes': 0}
    revision = (
        'sha256:'
        + hashlib.sha256(
            json.dumps(manifest, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()
        ).hexdigest()
    )
    content = b'archive bytes'
    package = {
        'revision': revision,
        'manifest': manifest,
        'content': content,
        'size': len(content),
        'sha256': hashlib.sha256(content).hexdigest(),
    }
    receipt = {'ready': True, 'content_digest': revision, 'mount_path': '/opt/langbot-artifacts/' + revision[7:]}
    return package, receipt


@pytest.mark.asyncio
async def test_warm_artifact_hit_never_reads_the_archive(tmp_path):
    box, client = service(tmp_path)
    package, receipt = package_and_receipt()
    metadata = {key: value for key, value in package.items() if key != 'content'}
    box.ap.skill_repository = SimpleNamespace(get_skill_package=AsyncMock(return_value=metadata))
    client.prepare_artifact.return_value = receipt
    assert await box.prepare_skill_artifact(_CONTEXT, 'pinned', package['revision']) == receipt
    box.ap.skill_repository.get_skill_package.assert_awaited_once_with(
        _CONTEXT, 'pinned', package['revision'], metadata_only=True
    )
    assert client.prepare_artifact.await_args.args[1] is None


@pytest.mark.asyncio
async def test_artifact_miss_reads_and_transfers_the_same_pinned_archive(tmp_path):
    box, client = service(tmp_path)
    package, receipt = package_and_receipt()
    metadata = {key: value for key, value in package.items() if key != 'content'}
    box.ap.skill_repository = SimpleNamespace(get_skill_package=AsyncMock(side_effect=[metadata, package]))
    client.prepare_artifact.side_effect = [{**receipt, 'ready': False}, receipt]
    assert await box.prepare_skill_artifact(_CONTEXT, 'pinned', package['revision']) == receipt
    calls = box.ap.skill_repository.get_skill_package.await_args_list
    assert calls[0].kwargs == {'metadata_only': True}
    assert calls[1].args == (_CONTEXT, 'pinned', package['revision']) and not calls[1].kwargs
    first, second = client.prepare_artifact.await_args_list
    assert first.args[1] is None and second.args[1] == package['content']
    assert first.args[0] == second.args[0]


@pytest.mark.asyncio
@pytest.mark.parametrize('changed', ['revision', 'manifest', 'size', 'sha256'])
async def test_artifact_miss_rejects_changed_publication_metadata(tmp_path, changed):
    box, client = service(tmp_path)
    package, receipt = package_and_receipt()
    metadata = {key: value for key, value in package.items() if key != 'content'}
    different = {
        'revision': 'sha256:' + '0' * 64,
        'manifest': {**package['manifest'], 'total_bytes': 1},
        'size': package['size'] + 1,
        'sha256': '0' * 64,
    }
    box.ap.skill_repository = SimpleNamespace(
        get_skill_package=AsyncMock(side_effect=[metadata, {**package, changed: different[changed]}])
    )
    client.prepare_artifact.return_value = {**receipt, 'ready': False}
    with pytest.raises(BoxValidationError, match='metadata changed'):
        await box.prepare_skill_artifact(_CONTEXT, 'pinned', package['revision'])
    client.prepare_artifact.assert_awaited_once()


@pytest.mark.asyncio
async def test_warm_artifact_hit_still_revalidates_the_generation(tmp_path):
    box, client = service(tmp_path)
    package, receipt = package_and_receipt()
    metadata = {key: value for key, value in package.items() if key != 'content'}
    box.ap.skill_repository = SimpleNamespace(get_skill_package=AsyncMock(return_value=metadata))
    box._validated_execution_context = AsyncMock(side_effect=[_CONTEXT, BoxValidationError('stale placement')])
    client.prepare_artifact.return_value = receipt
    with pytest.raises(BoxValidationError, match='stale placement'):
        await box.prepare_skill_artifact(_CONTEXT, 'pinned', package['revision'])
    client.prepare_artifact.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.skipif(
    not hasattr(sdk_errors, 'BoxArtifactNotPreparedError'), reason='requires the in-tree artifact preflight protocol'
)
@pytest.mark.parametrize('scenario', ['warm', 'cold', 'still-missing', 'backend-error', 'timeout', 'cancel'])
async def test_only_preexecution_cache_misses_can_retry_and_commands_are_never_replayed(tmp_path, scenario):
    from langbot_plugin.box.errors import BoxArtifactNotPreparedError
    from langbot.pkg.provider.tools.loaders.skill import register_activated_skill

    box, client = service(tmp_path, 'network')
    package, receipt = package_and_receipt()
    box.ap.skill_repository = SimpleNamespace(get_skill_package=AsyncMock(return_value=package))
    client.prepare_artifact.return_value = receipt
    query = make_query()
    register_activated_skill(query, {'name': 'pinned', 'revision': package['revision']})
    marker = tmp_path / 'command-side-effects'
    requests = 0

    async def execute(spec, *, action_context):
        nonlocal requests
        requests += 1
        assert [mount.content_digest for mount in spec.artifact_mounts] == [package['revision']]
        assert action_context.workspace_uuid == _CONTEXT.workspace_uuid
        if scenario == 'still-missing' or (scenario == 'cold' and requests == 1):
            raise BoxArtifactNotPreparedError('package not prepared before execution')
        with marker.open('a') as stream:
            stream.write('command executed\n')
        if scenario == 'backend-error':
            raise BoxError('executed command mentioned BoxArtifactNotPreparedError: do not replay')
        if scenario == 'cancel':
            raise asyncio.CancelledError
        return models.BoxExecutionResult(
            session_id=spec.session_id,
            backend_name='fake',
            status=models.BoxExecutionStatus.TIMED_OUT
            if scenario == 'timeout'
            else models.BoxExecutionStatus.COMPLETED,
            exit_code=None if scenario == 'timeout' else 0,
            stdout='',
            stderr='',
            duration_ms=1,
        )

    client.execute = AsyncMock(side_effect=execute)
    if scenario in {'still-missing', 'backend-error', 'cancel'}:
        expected = asyncio.CancelledError if scenario == 'cancel' else BoxError
        with pytest.raises(expected):
            await box.execute_tool({'command': 'record-one-side-effect'}, query)
    else:
        result = await box.execute_tool({'command': 'record-one-side-effect'}, query)
        assert result['ok'] is (scenario != 'timeout')
    assert requests == (2 if scenario in {'cold', 'still-missing'} else 1)
    if scenario == 'still-missing':
        assert not marker.exists()
    else:
        assert marker.read_text() == 'command executed\n'
    assert box.ap.skill_repository.get_skill_package.await_count == (1 if scenario in {'cold', 'still-missing'} else 0)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not hasattr(sdk_errors, 'BoxArtifactNotPreparedError'), reason='requires the in-tree artifact preflight protocol'
)
async def test_single_skill_cold_miss_skips_redundant_metadata_probe_and_logs_timing(tmp_path):
    from langbot_plugin.box.errors import BoxArtifactNotPreparedError
    from langbot.pkg.provider.tools.loaders.skill import register_activated_skill

    box, client = service(tmp_path, 'network')
    package, receipt = package_and_receipt()
    metadata = {key: value for key, value in package.items() if key != 'content'}
    reads = []

    async def get_package(context, name, revision, *, metadata_only=False):
        reads.append((name, metadata_only))
        return metadata if metadata_only else package

    box.ap.skill_repository = SimpleNamespace(get_skill_package=AsyncMock(side_effect=get_package))
    client.prepare_artifact.return_value = receipt
    query = make_query()
    register_activated_skill(query, {'name': 'pinned', 'revision': package['revision']})

    attempts = 0

    async def execute(spec, *, action_context):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise BoxArtifactNotPreparedError('package not prepared before execution')
        return models.BoxExecutionResult(
            session_id=spec.session_id,
            backend_name='fake',
            status=models.BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout='ok',
            stderr='',
            duration_ms=1,
        )

    client.execute = AsyncMock(side_effect=execute)
    result = await box.execute_tool({'command': 'echo ok'}, query)
    assert result['ok'] is True
    assert reads == [('pinned', False)]
    assert client.prepare_artifact.await_count == 1
    assert client.prepare_artifact.await_args.args[1] == package['content']
    logged = [call.args[0] for call in box.ap.logger.info.call_args_list]
    assert any('box_artifact_prepare_timing ' in line and 'skip_probe=True' in line for line in logged)
    assert any('box_execute_timing ' in line and 'artifact_cache_miss=True' in line for line in logged)


@pytest.mark.asyncio
@pytest.mark.skipif(
    not hasattr(sdk_errors, 'BoxArtifactNotPreparedError'), reason='requires the in-tree artifact preflight protocol'
)
async def test_multi_skill_cold_miss_keeps_probe_so_warm_skill_never_reads_archive(tmp_path):
    from langbot_plugin.box.errors import BoxArtifactNotPreparedError
    from langbot.pkg.provider.tools.loaders.skill import register_activated_skill

    box, client = service(tmp_path, 'network')
    warm_package, warm_receipt = package_and_receipt()
    cold_body = b'x'
    cold_manifest = {
        'algorithm': 'sha256-tree-v1',
        'files': [
            {
                'path': 'README.md',
                'size': len(cold_body),
                'sha256': hashlib.sha256(cold_body).hexdigest(),
                'executable': False,
            }
        ],
        'total_bytes': len(cold_body),
    }
    cold_revision = (
        'sha256:'
        + hashlib.sha256(
            json.dumps(cold_manifest, ensure_ascii=False, separators=(',', ':'), sort_keys=True).encode()
        ).hexdigest()
    )
    cold_content = b'cold archive bytes'
    cold_package = {
        'revision': cold_revision,
        'manifest': cold_manifest,
        'content': cold_content,
        'size': len(cold_content),
        'sha256': hashlib.sha256(cold_content).hexdigest(),
    }
    cold_receipt = {
        'ready': True,
        'content_digest': cold_revision,
        'mount_path': '/opt/langbot-artifacts/' + cold_revision[7:],
    }
    packages = {'warm': warm_package, 'cold': cold_package}
    reads = []

    async def get_package(context, name, revision, *, metadata_only=False):
        reads.append((name, metadata_only))
        pkg = packages[name]
        return {k: v for k, v in pkg.items() if k != 'content'} if metadata_only else pkg

    async def prepare(descriptor, content, *, action_context):
        if descriptor.content_digest == warm_package['revision']:
            assert content is None
            return warm_receipt
        if content is None:
            return {**cold_receipt, 'ready': False}
        assert content == cold_content
        return cold_receipt

    box.ap.skill_repository = SimpleNamespace(get_skill_package=AsyncMock(side_effect=get_package))
    client.prepare_artifact = AsyncMock(side_effect=prepare)
    query = make_query()
    register_activated_skill(query, {'name': 'warm', 'revision': warm_package['revision']})
    register_activated_skill(query, {'name': 'cold', 'revision': cold_revision})

    attempts = 0

    async def execute(spec, *, action_context):
        nonlocal attempts
        attempts += 1
        if attempts == 1:
            raise BoxArtifactNotPreparedError('cold artifact not prepared')
        return models.BoxExecutionResult(
            session_id=spec.session_id,
            backend_name='fake',
            status=models.BoxExecutionStatus.COMPLETED,
            exit_code=0,
            stdout='ok',
            stderr='',
            duration_ms=1,
        )

    client.execute = AsyncMock(side_effect=execute)
    result = await box.execute_tool({'command': 'echo ok'}, query)
    assert result['ok'] is True
    assert reads == [('warm', True), ('cold', True), ('cold', False)]


@pytest.mark.asyncio
async def test_duplicate_skill_revisions_are_deduplicated_during_artifact_preparation(tmp_path):
    from langbot.pkg.provider.tools.loaders.skill import register_activated_skill

    box, client = service(tmp_path, 'network')
    package, receipt = package_and_receipt()
    box.ap.skill_repository = SimpleNamespace(get_skill_package=AsyncMock(return_value=package))
    client.prepare_artifact.return_value = receipt
    query = make_query()
    register_activated_skill(query, {'name': 'first', 'revision': package['revision']})
    register_activated_skill(query, {'name': 'second', 'revision': package['revision']})

    mounts = await box.prepare_execution_artifacts(query, _CONTEXT, on_cache_miss=True)
    assert mounts == [{'content_digest': package['revision']}]
    assert box.ap.skill_repository.get_skill_package.await_count == 1
    assert client.prepare_artifact.await_count == 1


@pytest.mark.asyncio
async def test_skip_probe_still_enforces_post_rpc_placement_fence(tmp_path):
    box, client = service(tmp_path, 'network')
    package, receipt = package_and_receipt()
    box.ap.skill_repository = SimpleNamespace(get_skill_package=AsyncMock(return_value=package))
    box._validated_execution_context = AsyncMock(side_effect=[_CONTEXT, BoxValidationError('stale placement')])
    client.prepare_artifact.return_value = receipt

    with pytest.raises(BoxValidationError, match='stale placement'):
        await box.prepare_skill_artifact(_CONTEXT, 'pinned', package['revision'], skip_probe=True)
    client.prepare_artifact.assert_awaited_once()
