import asyncio
import base64
import json
import time
from types import SimpleNamespace

import pytest
import sqlalchemy as sa
from quart import Quart
from sqlalchemy.ext.asyncio import create_async_engine

from langbot.pkg.api.http.controller.groups.harness import HarnessRouterGroup
from langbot.pkg.entity.persistence.harness_instance_key import HarnessInstanceKey
from langbot.pkg.entity.persistence.harness_registration import HarnessBinding, HarnessRegistrationLink
from langbot.pkg.harness.binding import HarnessBindings
from langbot.pkg.utils import constants


def _payload(link):
    fragment = link['url'].split('#')[1]
    return json.loads(base64.urlsafe_b64decode(fragment + '=' * (-len(fragment) % 4)))


@pytest.mark.asyncio
async def test_instance_binding_is_atomic_and_a_link_cannot_be_redeemed_twice(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, 'instance_id', 'instance-identifier')
    engine = create_async_engine(f'sqlite+aiosqlite:///{tmp_path / "harness.db"}')
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(
            data={
                'harness': {
                    'enabled': True,
                    'instance_origin': 'https://instance.example:5300',
                    'client_origin': 'https://harness.example',
                },
                'system': {'jwt': {'secret': 'test-instance-secret'}},
            }
        ),
        deployment=SimpleNamespace(mode='oss'),
        persistence_mgr=SimpleNamespace(get_db_engine=lambda: engine),
    )
    try:
        async with engine.begin() as conn:
            for model in (HarnessRegistrationLink, HarnessBinding, HarnessInstanceKey):
                await conn.run_sync(model.__table__.create)
        service = HarnessBindings(ap)
        issuer = SimpleNamespace(workspace_uuid='issuer', account_uuid='admin')
        outsider = SimpleNamespace(workspace_uuid='other', account_uuid='another-admin')
        first, second = await asyncio.gather(
            service.issue(issuer, label='Company', preferred_auth='local'),
            service.issue(issuer, label='Company', preferred_auth=None),
        )
        payload = _payload(first)
        assert payload['base_url'] == 'https://instance.example:5300'
        assert payload['pub_ed25519'] == _payload(second)['pub_ed25519']
        async with engine.connect() as conn:
            stored = (await conn.execute(sa.select(HarnessRegistrationLink.token_hash))).scalars().all()
            assert len(stored) == 2 and all(payload['token'] not in digest for digest in stored)

        assert not await service.revoke(outsider, second['id'], links=True)
        assert await service.revoke(issuer, second['id'], links=True)
        assert await service.redeem(_payload(second)['token']) is None
        third = await service.issue(issuer, label='Company', preferred_auth=None)
        async with engine.begin() as conn:
            await conn.execute(
                sa.update(HarnessRegistrationLink)
                .where(HarnessRegistrationLink.id == third['id'])
                .values(expires_at=int(time.time()) - 1)
            )
        assert await service.redeem(_payload(third)['token']) is None

        # Reconstruct the service to verify that the data survives its lifetime.
        service = HarnessBindings(ap)
        results = await asyncio.gather(*(service.redeem(payload['token']) for _ in range(8)))
        (binding,) = [result for result in results if result is not None]
        assert binding['instance_uuid'] == constants.instance_id
        assert [row['id'] for row in await service.list_active(issuer, links=False)] == [binding['harness_id']]
        assert await service.list_active(outsider, links=False) == []
        assert await service.revoke(issuer, binding['harness_id'], links=False)
        assert await service.list_active(issuer, links=False) == []

        quart_app = Quart(__name__)
        await HarnessRouterGroup(ap, quart_app).initialize()
        client = quart_app.test_client()
        link = await service.issue(issuer, label='Direct registration', preferred_auth='local')
        body = {'token': _payload(link)['token']}
        path = '/api/v1/harness/register'
        assert (await client.post(path, json=body)).status_code == 404
        denied = await client.post(path, scheme='https', headers={'Origin': 'https://other.example'}, json=body)
        assert denied.status_code == 404
        accepted = await client.post(path, scheme='https', headers={'Origin': 'https://harness.example'}, json=body)
        assert accepted.status_code == 200
        assert accepted.headers['Cache-Control'] == 'no-store'
        assert (await accepted.get_json())['instance_uuid'] == constants.instance_id
    finally:
        await engine.dispose()
