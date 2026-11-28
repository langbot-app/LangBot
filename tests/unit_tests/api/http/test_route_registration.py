from __future__ import annotations

from types import SimpleNamespace

import pytest

from langbot.pkg.api.http.controller import group
from langbot.pkg.api.http.controller import main as controller_main
from langbot.pkg.telemetry import usage


def test_group_class_deduplicates_in_place_by_name_and_path(monkeypatch):
    isolated_groups: list[type[group.RouterGroup]] = []
    monkeypatch.setattr(group, 'preregistered_groups', isolated_groups)
    monkeypatch.setattr(usage, 'GROUPS', set())

    @group.group_class('probe', '/api/v1/probe')
    class ProbeGroupV1(group.RouterGroup):
        async def initialize(self) -> None:
            pass

    @group.group_class('probe_alt', '/api/v1/probe')
    class ProbeAltGroup(group.RouterGroup):
        async def initialize(self) -> None:
            pass

    @group.group_class('probe', '/api/v1/probe')
    class ProbeGroupV2(group.RouterGroup):
        async def initialize(self) -> None:
            pass

    assert group.preregistered_groups is isolated_groups
    assert isolated_groups == [ProbeAltGroup, ProbeGroupV2]
    assert ProbeGroupV1 not in isolated_groups
    assert usage.GROUPS == {'probe', 'probe_alt'}


@pytest.mark.asyncio
async def test_register_routes_is_idempotent_on_same_controller(monkeypatch):
    isolated_groups: list[type[group.RouterGroup]] = []
    monkeypatch.setattr(group, 'preregistered_groups', isolated_groups)
    monkeypatch.setattr(usage, 'GROUPS', set())

    init_calls = 0

    @group.group_class('probe', '/api/v1/probe')
    class ProbeGroup(group.RouterGroup):
        async def initialize(self) -> None:
            nonlocal init_calls
            init_calls += 1

            @self.route('/ping', methods=['GET'], auth_type=group.AuthType.NONE)
            async def ping():
                return self.success(data={'pong': True})

    controller = controller_main.HTTPController(SimpleNamespace())
    await controller.register_routes()
    await controller.register_routes()

    assert init_calls == 1
    client = controller.quart_app.test_client()

    health_resp = await client.get('/healthz')
    assert health_resp.status_code == 200
    assert (await health_resp.get_json())['code'] == 0

    probe_resp = await client.get('/api/v1/probe/ping')
    assert probe_resp.status_code == 200
    assert await probe_resp.get_json() == {'code': 0, 'msg': 'ok', 'data': {'pong': True}}


@pytest.mark.asyncio
async def test_multiple_controllers_handle_reregistered_groups_in_same_process(monkeypatch):
    isolated_groups: list[type[group.RouterGroup]] = []
    monkeypatch.setattr(group, 'preregistered_groups', isolated_groups)
    monkeypatch.setattr(usage, 'GROUPS', set())

    @group.group_class('probe', '/api/v1/probe')
    class ProbeGroupV1(group.RouterGroup):
        async def initialize(self) -> None:
            @self.route('/version', methods=['GET'], auth_type=group.AuthType.NONE)
            async def version():
                return self.success(data={'version': 'v1'})

    controller_v1 = controller_main.HTTPController(SimpleNamespace())
    await controller_v1.register_routes()

    # Simulate module reload re-registering the same (name, path) group in-process.
    @group.group_class('probe', '/api/v1/probe')
    class ProbeGroupV2(group.RouterGroup):
        async def initialize(self) -> None:
            @self.route('/version', methods=['GET'], auth_type=group.AuthType.NONE)
            async def version():
                return self.success(data={'version': 'v2'})

    assert isolated_groups == [ProbeGroupV2]

    controller_v2 = controller_main.HTTPController(SimpleNamespace())
    await controller_v2.register_routes()

    resp_v1 = await controller_v1.quart_app.test_client().get('/api/v1/probe/version')
    resp_v2 = await controller_v2.quart_app.test_client().get('/api/v1/probe/version')

    assert resp_v1.status_code == 200
    assert await resp_v1.get_json() == {'code': 0, 'msg': 'ok', 'data': {'version': 'v1'}}
    assert resp_v2.status_code == 200
    assert await resp_v2.get_json() == {'code': 0, 'msg': 'ok', 'data': {'version': 'v2'}}


@pytest.mark.asyncio
async def test_register_routes_does_not_mark_registered_when_group_init_fails(monkeypatch):
    isolated_groups: list[type[group.RouterGroup]] = []
    monkeypatch.setattr(group, 'preregistered_groups', isolated_groups)
    monkeypatch.setattr(usage, 'GROUPS', set())

    @group.group_class('broken', '/api/v1/broken')
    class BrokenGroup(group.RouterGroup):
        async def initialize(self) -> None:
            raise RuntimeError('boom')

    controller = controller_main.HTTPController(SimpleNamespace())
    with pytest.raises(RuntimeError, match='boom'):
        await controller.register_routes()

    assert controller._routes_registered is False
