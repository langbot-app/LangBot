"""Portable scenario documents must not retain installation credentials or IDs."""

import copy

import pytest

from langbot.pkg.api.http.service.scenario_format import parse_package, project_config


def test_projection_removes_credentials_and_resource_ids_without_mutating_source():
    original = {
        'password': 'private-value',
        'model': {'primary': 'foreign-model', 'fallbacks': []},
        'knowledge': ['foreign-kb'],
        'prompt': [{'role': 'system', 'content': 'Be helpful'}],
        'unknown': {'authorization': 'Bearer private'},
        'temperature': 0.5,
    }
    snapshot = copy.deepcopy(original)
    schema = [
        {'name': 'password', 'type': 'password', 'required': True},
        {'name': 'model', 'type': 'model-fallback-selector', 'required': True},
        {'name': 'knowledge', 'type': 'knowledge-base-multi-selector'},
        {'name': 'prompt', 'type': 'prompt-editor'},
        {'name': 'temperature', 'type': 'float'},
    ]
    projected, inputs = project_config(original, schema, 'agent', ['config'])
    assert original == snapshot
    assert projected['password'] == ''
    assert projected['model']['primary'] == ''
    assert projected['knowledge'] == []
    assert projected['unknown'] == {}
    assert projected['prompt'] == original['prompt']
    assert projected['temperature'] == 0.5
    assert {item.kind for item in inputs} == {'credential', 'model', 'knowledge', 'configuration'}
    assert all(item.required for item in inputs)


def test_platform_credentials_and_urls_are_never_copied_from_defaults():
    projected, inputs = project_config(
        {'url': 'https://user:password@example.org', 'token': 'secret', 'port': 1234},
        [
            {'name': 'token', 'type': 'string', 'default': 'unsafe', 'required': True},
            {'name': 'port', 'type': 'integer'},
        ],
        'main',
        ['adapter_config'],
        platform=True,
    )
    assert projected == {'url': '', 'token': '', 'port': 1234}
    assert len(inputs) == 2


def package():
    return {
        'metadata': {'name': 'Example'},
        'resources': [
            {
                'id': 'main',
                'kind': 'bot',
                'data': {
                    'event_bindings': [
                        {'target_type': 'pipeline', 'target_uuid': 'flow'},
                    ]
                },
            },
            {'id': 'flow', 'kind': 'pipeline', 'data': {'config': {}}},
        ],
    }


def test_internal_routes_must_resolve_to_matching_resource_kind():
    document = package()
    assert parse_package(document).resources[1].id == 'flow'
    document['resources'][0]['data']['event_bindings'][0]['target_uuid'] = 'foreign-uuid'
    with pytest.raises(ValueError, match='route reference'):
        parse_package(document)


def test_unknown_versions_duplicate_ids_and_invalid_input_paths_rejected():
    document = package()
    document['format_version'] = 2
    with pytest.raises(ValueError):
        parse_package(document)
    document = package()
    document['resources'].append(copy.deepcopy(document['resources'][1]))
    with pytest.raises(ValueError, match='Duplicate'):
        parse_package(document)
    document = package()
    document['inputs'] = [
        {'resource': 'flow', 'path': ['workspace_uuid'], 'kind': 'configuration', 'label': 'Workspace'}
    ]
    with pytest.raises(ValueError, match='configuration path'):
        parse_package(document)
