from __future__ import annotations

import quart

from langbot.pkg.api.http.controller import main as controller_main
from langbot.pkg.utils import bounded_executor


async def test_bounded_json_request_decodes_off_loop_in_workspace_scope(
    monkeypatch,
):
    app = quart.Quart(__name__)
    app.request_class = controller_main.BoundedJSONRequest
    observed_scopes: list[str | None] = []

    async def fake_to_thread(fn, *args, **kwargs):
        observed_scopes.append(bounded_executor.current_blocking_work_scope())
        return fn(*args, **kwargs)

    monkeypatch.setattr(
        controller_main.asyncio,
        'to_thread',
        fake_to_thread,
    )

    @app.post('/json')
    async def parse_json():
        with bounded_executor.blocking_work_scope('workspace-a'):
            payload = await quart.request.get_json()
        return quart.jsonify(payload)

    response = await app.test_client().post(
        '/json',
        json={'nested': {'value': 1}},
    )

    assert response.status_code == 200
    assert await response.get_json() == {'nested': {'value': 1}}
    assert observed_scopes == ['workspace-a']
