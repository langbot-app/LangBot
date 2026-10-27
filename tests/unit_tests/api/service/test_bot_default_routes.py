import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock

from langbot.pkg.api.http.service.bot import BotService


async def test_concurrent_first_bots_share_one_default_pipeline():
    pipelines = []

    async def create(context, data, default=False):
        await asyncio.sleep(0)
        assert default
        pipelines.append({'uuid': 'p', 'is_default': True})
        return 'p'

    ap = SimpleNamespace(
        pipeline_service=SimpleNamespace(
            get_pipelines=AsyncMock(side_effect=lambda context: list(pipelines)),
            create_pipeline=AsyncMock(side_effect=create),
        )
    )
    service = BotService(ap)
    first, second = await asyncio.gather(
        service._build_default_event_bindings('workspace'),
        service._build_default_event_bindings('workspace'),
    )
    ap.pipeline_service.create_pipeline.assert_awaited_once()
    for bindings in (first, second):
        assert len(bindings) == 2
        assert all(binding['target_uuid'] == 'p' for binding in bindings)
        assert bindings[0]['filters'] == [{'field': 'chat_type', 'operator': 'eq', 'value': 'person'}]
        assert bindings[1]['filters'][-1] == {'field': 'is_at_bot', 'operator': 'eq', 'value': True}


async def test_existing_default_pipeline_preferred_without_creating_another():
    ap = SimpleNamespace(
        pipeline_service=SimpleNamespace(
            get_pipelines=AsyncMock(
                return_value=[
                    {'uuid': 'recent'},
                    {'uuid': 'default', 'is_default': True},
                ]
            ),
            create_pipeline=AsyncMock(),
        )
    )
    routes = await BotService(ap)._build_default_event_bindings('workspace')
    assert all(route['target_uuid'] == 'default' for route in routes)
    ap.pipeline_service.create_pipeline.assert_not_awaited()


async def test_explicit_manual_route_does_not_create_or_replace_defaults():
    ap = SimpleNamespace(
        instance_config=SimpleNamespace(data={}),
        persistence_mgr=SimpleNamespace(execute_async=AsyncMock()),
        pipeline_service=SimpleNamespace(get_pipelines=AsyncMock(), create_pipeline=AsyncMock()),
    )
    service = BotService(ap)
    service.get_bot = AsyncMock(return_value={'enable': False})
    route = {
        'id': 'manual-route',
        'event_pattern': 'message.received',
        'target_type': 'discard',
        'target_uuid': '',
        'filters': [{'field': 'chat_id', 'operator': 'eq', 'value': 'manual-group'}],
        'priority': 10,
        'enabled': False,
        'description': 'Keep this manual rule',
        'order': 0,
    }
    await service.create_bot(
        'workspace',
        {
            'name': 'Manual',
            'adapter': 'onebot-v11',
            'adapter_config': {},
            'event_bindings': [route],
        },
    )
    inserted = ap.persistence_mgr.execute_async.await_args_list[0].args[0].compile().params
    assert inserted['event_bindings'] == [route]
    ap.pipeline_service.get_pipelines.assert_not_awaited()
    ap.pipeline_service.create_pipeline.assert_not_awaited()
