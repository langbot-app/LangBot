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


def test_schema_text_settings_survive_and_url_credentials_are_removed():
    projected, _ = project_config(
        {'endpoint': 'https://example.test/api', 'mode': 'detailed', 'proxy': 'https://user:password@example.test/api'},
        [
            {'name': 'endpoint', 'type': 'string'},
            {'name': 'mode', 'type': 'string'},
            {'name': 'proxy', 'type': 'string'},
        ],
        'agent',
        ['config'],
    )
    assert projected == {'endpoint': 'https://example.test/api', 'mode': 'detailed', 'proxy': ''}


def test_knowledge_reference_cannot_point_outside_package():
    document = package()
    document['resources'][1]['data']['config'] = {'knowledge': ['foreign-kb']}
    document['inputs'] = [
        {'resource': 'flow', 'path': ['config', 'knowledge'], 'kind': 'knowledge', 'label': 'Knowledge'}
    ]
    with pytest.raises(ValueError, match='knowledge reference'):
        parse_package(document)


def test_hidden_fields_are_not_required_and_platform_nonsecret_configuration_survives():
    from langbot.pkg.api.http.service.scenario_format import field_is_visible

    schema = [
        {'name': 'sandbox', 'type': 'boolean'},
        {
            'name': 'scope',
            'type': 'string',
            'required': True,
            'show_if': {'field': 'sandbox', 'operator': 'eq', 'value': True},
        },
    ]
    _, inputs = project_config({'sandbox': False}, schema, 'agent', ['config'])
    assert all(not item.required for item in inputs)
    assert not field_is_visible(schema[1], {'sandbox': False})
    assert field_is_visible(schema[1], {'sandbox': True})
    config, _ = project_config(
        {'title': 'Support', 'token': 'private'},
        [{'name': 'title', 'type': 'string'}, {'name': 'token', 'type': 'string'}],
        'main',
        ['adapter_config'],
        platform=True,
    )
    assert config == {'title': 'Support', 'token': ''}


def test_partial_pipeline_configuration_gets_runtime_stage_defaults():
    from langbot.pkg.api.http.service.scenario_format import complete_pipeline_config

    original = {'ai': {'runner': {'id': 'example'}, 'runner_config': {}}, 'safety': {'rate-limit': {'limitation': 12}}}
    complete = complete_pipeline_config(original)
    assert complete['safety']['content-filter']['check-sensitive-words'] is True
    assert complete['safety']['rate-limit']['limitation'] == 12
    assert complete['ai']['runner']['id'] == 'example'
    assert 'output' in complete and 'trigger' in complete
    assert 'output' not in original
    with pytest.raises(ValueError, match='stage configuration'):
        complete_pipeline_config({'safety': 'invalid'})
