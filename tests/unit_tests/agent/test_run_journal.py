"""Agent monitoring snapshots retain useful input without duplicating binary payloads."""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from langbot.pkg.agent.runner.run_journal import AgentRunJournal


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

    if event_type != 'message.received':
        assert saved['metadata']['input_event'] == event.data
    else:
        assert 'input_event' not in saved['metadata']
