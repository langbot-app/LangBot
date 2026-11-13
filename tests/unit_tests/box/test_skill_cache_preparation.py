import hashlib
import json
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.box import models
from langbot_plugin.box.errors import BoxAdmissionError, BoxValidationError
from langbot.pkg.box.service import BoxService
from tests.unit_tests.box.test_box_service import _CONTEXT, make_app


def service(tmp_path):
    app = make_app(Mock(), [str(tmp_path)], host_root=str(tmp_path))
    client = SimpleNamespace(prepare_artifact=AsyncMock())
    result = BoxService(app, client=client)
    result._available = True
    return result, client


@pytest.mark.parametrize('managed', [False, True])
def test_user_execution_cannot_select_cached_artifacts(tmp_path, managed):
    box, _ = service(tmp_path)
    box._cloud_managed = managed
    with pytest.raises(BoxAdmissionError, match='composed by the Host'):
        box._managed_policy_payload(_CONTEXT, {'artifact_mounts': [{'content_digest': 'sha256:' + 'a' * 64}]})


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
    box.ap.skill_repository.get_skill_package.assert_awaited_with(_CONTEXT, 'pinned', revision)
    descriptor, transferred = client.prepare_artifact.await_args.args
    assert descriptor.content_digest == revision
    assert descriptor.manifest == manifest
    assert transferred == content
    assert client.prepare_artifact.await_args.kwargs['action_context'].workspace_uuid == _CONTEXT.workspace_uuid
