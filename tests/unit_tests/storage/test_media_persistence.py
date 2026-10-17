"""Persist media references without changing live messages or metadata-only policy."""

import base64
import copy
import json
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
import sqlalchemy as sa

from langbot.pkg.agent.runner.run_journal import AgentRunJournal
from langbot.pkg.entity.persistence.agent_run import AgentRunEvent
from langbot.pkg.entity.persistence.event_log import EventLog
from langbot.pkg.entity.persistence.monitoring import MonitoringMessage
from langbot.pkg.entity.persistence.transcript import Transcript
from langbot.pkg.pipeline.monitoring_helper import MonitoringHelper
from langbot.pkg.storage.media import MediaCache
from tests.unit_tests.api.service.test_monitoring_tenancy import (
    WORKSPACE_A,
    _context,
    _record_message,
    service as base_service,  # noqa: F401
)


@pytest.fixture
def media_service(base_service):  # noqa: F811
    service = base_service
    objects = {}

    async def save(key, data):
        objects[key] = data

    provider = SimpleNamespace(
        exists=AsyncMock(side_effect=lambda key: key in objects),
        save=AsyncMock(side_effect=save),
    )
    service.ap.logger = logging.getLogger(__name__)
    service.ap.storage_mgr = SimpleNamespace(storage_provider=provider)
    cache = MediaCache(service.ap, service.ap.storage_mgr)
    service.ap.storage_mgr.media_cache = cache
    service.ap.monitoring_service = service
    return service, objects, cache


def image(raw=b'tiny adapter image', *, encoded=True):
    payload = base64.b64encode(raw).decode()
    return {'type': 'Image', 'base64': f'data:image/png;base64,{payload}' if encoded else payload}


@pytest.mark.asyncio
@pytest.mark.parametrize(
    'response_kind',
    ['input', 'resp_message_chain', 'resp_messages', 'direct', 'structured', 'structured_dict', 'discarded'],
)
async def test_all_retained_monitoring_messages_use_cas(media_service, response_kind, monkeypatch):
    service, objects, _ = media_service
    context = _context(WORKSPACE_A)
    chain = [image()]
    original = copy.deepcopy(chain)
    legacy_content = json.dumps(chain)
    json_dumps = json.dumps

    def serialize_references(value, *args, **kwargs):
        assert not MediaCache.has_inline_images(value), 'Inline images must reach CAS before JSON serialization'
        return json_dumps(value, *args, **kwargs)

    monkeypatch.setattr(json, 'dumps', serialize_references)
    query = SimpleNamespace(
        _execution_context=context,
        launcher_type='person',
        launcher_id='user',
        sender_id='user',
        message_chain=SimpleNamespace(model_dump=lambda: chain),
        variables={},
    )
    resource = dict(bot_id='same-bot', bot_name='Bot', pipeline_id='pipeline', pipeline_name='Pipeline')
    if response_kind == 'input':
        await MonitoringHelper.record_query_start(service.ap, query, **resource)
    elif response_kind == 'direct':
        await _record_message(service, context, legacy_content)
    elif response_kind in ('structured', 'structured_dict'):
        content = {'chain': chain} if response_kind == 'structured_dict' else chain
        await _record_message(service, context, content)
    elif response_kind == 'discarded':
        from langbot.pkg.platform.botmgr import RuntimeBot

        bot = SimpleNamespace(
            ap=service.ap,
            execution_context=context,
            bot_entity=SimpleNamespace(uuid='same-bot', name='Bot'),
            PIPELINE_DISCARD=RuntimeBot.PIPELINE_DISCARD,
            PIPELINE_DISCARD_DISPLAY_NAME=RuntimeBot.PIPELINE_DISCARD_DISPLAY_NAME,
            logger=SimpleNamespace(error=AsyncMock()),
        )
        await RuntimeBot._record_discarded_message(
            bot, 'person', 'user', 'user', SimpleNamespace(), query.message_chain
        )
    else:
        response = SimpleNamespace(model_dump=lambda: chain)
        if response_kind == 'resp_message_chain':
            query.resp_message_chain = [response]
        else:
            query.resp_messages = [SimpleNamespace(get_content_platform_message_chain=lambda: response)]
        await MonitoringHelper.record_query_response(service.ap, query, **resource)

    async with service.ap.persistence_mgr.get_db_engine().connect() as conn:
        stored = (await conn.execute(sa.select(MonitoringMessage.message_content))).scalar_one()
    saved_chain = json.loads(stored)
    saved = (saved_chain['chain'] if isinstance(saved_chain, dict) else saved_chain)[0]
    assert saved['base64'] is None
    assert saved['url'].startswith('/api/v1/files/media/')
    assert objects[saved['storage_key']] == b'tiny adapter image'
    assert chain == original


@pytest.mark.asyncio
async def test_metadata_only_ingress_discards_images_without_populating_cas(media_service):
    service, objects, _ = media_service
    payload = {'type': 'message.received', 'message_chain': [image(encoded=False)], 'count': 0}
    original = copy.deepcopy(payload)
    await service.record_ingress_event(
        _context(WORKSPACE_A),
        event_id='ingress',
        event_type='message.received',
        bot_id='same-bot',
        bot_name='Bot',
        platform='slack',
        payload=payload,
    )
    async with service.ap.persistence_mgr.get_db_engine().connect() as conn:
        stored = (await conn.execute(sa.select(EventLog.input_json))).scalar_one()
    assert json.loads(stored)['message_chain'][0]['base64'] is None
    assert not objects
    assert payload == original


@pytest.mark.asyncio
async def test_repeated_images_deduplicate_across_messages_and_run_events(media_service):
    service, objects, cache = media_service
    raw = b'shared image'
    payload = image(raw)
    await _record_message(service, _context(WORKSPACE_A), json.dumps([payload]))
    journal = AgentRunJournal(service.ap)
    result = {
        'type': 'message.completed',
        'data': {
            'message': {'content': [payload]},
            'provider_image': {'type': 'image_base64', 'image_base64': payload['base64']},
        },
    }
    original = copy.deepcopy(result)
    metadata = {'diagnostic_image': image(b'metadata-only image')}
    await journal.append_run_result(result_dict=result, run_id='run', sequence=1, metadata=metadata)
    async with service.ap.persistence_mgr.get_db_engine().connect() as conn:
        stored = (await conn.execute(sa.select(AgentRunEvent.data_json))).scalar_one()
        saved_metadata = (await conn.execute(sa.select(AgentRunEvent.metadata_json))).scalar_one()
    saved = json.loads(stored)
    assert saved['message']['content'][0]['hash'] == cache.hash_bytes(raw)
    assert saved['provider_image']['image_base64'] is None
    assert saved['provider_image']['image_url']['url'].startswith('/api/v1/files/media/')
    assert len(objects) == 1
    service.ap.storage_mgr.storage_provider.save.assert_awaited_once()
    assert result == original
    assert not MediaCache.has_inline_images(json.loads(saved_metadata))
    assert MediaCache.has_inline_images(metadata)


@pytest.mark.asyncio
async def test_cas_failure_does_not_write_inline_payload_to_database(media_service):
    service, objects, _ = media_service
    service.ap.storage_mgr.storage_provider.save.side_effect = OSError('Disk full')
    message_id = await _record_message(service, _context(WORKSPACE_A), json.dumps([image()]))
    async with service.ap.persistence_mgr.get_db_engine().connect() as conn:
        stored = (
            await conn.execute(sa.select(MonitoringMessage.message_content).where(MonitoringMessage.id == message_id))
        ).scalar_one()
    assert json.loads(stored)[0]['base64'] is None
    assert not objects


@pytest.mark.asyncio
@pytest.mark.parametrize('role', ['user', 'assistant'])
async def test_transcript_remains_metadata_only_without_creating_cas_objects(media_service, role):
    service, objects, _ = media_service
    contents = [image(), {'type': 'image_base64', 'image_base64': 'eA=='}]
    original = copy.deepcopy(contents)
    event = SimpleNamespace(
        event_id='event',
        conversation_id='conversation',
        bot_id='same-bot',
        workspace_id=WORKSPACE_A,
        thread_id=None,
        actor=None,
        input=SimpleNamespace(text='image', contents=contents, attachments=[]),
    )
    journal = AgentRunJournal(service.ap)
    if role == 'user':
        await journal.write_user_transcript(event, 'event')
    else:
        await journal.write_assistant_transcript(
            result_dict={'data': {'message': {'role': 'assistant', 'content': contents}}},
            event=event,
            run_id='run',
            runner_id='runner',
        )
    async with service.ap.persistence_mgr.get_db_engine().connect() as conn:
        stored = (await conn.execute(sa.select(Transcript.content_json))).scalar_one()
    assert not MediaCache.has_inline_images(json.loads(stored))
    assert not objects
    assert contents == original
