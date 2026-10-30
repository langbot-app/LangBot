"""Agent monitoring snapshots retain useful input without duplicating binary payloads."""

import datetime
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.agent.runner.run_journal import AgentRunJournal
from langbot.pkg.agent.runner import event_log_store
from langbot.pkg.agent.runner.host_models import AgentEventEnvelope
from langbot.pkg.storage.media import MediaCache


@pytest.mark.parametrize('scale', [1, 1000, 1_000_000])
@pytest.mark.parametrize('seconds', [1_790_000_000, 1_790_000_000.125, -1_790_000_000, 10_000_000_000])
def test_event_time_normalizes_current_epoch_units(scale, seconds):
    assert AgentRunJournal._event_time_to_utc(seconds * scale) == datetime.datetime.fromtimestamp(
        seconds, datetime.timezone.utc
    )


@pytest.mark.parametrize(
    'value',
    [None, True, False, 0, '1790000000', [], {}, float('nan'), float('inf'), -float('inf'), 10**400, -(10**400)],
)
def test_event_time_rejects_invalid_values_without_raising(value):
    assert AgentRunJournal._event_time_to_utc(value) is None


@pytest.fixture
def event_log_writer(monkeypatch):
    append_event = AsyncMock(return_value='event-log-id')
    monkeypatch.setattr(event_log_store, 'EventLogStore', lambda engine: SimpleNamespace(append_event=append_event))
    journal = AgentRunJournal(SimpleNamespace(persistence_mgr=SimpleNamespace(get_db_engine=lambda: None)))
    return journal, append_event


@pytest.mark.asyncio
@pytest.mark.parametrize('scale', [1, 1000, 1_000_000])
async def test_write_event_log_normalizes_timestamp(event_log_writer, scale):
    journal, append_event = event_log_writer
    event = AgentEventEnvelope(
        event_id='event',
        event_type='message.received',
        source='platform',
        event_time=1_790_000_000 * scale,
        input={},
        delivery={'surface': 'platform'},
    )
    assert await journal.write_event_log(event, None, 'run', 'runner') == 'event-log-id'
    assert append_event.call_args.kwargs['event_time'] == datetime.datetime.fromtimestamp(
        1_790_000_000, datetime.timezone.utc
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('scale', [1, 1000, 1_000_000])
async def test_steering_dropped_audit_normalizes_timestamp(event_log_writer, scale):
    journal, append_event = event_log_writer
    await journal.write_steering_dropped_audits([{'event': {'event_time': 1_790_000_000 * scale}}], 'run', 'runner')
    assert append_event.call_args.kwargs['event_type'] == 'steering.dropped'
    assert append_event.call_args.kwargs['event_time'] == datetime.datetime.fromtimestamp(
        1_790_000_000, datetime.timezone.utc
    )


@pytest.mark.asyncio
@pytest.mark.parametrize('value', [None, 0, True, 'invalid', float('inf'), 10**400])
async def test_invalid_steering_time_does_not_prevent_audit(event_log_writer, value):
    journal, append_event = event_log_writer
    await journal.write_steering_dropped_audits([{'event': {'event_time': value}}], 'run', 'runner')
    append_event.assert_awaited_once()
    assert append_event.call_args.kwargs['event_time'] is None


@pytest.mark.asyncio
@pytest.mark.parametrize('event_type', ['message.received', 'group.member_joined'])
async def test_agent_run_snapshot_records_identity_and_redacts_inline_attachments(event_type):
    journal = AgentRunJournal(SimpleNamespace())
    ledger = SimpleNamespace(create_run=AsyncMock(return_value={}))
    journal._run_ledger_store = ledger
    raw_input = {
        'text': 'Describe the attached image',
        'contents': [{'type': 'image_base64', 'image_base64': 'large-image-data'}],
        'attachments': [{'name': 'notes.txt', 'content': 'large-file-data'}],
    }
    event = SimpleNamespace(
        event_id='event-1',
        conversation_id='conversation-1',
        thread_id=None,
        workspace_id='workspace-1',
        bot_id='bot-1',
        event_type=event_type,
        data={'user_id': 'user-1', 'group_id': 'group-1'},
        source='platform',
        delivery=SimpleNamespace(model_dump=lambda **kwargs: {'target_id': 'group-1'}),
    )
    binding = SimpleNamespace(
        binding_id='agent_agent-1_runner-1',
        agent_id='agent-1',
        processor_id='agent-1',
        processor_type='agent',
    )
    await journal.create_run(
        event=event,
        binding=binding,
        descriptor=SimpleNamespace(id='runner-1'),
        context={'run_id': 'run-1', 'input': raw_input},
        authorization={},
    )
    saved = ledger.create_run.call_args.kwargs
    assert saved['agent_id'] == 'agent-1'
    assert saved['metadata']['input']['text'] == raw_input['text']
    assert saved['metadata']['input']['contents'][0]['image_base64'] is None
    assert saved['metadata']['input']['attachments'][0]['content'] is None
    assert saved['metadata']['delivery'] == {'target_id': 'group-1'}
    assert raw_input['contents'][0]['image_base64'] == 'large-image-data'
    assert raw_input['attachments'][0]['content'] == 'large-file-data'

    assert saved['metadata']['input_event'] == event.data


def test_event_snapshot_preserves_custom_values_and_redacts_nested_binary():
    data = {
        'member': {'id': 'u1', 'active': False},
        'count': 0,
        'custom': {'contents': [{'type': 'image_base64', 'image_base64': 'secret'}]},
        'attachments': [{'name': 'file.txt', 'content': 'secret'}],
    }
    saved = AgentRunJournal._sanitize_event_data(data)
    assert saved['member'] == data['member']
    assert saved['count'] == 0
    assert saved['custom']['contents'][0]['image_base64'] is None
    assert saved['attachments'][0]['content'] is None
    assert data['custom']['contents'][0]['image_base64'] == 'secret'


@pytest.mark.parametrize(
    'image',
    [
        {'type': 'Image', 'base64': 'eA=='},
        {'type': 'image_base64', 'image_base64': 'eA=='},
        {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,eA=='}},
    ],
)
def test_metadata_and_transcript_redaction_cover_all_image_encodings(image):
    content = AgentRunJournal._sanitize_content_item(image)
    event = AgentRunJournal._sanitize_event_data({'nested': [image]})
    assert not MediaCache.has_inline_images(content)
    assert not MediaCache.has_inline_images(event)
    assert content['content_redacted'] is True
    assert event['nested'][0]['content_redacted'] is True
    assert MediaCache.has_inline_images(image)
