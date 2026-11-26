from types import SimpleNamespace

import pytest

from langbot.pkg.platform.adapters.harness.bindings import (
    bot_uuid_for,
    processor_bot_config,
    sync_processor_bots,
)


class FakeBotService:
    def __init__(self, bots=None):
        self.bots = {bot['uuid']: dict(bot) for bot in bots or []}
        self.created = []
        self.updated = []

    async def get_bots(self, _context, include_secret=False):
        return list(self.bots.values())

    async def create_bot(self, _context, payload, *, bot_uuid=None):
        self.created.append(payload)
        payload = dict(payload, uuid=bot_uuid or payload['uuid'])
        self.bots[payload['uuid']] = payload
        return payload['uuid']

    async def update_bot(self, _context, bot_uuid, payload):
        self.updated.append((bot_uuid, payload))
        self.bots[bot_uuid].update(payload)


@pytest.fixture
def processor():
    return {'uuid': 'processor-1', 'kind': 'agent', 'name': 'Support'}


def test_processor_bot_identity_and_route_are_deterministic(processor):
    first = processor_bot_config(processor, 'workspace-1')
    assert first == processor_bot_config(processor, 'workspace-1')
    assert first['uuid'] == bot_uuid_for('workspace-1', processor['uuid'])
    assert first['adapter_config'] == {'processor_uuid': 'processor-1', 'processor_kind': 'agent'}
    assert first['event_bindings'][0]['target_uuid'] == 'processor-1'
    assert 'filters' not in first['event_bindings'][0]
    assert bot_uuid_for('workspace-1', 'processor-1') != bot_uuid_for('workspace-2', 'processor-1')


@pytest.mark.asyncio
async def test_sync_is_idempotent_and_repairs_existing_projection(processor):
    bot_service = FakeBotService()
    ap = SimpleNamespace(bot_service=bot_service)
    await sync_processor_bots(ap, object(), 'workspace-1', [processor])
    await sync_processor_bots(ap, object(), 'workspace-1', [processor])
    assert len(bot_service.created) == 1
    assert bot_service.updated == []

    changed = dict(processor, name='Renamed')
    await sync_processor_bots(ap, object(), 'workspace-1', [changed])
    assert len(bot_service.created) == 1
    assert bot_service.bots[bot_uuid_for('workspace-1', 'processor-1')]['name'] == 'Harness · Renamed'


@pytest.mark.asyncio
async def test_sync_disables_revoked_processor_bot(processor):
    existing = processor_bot_config(processor, 'workspace-1')
    bot_service = FakeBotService([existing])
    ap = SimpleNamespace(bot_service=bot_service)
    await sync_processor_bots(ap, object(), 'workspace-1', [])
    assert bot_service.updated == [(existing['uuid'], {'enable': False})]
    assert bot_service.bots[existing['uuid']]['enable'] is False


@pytest.mark.asyncio
async def test_v4_projection_adds_one_bot_for_each_new_processor():
    """Measure the SPEC v4.0 baseline before changing the routing model."""
    bot_service = FakeBotService()
    ap = SimpleNamespace(bot_service=bot_service)
    processors = [{'uuid': f'processor-{i}', 'kind': 'agent', 'name': f'Agent {i}'} for i in range(100)]

    await sync_processor_bots(ap, object(), 'workspace-1', processors[:1])
    assert len(bot_service.bots) == 1
    await sync_processor_bots(ap, object(), 'workspace-1', processors)
    assert len(bot_service.bots) == 100

    await sync_processor_bots(ap, object(), 'workspace-1', processors[:1])
    assert len(bot_service.bots) == 100
    assert sum(bot['enable'] for bot in bot_service.bots.values()) == 1
