"""Network Docker status avoids unrelated probes; legacy readiness stays unchanged."""

from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.box import errors as sdk_box_errors
from langbot_plugin.box.errors import BoxValidationError
from langbot_plugin.skill_store import SkillStore

from langbot.pkg.box import settings
from langbot.pkg.box.service import BoxService
from tests.unit_tests.box.test_box_service import _CONTEXT, make_app


def status_service(monkeypatch, selected, backend, mode='network'):
    if mode == 'network' and (
        not hasattr(sdk_box_errors, 'BoxArtifactNotPreparedError')
        or not callable(getattr(SkillStore, 'list_publication_manifest_resources', None))
    ):
        pytest.skip('requires network Skill execution capabilities from the in-tree SDK')
    monkeypatch.setattr(settings, 'get_backend', AsyncMock(return_value=selected))
    monkeypatch.setattr(settings, 'get_settings', AsyncMock(return_value={'limits': {'config': {'max_sessions': 2}}}))
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
    service._validated_execution_context = AsyncMock(return_value=_CONTEXT)
    service.get_workspace_backend_settings = AsyncMock(
        return_value={
            'backends': [{'name': selected, 'available': False, 'reason': 'readiness_failed'}],
        }
    )
    return service


@pytest.mark.asyncio
@pytest.mark.parametrize('available', [True, False])
async def test_matching_docker_uses_fresh_status_without_unrelated_probes(monkeypatch, available):
    backend = {'name': 'docker', 'available': available}
    service = status_service(monkeypatch, 'docker', backend)
    result = await service.get_status(_CONTEXT)
    assert result['available'] is available
    assert result['backend'] == backend
    assert result['capacity'] == {'limit': 2, 'used': 1, 'remaining': 1}
    service.get_workspace_backend_settings.assert_not_awaited()
    assert service._validated_execution_context.await_count == 2


@pytest.mark.asyncio
async def test_matching_docker_still_rejects_post_rpc_placement_cutover(monkeypatch):
    service = status_service(monkeypatch, 'docker', {'name': 'docker', 'available': True})
    service._validated_execution_context.side_effect = [_CONTEXT, BoxValidationError('stale placement')]
    with pytest.raises(BoxValidationError, match='stale placement'):
        await service.get_status(_CONTEXT)
    service.get_workspace_backend_settings.assert_not_awaited()


@pytest.mark.asyncio
@pytest.mark.parametrize('available', [True, False])
async def test_legacy_matching_docker_preserves_backend_enumeration(monkeypatch, available):
    service = status_service(monkeypatch, 'docker', {'name': 'docker', 'available': not available}, mode='legacy')
    backend = {'name': 'docker', 'available': available}
    service.get_workspace_backend_settings.return_value = {'backends': [backend]}
    result = await service.get_status(_CONTEXT)
    assert result['available'] is available
    assert result['backend'] == backend
    service.get_workspace_backend_settings.assert_awaited_once_with(_CONTEXT)


@pytest.mark.asyncio
@pytest.mark.parametrize('mode', ['legacy', 'network'])
@pytest.mark.parametrize(
    'selected,backend',
    [
        ('e2b', {'name': 'e2b', 'available': True}),
        ('nsjail', {'name': 'nsjail', 'available': True}),
        ('docker', {'name': 'host', 'available': True}),
        ('docker', None),
        ('docker', 'invalid status'),
    ],
)
async def test_overrides_and_other_backends_retain_full_readiness_checks(monkeypatch, selected, backend, mode):
    service = status_service(monkeypatch, selected, backend, mode=mode)
    result = await service.get_status(_CONTEXT)
    assert result['available'] is False
    assert result['backend'] == {'name': selected, 'available': False, 'reason': 'readiness_failed'}
    service.get_workspace_backend_settings.assert_awaited_once_with(_CONTEXT)
