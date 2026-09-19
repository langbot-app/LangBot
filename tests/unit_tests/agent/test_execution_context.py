"""Tests for Host-only Runner tool execution context."""

from __future__ import annotations


from langbot_plugin.api.entities.builtin.runner.delivery import DeliveryContext
from langbot_plugin.api.entities.builtin.runner.input import AgentInput
from langbot_plugin.api.entities.builtin.pipeline import query as pipeline_query
from langbot_plugin.api.entities.builtin.provider.message import ContentElement

from langbot.pkg.agent.runner.execution_context import (
    append_mcp_resource_context_to_event,
    build_execution_query,
    prepare_execution_query,
    project_mcp_resource_config,
)
from langbot.pkg.agent.runner.host_models import AgentEventEnvelope


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


def test_query_preparation_does_not_choose_a_box():
    event = make_event()
    query = pipeline_query.Query.model_construct(variables={})
    prepare_execution_query(query, event, ['pdf'])
    event_query = build_execution_query(event, ['pdf'])
    assert query.variables == {'_pipeline_bound_skills': ['pdf']}
    assert event_query.variables == {'_pipeline_bound_skills': ['pdf']}
    assert getattr(query, '_box_binding', None) is None


def test_project_mcp_resource_config_uses_independent_runner_settings():
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
    assert '_host_box_scope' not in query.variables


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

    assert '_host_box_scope' not in query.variables
    assert query.pipeline_config is None
    assert query.pipeline_uuid is None
