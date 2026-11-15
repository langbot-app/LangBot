"""Routine Docker status must not probe unused backends or reuse stale readiness."""

from unittest.mock import AsyncMock, Mock

import pytest
from langbot_plugin.box.errors import BoxValidationError

from langbot.pkg.box import settings
from langbot.pkg.box.service import BoxService
from tests.unit_tests.box.test_box_service import _CONTEXT, make_app


def status_service(monkeypatch, selected, backend):
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
    service = BoxService(make_app(Mock(), enabled=True), client=client)
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
async def test_overrides_and_other_backends_retain_full_readiness_checks(monkeypatch, selected, backend):
    service = status_service(monkeypatch, selected, backend)
    result = await service.get_status(_CONTEXT)
    assert result['available'] is False
    assert result['backend'] == {'name': selected, 'available': False, 'reason': 'readiness_failed'}
    service.get_workspace_backend_settings.assert_awaited_once_with(_CONTEXT)
