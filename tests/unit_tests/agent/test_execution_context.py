"""Tests for Host-only AgentRunner tool execution context."""

from __future__ import annotations

import json

from langbot_plugin.api.entities.builtin.agent_runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.agent_runner.input import AgentInput
from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query
from langbot_plugin.api.entities.builtin.provider.message import ContentElement

from langbot.pkg.agent.runner.execution_context import (
    append_mcp_resource_context_to_event,
    build_execution_query,
    build_host_box_scope,
    prepare_box_scope,
    prepare_execution_query,
    project_mcp_resource_config,
)
from langbot.pkg.agent.runner.host_models import AgentEventEnvelope
from langbot.pkg.utils import constants


class PlatformAdapter:
    pass


def make_event(
    *,
    event_id: str = 'event-1',
    conversation_id: str | None = 'person_user-1',
    target_type: str | None = 'person',
    target_id: str | None = 'user-1',
    adapter: str = 'PlatformAdapter',
) -> AgentEventEnvelope:
    reply_target = {}
    if target_type is not None:
        reply_target['target_type'] = target_type
    if target_id is not None:
        reply_target['target_id'] = target_id
    return AgentEventEnvelope(
        event_id=event_id,
        event_type='message.received',
        source='platform',
        bot_id='bot-1',
        workspace_id='workspace-1',
        conversation_id=conversation_id,
        input=AgentInput(text='hello'),
        delivery=DeliveryContext(
            surface='platform',
            reply_target=reply_target,
            platform_capabilities={'adapter': adapter},
        ),
    )


def test_pipeline_and_event_execution_use_same_platform_session_scope(monkeypatch):
    monkeypatch.setattr(constants, 'instance_id', 'instance-1')
    event = make_event()
    query = pipeline_query.Query.model_construct(
        query_id=1,
        launcher_type='person',
        launcher_id='user-1',
        sender_id='user-1',
        adapter=PlatformAdapter(),
        variables={},
    )

    prepare_execution_query(query, event, ['pdf'])
    event_query = build_execution_query(event, ['pdf'])

    assert query.variables['_host_box_scope'] == event_query.variables['_host_box_scope']
    assert query.variables['_pipeline_bound_skills'] == ['pdf']
    assert event_query.variables['_pipeline_bound_skills'] == ['pdf']
    scope = json.loads(query.variables['_host_box_scope'])
    assert scope == {
        'instance_id': 'instance-1',
        'workspace_id': 'workspace-1',
        'bot_id': 'bot-1',
        'platform_adapter': 'PlatformAdapter',
        'target_type': 'person',
        'target_id': 'user-1',
        'thread_id': None,
    }


def test_prepare_box_scope_does_not_change_existing_skill_projection():
    event = make_event()
    query = pipeline_query.Query.model_construct(
        query_id=1,
        launcher_type='person',
        launcher_id='user-1',
        variables={'_pipeline_bound_skills': ['existing']},
    )

    variables = prepare_box_scope(query, event)

    assert variables['_host_box_scope']
    assert variables['_pipeline_bound_skills'] == ['existing']


def test_prepare_box_scope_preserves_event_first_channel_scope():
    channel_event = make_event(target_type='channel', target_id='same')
    channel_query = build_execution_query(channel_event, [])
    original_scope = channel_query.variables['_host_box_scope']

    prepare_execution_query(channel_query, channel_event, [])

    person_scope = build_execution_query(make_event(target_type='person', target_id='same'), []).variables[
        '_host_box_scope'
    ]
    assert channel_query.variables['_host_box_scope'] == original_scope
    assert json.loads(original_scope)['target_type'] == 'channel'
    assert original_scope != person_scope


def test_prepare_box_scope_overwrites_untrusted_existing_scope():
    event = make_event(target_type='person', target_id='user-1')
    query = pipeline_query.Query.model_construct(
        query_id=1,
        launcher_type='person',
        launcher_id='user-1',
        variables={'_host_box_scope': 'forged-scope'},
    )

    variables = prepare_box_scope(query, event)

    assert variables['_host_box_scope'] != 'forged-scope'
    assert json.loads(variables['_host_box_scope'])['target_id'] == 'user-1'


def test_project_mcp_resource_config_uses_independent_agent_runner_settings():
    query = pipeline_query.Query.model_construct(variables={})
    attachments = [
        {
            'server_uuid': 'srv-1',
            'server_name': 'docs',
            'uri': 'file:///README.md',
            'mode': 'pinned',
        }
    ]

    variables = project_mcp_resource_config(
        query,
        {
            'mcp-resources': attachments,
            'mcp-resource-agent-read-enabled': False,
        },
    )

    assert variables['_pipeline_mcp_resource_attachments'] == attachments
    assert variables['_pipeline_mcp_resource_attachments'] is not attachments
    assert variables['_pipeline_mcp_resource_agent_read_enabled'] is False


def test_project_mcp_resource_config_fails_closed_for_non_boolean_read_flag():
    query = pipeline_query.Query.model_construct(variables={})

    variables = project_mcp_resource_config(
        query,
        {'mcp-resource-agent-read-enabled': 0},
    )

    assert variables['_pipeline_mcp_resource_agent_read_enabled'] is False


def test_pinned_context_updates_text_and_structured_input():
    event = make_event()
    event.input = AgentInput(
        text='hello',
        contents=[ContentElement.from_text('hello')],
    )

    append_mcp_resource_context_to_event(event, '\n\npinned-context')

    assert event.input.text == 'hello\n\npinned-context'
    assert event.input.contents[0].text == 'hello\n\npinned-context'


def test_event_reply_target_populates_valid_session_identity():
    event = make_event(conversation_id='rotating-transcript-id', target_type='group', target_id='room-1')

    query = build_execution_query(event, [])

    assert query.launcher_type.value == 'group'
    assert query.launcher_id == 'room-1'
    assert query.sender_id == 'room-1'
    assert query.session.launcher_type.value == 'group'
    assert query.session.launcher_id == 'room-1'
    scope = json.loads(query.variables['_host_box_scope'])
    assert scope['target_type'] == 'group'
    assert scope['target_id'] == 'room-1'
    assert 'rotating-transcript-id' not in query.variables['_host_box_scope']


def test_non_message_event_without_conversation_uses_event_scope():
    event = make_event(
        event_id='scheduled/event/中文',
        conversation_id=None,
        target_type=None,
        target_id=None,
        adapter='scheduler',
    )
    event.event_type = 'schedule.triggered'

    query = build_execution_query(event, [])

    scope = json.loads(query.variables['_host_box_scope'])
    assert scope['target_type'] == 'event'
    assert scope['target_id'] == event.event_id
    assert query.pipeline_config is None
    assert query.pipeline_uuid is None


def test_scope_isolated_by_instance_and_platform_adapter(monkeypatch):
    event = make_event(adapter='AdapterA')
    monkeypatch.setattr(constants, 'instance_id', 'instance-a')
    first = build_host_box_scope(event)

    monkeypatch.setattr(constants, 'instance_id', 'instance-b')
    second = build_host_box_scope(event)
    other_adapter = build_host_box_scope(make_event(adapter='AdapterB'))

    assert first != second
    assert second != other_adapter
