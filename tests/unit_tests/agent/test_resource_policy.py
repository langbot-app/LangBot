"""Tests for generic AgentRunner resource-policy projection."""

from types import SimpleNamespace

import pytest

from langbot.pkg.agent.runner.resource_policy import ResourcePolicyProjector


def test_pipeline_projection_intersects_selected_tools_with_scoped_tools():
    policy = ResourcePolicyProjector.from_runner_config(
        {
            'enable-all-tools': False,
            'tools': ['plugin_tool', 'missing_tool', 'plugin_tool'],
            'knowledge-bases': ['kb-config'],
        },
        resolved_model_uuids=['model-1', 'model-1'],
        resolved_tool_names=['exec', 'plugin_tool', 'mcp_tool'],
        resolved_kb_uuids=['kb-runtime'],
        resolved_skill_names=[],
    )

    assert policy.allow_all_tools is False
    assert policy.allowed_tool_names == ['plugin_tool']
    assert policy.allowed_model_uuids == ['model-1']
    assert policy.allowed_kb_uuids == ['kb-runtime']
    assert policy.allowed_skill_names == []


def test_pipeline_projection_materializes_enable_all_tools_from_scoped_tools():
    policy = ResourcePolicyProjector.from_runner_config(
        {'enable-all-tools': True, 'tools': ['ignored']},
        resolved_tool_names=['exec', 'mcp_tool'],
    )

    assert policy.allow_all_tools is False
    assert policy.allowed_tool_names == ['exec', 'mcp_tool']


def test_pipeline_projection_keeps_sources_only_for_authorized_tools():
    policy = ResourcePolicyProjector.from_runner_config(
        {'enable-all-tools': False, 'tools': ['mcp_tool']},
        resolved_tool_names=['plugin_tool', 'mcp_tool'],
        resolved_tool_sources={
            'plugin_tool': {'source': 'plugin', 'source_id': 'test/plugin'},
            'mcp_tool': {'source': 'mcp', 'source_id': 'mcp-server'},
        },
    )

    assert policy.allowed_tool_sources == {
        'mcp_tool': {'source': 'mcp', 'source_id': 'mcp-server'},
    }


def test_independent_agent_projection_preserves_all_tools_intent():
    policy = ResourcePolicyProjector.from_runner_config({})

    assert policy.allow_all_tools is True
    assert policy.allowed_tool_names is None


@pytest.mark.parametrize('invalid_value', [0, None, 'false', [], {}])
def test_enable_all_tools_fails_closed_for_non_boolean_values(invalid_value):
    policy = ResourcePolicyProjector.from_runner_config(
        {'enable-all-tools': invalid_value, 'tools': ['explicit-tool']},
    )

    assert policy.allow_all_tools is False
    assert policy.allowed_tool_names == ['explicit-tool']


def test_independent_agent_projection_preserves_selected_tools():
    policy = ResourcePolicyProjector.from_runner_config(
        {'enable-all-tools': False, 'tools': ['exec', None, 'exec', 123]},
    )

    assert policy.allow_all_tools is False
    assert policy.allowed_tool_names == ['exec']


def test_filter_tools_supports_sdk_objects_and_dictionary_tools():
    policy = ResourcePolicyProjector.from_runner_config(
        {'enable-all-tools': False, 'tools': ['dict-tool', 'object-tool']},
    )
    tools = [
        {'name': 'dict-tool'},
        SimpleNamespace(name='object-tool'),
        SimpleNamespace(name='other-tool'),
    ]

    assert ResourcePolicyProjector.filter_tools(tools, policy) == tools[:2]
