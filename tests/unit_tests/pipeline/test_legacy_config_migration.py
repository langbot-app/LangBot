"""Behavioral tests for the pure, fail-closed legacy migration planner."""

import copy
import importlib
import importlib.util
import json
from pathlib import Path

import pytest


FIXTURES = json.loads((Path(__file__).parents[2] / 'fixtures/pipeline_migration/synthetic_legacy.json').read_text())
TARGETS = {
    'local-agent': ('LocalAgent', '0.1.7', None),
    'dify-service-api': ('DifyAgent', '0.1.7', None),
    'coze-api': ('CozeAgent', '0.1.7', None),
    'dashscope-app-api': ('DashScopeAgent', '0.1.7', None),
    'n8n-service-api': ('N8nAgent', '0.1.7', None),
    'langflow-api': ('LangflowAgent', '0.1.7', None),
    'deerflow-api': ('DeerFlowAgent', '0.1.7', None),
    'tbox-app-api': ('TboxAgent', '0.1.5', None),
    'weknora-api': ('WeKnoraAgent', '0.1.7', None),
}


def source_for(runner='deerflow-api'):
    return {
        'uuid': 'synthetic-pipeline',
        'bot_uuid': 'synthetic-bot',
        'stages': [{'stage': 'synthetic', 'config': {'nested': [False, 0, None]}}],
        'output': {'misc': {'remove-think': False}},
        'ai': {'runner': {'runner': runner, 'expire-time': 0}, runner: copy.deepcopy(FIXTURES[runner])},
    }


def plan(source, preferences=None):
    return planner().plan_legacy_pipeline(source, preferences)


def assert_block(result, code, field=None):
    assert result['state'] == 'blocked'
    assert result['config'] is None
    assert result['changed_paths'] == []
    expected = {'code': code}
    if field is not None:
        expected['field'] = field
    assert expected in result['blockers']


@pytest.mark.parametrize('runner', TARGETS)
def test_recognizes_all_nine_exact_official_identities(runner):
    result = plan(source_for(runner))
    name, version, blocker = TARGETS[runner]
    assert result['legacy_runner'] == runner
    assert result['target_runner_id'] == f'plugin:langbot-team/{name}/default'
    assert result['target_plugin'] == {'author': 'langbot-team', 'name': name, 'version': version}
    if blocker:
        assert result['state'] == 'blocked'
        assert blocker in {item['code'] for item in result['blockers']}
    else:
        assert result['state'] == 'ready'


def test_supported_deerflow_candidate_preserves_source_and_denies_new_resources():
    source = source_for()
    source['ai']['local-agent'] = {
        'enable-all-tools': True,
        'tools': ['private-tool'],
        'knowledge-bases': ['private-kb'],
        'mcp-resources': [{'uri': 'private'}],
    }
    preferences = {
        'enable_all_plugins': False,
        'plugins': [{'author': 'langbot-team', 'name': 'DeerFlowAgent'}],
        'enable_all_mcp_servers': False,
        'mcp_servers': ['restricted-server'],
        'enable_all_skills': False,
        'skills': [],
        'mcp_resource_agent_read_enabled': True,
        'mcp_resources': [{'uri': 'private'}],
    }
    before = copy.deepcopy((source, preferences))
    result = plan(source, preferences)
    assert result['state'] == 'ready'
    candidate = result['config']
    assert candidate is not source
    assert candidate['ai']['runner'] == {'id': result['target_runner_id'], 'expire-time': 0}
    selected = candidate['ai']['runner_config'][result['target_runner_id']]
    assert selected == {
        **FIXTURES['deerflow-api'],
        'enable-all-tools': False,
        'tools': [],
        'knowledge-bases': [],
        'mcp-resources': [],
        'mcp-resource-agent-read-enabled': False,
    }
    for key in ('uuid', 'bot_uuid', 'stages', 'output'):
        assert candidate[key] == source[key]
    assert set(candidate['ai']) == {'runner', 'runner_config'}
    assert source['ai']['local-agent'] == before[0]['ai']['local-agent']
    assert source['ai']['deerflow-api'] == before[0]['ai']['deerflow-api']
    assert (source, preferences) == before
    candidate['stages'][0]['config']['nested'].append('mutated')
    selected['api-key'] = 'mutated'
    assert (source, preferences) == before
    assert result['changed_paths'] == [
        'ai.runner.runner',
        'ai.runner.id',
        'ai.runner_config',
        'ai.local-agent',
        'ai.deerflow-api',
    ]
    assert {'code': 'external.state_validation_required', 'field': 'ai.runner'} in result['warnings']


@pytest.mark.parametrize('runner', TARGETS)
def test_current_identifiers_are_not_migrated_twice(runner):
    name = TARGETS[runner][0]
    source = source_for(runner)
    source['ai']['runner'] = {'id': f'plugin:langbot-team/{name}/default', 'expire-time': 0}
    result = plan(source)
    assert result['state'] == 'already_current'
    assert result['config'] is None
    assert result['changed_paths'] == []


@pytest.mark.parametrize('value', [None, [], False, 0, 'secret'])
def test_malformed_roots_are_safe_blockers(value):
    assert_block(plan(value), 'invalid_type', 'config')


@pytest.mark.parametrize('field', ['ai', 'runner'])
@pytest.mark.parametrize('value', [None, [], False, 0, 'secret'])
def test_malformed_envelopes_are_safe_blockers(field, value):
    source = source_for()
    if field == 'ai':
        source['ai'] = value
    else:
        source['ai']['runner'] = value
    assert_block(plan(source), 'invalid_type', 'ai' if field == 'ai' else 'ai.runner')


@pytest.mark.parametrize('current', [None, '', False, {}, 'plugin:langbot-team/DeerFlowAgent/default'])
def test_mixed_selections_block_even_empty_current_id(current):
    source = source_for()
    source['ai']['runner']['id'] = current
    assert_block(plan(source), 'mixed_runner_selection', 'ai.runner')


@pytest.mark.parametrize('value', [None, False, 0, '', [], 'secret'])
def test_malformed_active_runner_section_is_not_defaulted(value):
    source = source_for()
    source['ai']['deerflow-api'] = value
    assert_block(plan(source), 'invalid_type', 'ai.deerflow-api')


def test_existing_runner_config_is_not_overwritten():
    source = source_for()
    source['ai']['runner_config'] = {'plugin:custom/Runner/default': {'secret': 'value'}}
    assert_block(plan(source), 'mixed_runner_config', 'ai.runner_config')


def test_unknown_selection_is_not_echoed_as_public_legacy_id():
    source = source_for()
    source['ai']['runner']['runner'] = 'secret-value'
    result = plan(source)
    assert result['state'] == 'not_legacy'
    assert 'secret-value' not in json.dumps(result)


@pytest.mark.parametrize('value', [None, False, -1, 1.5, '0'])
def test_expiry_is_strict_nonnegative_integer(value):
    source = source_for()
    source['ai']['runner']['expire-time'] = value
    assert_block(plan(source), 'invalid_expiry', 'ai.runner.expire-time')


def test_unknown_active_field_name_and_value_never_leak():
    source = source_for()
    source['ai']['deerflow-api']['secret-field-name'] = 'secret-field-value'
    result = plan(source)
    assert_block(result, 'unknown_field', 'ai.deerflow-api')
    assert 'secret-field' not in json.dumps(result)


@pytest.mark.parametrize('value', [float('nan'), float('inf'), {1: 'secret'}, ('tuple',), b'secret'])
def test_non_json_values_block_without_serialization_or_coercion(value):
    source = source_for()
    source['opaque'] = value
    assert_block(plan(source), 'invalid_json_value', 'config')


def test_cyclic_input_blocks_without_recursion_error():
    source = source_for()
    source['opaque'] = source
    assert_block(plan(source), 'invalid_json_value', 'config')


@pytest.mark.parametrize('runner', TARGETS)
@pytest.mark.parametrize('value', [None, False, 0, '', [], {}])
def test_unknown_active_keys_block_even_when_falsey(runner, value):
    source = source_for(runner)
    source['ai'][runner]['secret-unknown-key'] = value
    assert_block(plan(source), 'unknown_field', f'ai.{runner}')


@pytest.mark.parametrize('runner', TARGETS)
def test_missing_active_section_is_not_seeded(runner):
    source = source_for(runner)
    del source['ai'][runner]
    assert_block(plan(source), 'missing_field', f'ai.{runner}')


@pytest.mark.parametrize('container', ['ai', 'selection'])
def test_unknown_active_envelope_keys_are_not_echoed(container):
    source = source_for()
    target = source['ai'] if container == 'ai' else source['ai']['runner']
    target['secret-unknown-key'] = 'secret-value'
    result = plan(source)
    assert_block(result, 'unknown_field', 'ai' if container == 'ai' else 'ai.runner')
    assert 'secret-' not in json.dumps(result)


@pytest.mark.parametrize(
    'preferences',
    [
        False,
        [],
        'secret',
        {'enable_all_plugins': 1},
        {'enable_all_mcp_servers': None},
        {'enable_all_skills': 'false'},
        {'plugins': ['secret']},
        {'mcp_servers': [1]},
        {'skills': [None]},
        {'mcp_resource_agent_read_enabled': 0},
        {'mcp_resources': [False]},
    ],
)
def test_malformed_extension_preferences_block_without_expanding_access(preferences):
    result = plan(source_for(), preferences)
    assert result['state'] == 'blocked'
    assert any(item['code'] == 'invalid_extension_preferences' for item in result['blockers'])
    assert 'secret' not in json.dumps(result)


def test_explicit_plugin_denylist_is_not_silently_broadened():
    preferences = {'enable_all_plugins': False, 'plugins': []}
    assert_block(plan(source_for(), preferences), 'extensions.runner_excluded', 'extensions_preferences.plugins')
    assert preferences == {'enable_all_plugins': False, 'plugins': []}


@pytest.mark.parametrize('field', ['api-key', 'auth-header'])
@pytest.mark.parametrize('secret', [' synthetic ', '\tsynthetic', 'synthetic\n'])
def test_deerflow_secret_trim_drift_blocks_without_leaking(field, secret):
    source = source_for()
    source['ai']['deerflow-api'][field] = secret
    result = plan(source)
    assert result['state'] == 'ready'
    assert result['config']['ai']['runner_config'][result['target_runner_id']][field] == secret
    assert secret not in json.dumps({k: v for k, v in result.items() if k != 'config'})
    assert source['ai']['deerflow-api'][field] == secret


@pytest.mark.parametrize(
    'field,value', [('assistant-id', ''), ('assistant-id', ' padded '), ('model-name', ' padded ')]
)
def test_deerflow_option_trim_drift_is_not_repaired(field, value):
    source = source_for()
    source['ai']['deerflow-api'][field] = value
    result = plan(source)
    assert result['state'] == 'ready'
    assert result['config']['ai']['runner_config'][result['target_runner_id']][field] == value


@pytest.mark.parametrize('field', ['thinking-enabled', 'plan-mode', 'subagent-enabled'])
@pytest.mark.parametrize('value', [None, 0, 1, 'false', []])
def test_deerflow_requires_real_booleans(field, value):
    source = source_for()
    source['ai']['deerflow-api'][field] = value
    assert_block(plan(source), 'invalid_type', f'ai.deerflow-api.{field}')


@pytest.mark.parametrize('field', ['timeout', 'max-concurrent-subagents', 'recursion-limit'])
@pytest.mark.parametrize('value', [None, False, 1.5, '3'])
def test_deerflow_requires_real_integers_without_coercion(field, value):
    source = source_for()
    source['ai']['deerflow-api'][field] = value
    assert_block(plan(source), 'invalid_type', f'ai.deerflow-api.{field}')


@pytest.mark.parametrize('field', ['timeout', 'max-concurrent-subagents', 'recursion-limit'])
@pytest.mark.parametrize('value', [0, -1, 1])
def test_deerflow_does_not_invent_numeric_clamps(field, value):
    source = source_for()
    source['ai']['deerflow-api'][field] = value
    result = plan(source)
    assert result['state'] == 'ready'
    assert result['config']['ai']['runner_config'][result['target_runner_id']][field] == value


@pytest.mark.parametrize('value', [None, False, 0, [], ''])
def test_deerflow_requires_url_not_ui_default(value):
    source = source_for()
    source['ai']['deerflow-api']['api-base'] = value
    result = plan(source)
    assert result['state'] == 'blocked'
    assert result['blockers'][0]['field'] == 'ai.deerflow-api.api-base'


def test_deerflow_native_runtime_defaults_are_materialized_not_ui_defaults():
    source = source_for()
    source['ai']['deerflow-api'] = {'api-base': ' https://example.invalid/path/?signed=synthetic '}
    del source['ai']['runner']['expire-time']
    result = plan(source)
    assert result['state'] == 'ready'
    selected = result['config']['ai']['runner_config'][result['target_runner_id']]
    assert selected == {
        'api-base': ' https://example.invalid/path/?signed=synthetic ',
        'api-key': '',
        'auth-header': '',
        'assistant-id': 'lead_agent',
        'model-name': '',
        'thinking-enabled': False,
        'plan-mode': False,
        'subagent-enabled': False,
        'max-concurrent-subagents': 3,
        'timeout': 300,
        'recursion-limit': 1000,
        'enable-all-tools': False,
        'tools': [],
        'knowledge-bases': [],
        'mcp-resources': [],
        'mcp-resource-agent-read-enabled': False,
    }
    assert 'expire-time' not in result['config']['ai']['runner']


def test_deerflow_missing_endpoint_blocks_instead_of_using_schema_localhost():
    source = source_for()
    del source['ai']['deerflow-api']['api-base']
    assert_block(plan(source), 'missing_field', 'ai.deerflow-api.api-base')


def test_ready_public_projection_contains_no_secrets_or_credentials_in_urls():
    source = source_for()
    section = source['ai']['deerflow-api']
    section.update(
        {
            'api-key': 'SECRET-KEY',
            'auth-header': 'Bearer SECRET-HEADER',
            'api-base': 'https://name:SECRET-PASSWORD@example.invalid/?token=SECRET-TOKEN',
        }
    )
    result = plan(source)
    assert result['state'] == 'ready'
    selected = result['config']['ai']['runner_config'][result['target_runner_id']]
    for key, value in section.items():
        assert selected[key] == value
    public = {key: value for key, value in result.items() if key != 'config'}
    assert 'SECRET' not in json.dumps(public)


@pytest.mark.parametrize('value', [None, 0, 'false'])
def test_remove_think_flag_is_not_coerced(value):
    source = source_for('tbox-app-api')
    source['output']['misc']['remove-think'] = value
    assert_block(plan(source), 'invalid_type', 'output.misc.remove-think')


@pytest.mark.parametrize(
    'runner,code',
    [
        ('dify-service-api', 'dify.remove_think_schema'),
        ('coze-api', 'coze.remove_think'),
        ('dashscope-app-api', 'dashscope.remove_think'),
        ('tbox-app-api', 'tbox.remove_think'),
    ],
)
def test_unsupported_thinking_suppression_has_precise_blocker(runner, code):
    source = source_for(runner)
    source['output']['misc']['remove-think'] = True
    result = plan(source)
    assert code not in {b['code'] for b in result['blockers']}
    if result['state'] == 'ready':
        assert result['config']['ai']['runner_config'][result['target_runner_id']]['remove-think'] is True


@pytest.mark.parametrize('rounds', [0, 1, 10, -1])
def test_local_rounds_are_never_translated_into_transcript_item_counts(rounds):
    source = source_for('local-agent')
    source['ai']['local-agent']['max-round'] = rounds
    result = plan(source)
    assert result['state'] == 'ready'
    selected = result['config']['ai']['runner_config'][result['target_runner_id']]
    assert 'max-round' not in selected
    assert selected['context-history-fetch-limit'] == 50
    assert selected['context-window-tokens'] == 200000
    assert selected['tool-execution-mode'] == 'serial'
    assert {'code': 'local.context_defaults', 'field': 'ai.local-agent.max-round'} in result['warnings']


@pytest.mark.parametrize(
    'field,value,code',
    [
        (
            'model',
            {'primary': 'model', 'fallbacks': [], 'reasoning': {'SECRET-model': 'invalid-level'}},
            'local.reasoning_value',
        ),
        ('prompt', [{'role': 'system', 'content': 42}], 'local.prompt_shape'),
        ('prompt', [{'role': 'system', 'content': 'text', 'SECRET-key': 'SECRET-value'}], 'local.prompt_shape'),
        ('prompt', [{'role': 'system', 'content': [{'type': 'text', 'text': 42}]}], 'local.prompt_shape'),
    ],
)
def test_local_unsupported_behaviors_have_specific_safe_blockers(field, value, code):
    source = source_for('local-agent')
    source['ai']['local-agent'][field] = value
    result = plan(source)
    assert_block(result, code, f'ai.local-agent.{field}')
    assert 'SECRET' not in json.dumps(result)


@pytest.mark.parametrize(
    'field,value',
    [
        ('enable-all-tools', None),
        ('enable-all-tools', 0),
        ('tools', None),
        ('tools', [42]),
        ('mcp-resources', None),
        ('mcp-resources', [False]),
        ('mcp-resource-agent-read-enabled', 'false'),
    ],
)
def test_local_host_policy_malformed_values_block(field, value):
    source = source_for('local-agent')
    source['ai']['local-agent'][field] = value
    assert_block(plan(source), 'invalid_type', f'ai.local-agent.{field}')


@pytest.mark.parametrize(
    'runner,field',
    [
        ('dify-service-api', 'api-key'),
        ('dify-service-api', 'base-prompt'),
        ('coze-api', 'timeout'),
        ('coze-api', 'api-base'),
        ('langflow-api', 'flow-id'),
        ('n8n-service-api', 'webhook-url'),
        ('tbox-app-api', 'app-id'),
        ('weknora-api', 'app-type'),
    ],
)
def test_defaultless_native_fields_are_not_filled_from_target_schema(runner, field):
    source = source_for(runner)
    del source['ai'][runner][field]
    assert_block(plan(source), 'missing_field', f'ai.{runner}.{field}')


@pytest.mark.parametrize('value', [None, False, 0, [], {}])
@pytest.mark.parametrize('runner', [r for r in TARGETS if r not in ('local-agent', 'n8n-service-api')])
def test_external_api_keys_require_strings_even_if_target_coerces(runner, value):
    source = source_for(runner)
    source['ai'][runner]['api-key'] = value
    assert_block(plan(source), 'invalid_type', f'ai.{runner}.api-key')


@pytest.mark.parametrize(
    'section',
    [
        {'auto_save_history': False, 'auto-save-history': True},
        {'auto_save_history': True, 'auto-save-history': False},
    ],
)
def test_coze_actual_underscore_history_key_missing_null_or_conflict_blocks(section):
    source = source_for('coze-api')
    source['ai']['coze-api'].pop('auto_save_history')
    source['ai']['coze-api'].update(section)
    assert_block(plan(source), 'coze.history_alias', 'ai.coze-api.auto_save_history')


@pytest.mark.parametrize('value', [False, True])
def test_coze_equal_aliases_are_unambiguous_but_statefulness_still_blocks(value):
    source = source_for('coze-api')
    source['ai']['coze-api'].update({'auto_save_history': value, 'auto-save-history': value})
    result = plan(source)
    assert selected_config(result)['auto-save-history'] is value
    assert 'coze.history_alias' not in {b['code'] for b in result['blockers']}


def test_coze_custom_endpoint_not_replaced_with_schema_region():
    source = source_for('coze-api')
    source['ai']['coze-api']['api-base'] = 'https://secret-user:secret-pass@proxy.invalid'
    result = plan(source)
    assert_block(result, 'coze.custom_endpoint', 'ai.coze-api.api-base')
    assert 'secret-' not in json.dumps(result)


@pytest.mark.parametrize('underscore,hyphen', [('one', 'two')])
def test_dashscope_seed_hyphen_is_not_actual_native_runtime_key(underscore, hyphen):
    source = source_for('dashscope-app-api')
    section = source['ai']['dashscope-app-api']
    section.pop('references_quote')
    if underscore is not None:
        section['references_quote'] = underscore
    section['references-quote'] = hyphen
    assert_block(plan(source), 'dashscope.references_alias', 'ai.dashscope-app-api.references_quote')


@pytest.mark.parametrize('axis', ['input', 'output'])
@pytest.mark.parametrize('underscore,hyphen', [(None, 'text'), ('chat', 'text'), ('text', 'chat')])
def test_langflow_conflicting_or_nondefault_ui_only_alias_blocks(axis, underscore, hyphen):
    source = source_for('langflow-api')
    section = source['ai']['langflow-api']
    section.pop(f'{axis}_type')
    if underscore is not None:
        section[f'{axis}_type'] = underscore
    section[f'{axis}-type'] = hyphen
    assert_block(plan(source), 'langflow.io_alias', f'ai.langflow-api.{axis}_type')


@pytest.mark.parametrize(
    'raw',
    [
        '{broken-secret',
        '[]',
        '0',
        'false',
        '{"key": NaN}',
        '{"key": Infinity}',
        '{"key": 1e999}',
        '{"key":1,"key":2}',
        '{"nested":{"key":1,"key":2}}',
        [],
        False,
        0,
    ],
)
def test_langflow_tweaks_require_strict_object_json_without_fallback_loss(raw):
    source = source_for('langflow-api')
    source['ai']['langflow-api']['tweaks'] = raw
    result = plan(source)
    assert_block(result, 'langflow.invalid_tweaks', 'ai.langflow-api.tweaks')
    assert 'broken-secret' not in json.dumps(result)


@pytest.mark.parametrize('raw', [None, '', '{}', '{"nested":{"token":"SECRET","values":[null,false,0]}}'])
def test_langflow_native_empty_and_valid_tweaks_not_misreported(raw):
    source = source_for('langflow-api')
    source['ai']['langflow-api']['tweaks'] = raw
    original = copy.deepcopy(source)
    result = plan(source)
    assert result['state'] == 'ready'
    assert 'langflow.invalid_tweaks' not in {item['code'] for item in result['blockers']}
    assert 'SECRET' not in json.dumps({k: v for k, v in result.items() if k != 'config'})
    assert source == original


def test_n8n_ignore_cannot_be_encoded_as_ignored_plugin_field():
    source = source_for('n8n-service-api')
    source['ai']['n8n-service-api']['response-handling'] = 'ignore'
    result = plan(source)
    assert 'n8n.ignore_missing_0_1_6' not in {b['code'] for b in result['blockers']}


@pytest.mark.parametrize(
    'mode,missing',
    [
        ('basic', 'basic-username'),
        ('basic', 'basic-password'),
        ('jwt', 'jwt-secret'),
        ('header', 'header-name'),
        ('header', 'header-value'),
    ],
)
def test_n8n_missing_active_auth_material_has_precise_blocker(mode, missing):
    source = source_for('n8n-service-api')
    source['ai']['n8n-service-api'].update(
        {
            'auth-type': mode,
            'basic-username': 'synthetic-user',
            'basic-password': 'SECRET-pass',
            'jwt-secret': 'SECRET-jwt',
            'header-name': 'X-Synthetic',
            'header-value': 'SECRET-header',
        }
    )
    source['ai']['n8n-service-api'].pop(missing)
    result = plan(source)
    assert_block(result, 'missing_field', f'ai.n8n-service-api.{missing}')
    assert 'SECRET' not in json.dumps(result)


@pytest.mark.parametrize('mode', ['none', 'basic', 'jwt', 'header'])
def test_n8n_secrets_remain_raw_and_not_public_even_for_inactive_modes(mode):
    source = source_for('n8n-service-api')
    section = source['ai']['n8n-service-api']
    section.update(
        {
            'auth-type': mode,
            'basic-username': 'user',
            'basic-password': ' SECRET-pass ',
            'jwt-secret': '\tSECRET-jwt',
            'header-name': 'Authorization',
            'header-value': 'Bearer SECRET-header ',
        }
    )
    original = copy.deepcopy(source)
    result = plan(source)
    selected = selected_config(result)
    for field in ('basic-password', 'jwt-secret', 'header-value'):
        assert selected[field] == section[field]
    assert 'SECRET' not in json.dumps({k: v for k, v in result.items() if k != 'config'})
    assert source == original


@pytest.mark.parametrize(
    'runner,field,value',
    [
        ('dify-service-api', 'app-type', 'unknown'),
        ('dashscope-app-api', 'app-type', 'chat'),
        ('weknora-api', 'app-type', 'workflow'),
        ('n8n-service-api', 'auth-type', 'SECRET-unknown'),
    ],
)
def test_invalid_enum_values_are_not_echoed(runner, field, value):
    source = source_for(runner)
    source['ai'][runner][field] = value
    result = plan(source)
    assert_block(result, 'invalid_value', f'ai.{runner}.{field}')
    assert 'SECRET' not in json.dumps(result)


@pytest.mark.parametrize('timeout', [None, 0, 30, 301])
def test_dify_saved_timeout_is_not_blindly_activated(timeout):
    source = source_for('dify-service-api')
    source['ai']['dify-service-api']['timeout'] = timeout
    result = plan(source)
    assert 'dify.timeout_semantics' not in {b['code'] for b in result['blockers']}
    assert {'code': 'dify.timeout_default', 'field': 'ai.dify-service-api.timeout'} in result['warnings']


@pytest.mark.parametrize('current', [None, '', False, [], 'plugin:bad', ' plugin:a/b/c', 'plugin:a/b/c/extra'])
def test_malformed_current_id_is_not_already_current(current):
    source = {'ai': {'runner': {'id': current}}}
    assert_block(plan(source), 'invalid_runner_id', 'ai.runner.id')


@pytest.mark.parametrize('runner', TARGETS)
def test_deterministic_results_and_input_nonmutation_for_all_nine(runner):
    source = source_for(runner)
    original = copy.deepcopy(source)
    first = plan(source)
    second = plan(source)
    assert first == second
    assert source == original
    assert all(set(item) <= {'code', 'field'} for item in first['blockers'] + first['warnings'])


def test_ready_candidate_is_idempotently_recognized_current():
    first = plan(source_for())
    second = plan(first['config'])
    assert second['state'] == 'already_current'
    assert second['config'] is None


def planner():
    name = 'langbot.pkg.pipeline.legacy_config_migration'
    assert importlib.util.find_spec(name) is not None, 'Pure migration planner is not implemented'
    return importlib.import_module(name)


def selected_config(result):
    assert result['state'] == 'ready', result['blockers']
    return result['config']['ai']['runner_config'][result['target_runner_id']]


@pytest.mark.parametrize(
    'prompt',
    [
        [],
        [{'role': 'system', 'content': ''}],
        [{'role': 'tool', 'content': None, 'tool_call_id': 'call'}],
        [
            {
                'role': 'user',
                'name': 'name',
                'content': [
                    {'type': 'text', 'text': ''},
                    {'type': 'image_url', 'image_url': {'url': 'https://image.invalid'}},
                ],
                'provider_specific_fields': {'opaque': [False, None]},
            }
        ],
        [
            {
                'role': 'assistant',
                'tool_calls': [
                    {
                        'id': 'call',
                        'type': 'function',
                        'function': {'name': 'tool', 'arguments': '{}'},
                        'provider_specific_fields': {'signature': 'opaque'},
                    }
                ],
            }
        ],
    ],
)
def test_sdk_valid_prompts_are_preserved(prompt):
    from langbot_plugin.api.entities.builtin.provider.message import Message

    for message in prompt:
        Message.model_validate(message, strict=True)
    source = source_for('local-agent')
    source['ai']['local-agent']['prompt'] = prompt
    assert selected_config(plan(source))['prompt'] == prompt


@pytest.mark.parametrize(
    'level', ['provider_default', 'disabled', 'enabled', 'minimal', 'low', 'medium', 'high', 'xhigh', 'max']
)
def test_reasoning_and_local_authorizations_survive(level):
    source = source_for('local-agent')
    section = source['ai']['local-agent']
    section.update(
        {
            'model': {'primary': 'm', 'fallbacks': ['f'], 'reasoning': {'m': level}},
            'knowledge-base': 'kb',
            'enable-all-tools': False,
            'tools': ['tool'],
            'mcp-resources': [],
            'mcp-resource-agent-read-enabled': False,
        }
    )
    preferences = {'mcp_resources': [{'uri': 'not-granted'}], 'mcp_resource_agent_read_enabled': True}
    selected = selected_config(plan(source, preferences))
    assert selected['model'] == section['model']
    assert selected['knowledge-bases'] == ['kb']
    assert selected['tools'] == ['tool']
    assert selected['enable-all-tools'] is False
    assert selected['mcp-resources'] == []
    assert selected['mcp-resource-agent-read-enabled'] is False
    assert selected['tool-execution-mode'] == 'serial'
    assert 'knowledge-base' not in selected
    assert 'assistant-id' not in selected


def test_missing_local_host_policy_uses_native_defaults_and_preferences():
    source = source_for('local-agent')
    section = source['ai']['local-agent']
    del section['enable-all-tools']
    del section['tools']
    section['model'] = 'm'
    selected = selected_config(
        plan(source, {'mcp_resources': [{'uri': 'granted'}], 'mcp_resource_agent_read_enabled': False})
    )
    assert selected['enable-all-tools'] is True
    assert selected['tools'] == []
    assert selected['mcp-resources'] == [{'uri': 'granted'}]
    assert selected['mcp-resource-agent-read-enabled'] is False
    assert selected['model'] == {'primary': 'm', 'fallbacks': [], 'reasoning': {}}


@pytest.mark.parametrize('raw', [None, '', ' ', 'null', {}, '{"nested":[null,false,0]}'])
def test_langflow_convenience_inputs_are_explicitly_normalized(raw):
    source = source_for('langflow-api')
    source['ai']['langflow-api']['tweaks'] = raw
    selected = selected_config(plan(source))
    assert selected['tweaks'] == ({'nested': [None, False, 0]} if isinstance(raw, str) and raw.startswith('{') else {})
    assert selected['input-type'] == 'chat'
    assert 'input_type' not in selected
    assert selected['langbot-assets-enabled'] is False


@pytest.mark.parametrize('value', ['', ' ', 'references'])
def test_dashscope_unambiguous_seed_alias_is_repaired(value):
    source = source_for('dashscope-app-api')
    section = source['ai']['dashscope-app-api']
    del section['references_quote']
    section['references-quote'] = value
    result = plan(source)
    selected = selected_config(result)
    assert selected['references_quote'] == value
    assert 'references-quote' not in selected
    assert selected['timeout'] == 120
    assert {'code': 'migration.alias_repaired', 'field': 'ai.dashscope-app-api.references-quote'} in result['warnings']


@pytest.mark.parametrize('mode', ['agent', 'chat'])
@pytest.mark.parametrize('value', ['ABSENT', None, '', ' ', 'saved-agent'])
def test_weknora_agent_absence_is_not_null_or_empty(mode, value):
    source = source_for('weknora-api')
    section = source['ai']['weknora-api']
    section['app-type'] = mode
    section['knowledge-base-ids'] = None
    if value != 'ABSENT':
        section['agent-id'] = value
    selected = selected_config(plan(source))
    assert selected['agent-id'] == (
        ('builtin-quick-answer' if mode == 'chat' else 'builtin-smart-reasoning') if value == 'ABSENT' else value
    )
    assert selected['knowledge-base-ids'] == []
    assert selected['knowledge-bases'] == []


@pytest.mark.parametrize('runner', ['dashscope-app-api', 'langflow-api', 'deerflow-api', 'weknora-api'])
def test_every_ready_external_denies_dormant_host_resources(runner):
    source = source_for(runner)
    source['ai']['local-agent'] = {'tools': ['forbidden'], 'knowledge-bases': ['forbidden'], 'enable-all-tools': True}
    selected = selected_config(plan(source, {'enable_all_mcp_servers': True, 'mcp_resources': [{'uri': 'forbidden'}]}))
    assert selected['enable-all-tools'] is False
    assert selected['tools'] == selected['knowledge-bases'] == selected['mcp-resources'] == []
    assert selected['mcp-resource-agent-read-enabled'] is False
    if runner != 'deerflow-api':
        assert 'assistant-id' not in selected


@pytest.mark.parametrize(
    'runner,identity',
    [
        ('dify-service-api', 'legacy-session'),
        ('coze-api', 'legacy-session'),
        ('n8n-service-api', 'legacy-session'),
        ('tbox-app-api', 'legacy-bot'),
    ],
)
def test_verified_plugin_identity_modes_are_explicit(runner, identity):
    result = plan(source_for(runner))
    assert selected_config(result)['user-id-source'] == identity
    assert {'code': 'migration.identity_preserved', 'field': f'ai.{runner}'} in result['warnings']


@pytest.mark.parametrize(
    'values,expected',
    [
        ({}, True),
        ({'auto_save_history': None}, True),
        ({'auto-save-history': False}, False),
        ({'auto_save_history': False}, False),
        ({'auto_save_history': None, 'auto-save-history': False}, False),
    ],
)
def test_coze_history_aliases_and_null_defaults(values, expected):
    source = source_for('coze-api')
    section = source['ai']['coze-api']
    section.pop('auto_save_history')
    section.update(values)
    section['api-base'] = 'https://custom.invalid/prefix'
    selected = selected_config(plan(source))
    assert selected['auto-save-history'] is expected
    assert 'auto_save_history' not in selected
    assert selected['api-base'] == section['api-base']


@pytest.mark.parametrize(
    'values,code,field',
    [
        (
            {'basic-username': '姓名', 'basic-password': 'p', 'auth-type': 'basic'},
            'n8n.basic_encoding',
            'basic-username',
        ),
        (
            {'basic-username': 'a:b', 'basic-password': 'p', 'auth-type': 'basic'},
            'n8n.basic_encoding',
            'basic-username',
        ),
        ({'header-name': '', 'header-value': '', 'auth-type': 'header'}, 'n8n.header_name', 'header-name'),
    ],
)
def test_n8n_invalid_auth_is_not_reencoded_or_silently_dropped(values, code, field):
    source = source_for('n8n-service-api')
    source['ai']['n8n-service-api'].update(values)
    assert_block(plan(source), code, f'ai.n8n-service-api.{field}')


def test_n8n_ignore_and_native_latin1_are_selected():
    source = source_for('n8n-service-api')
    source['ai']['n8n-service-api'].update(
        {'auth-type': 'basic', 'basic-username': 'café', 'basic-password': 'p', 'response-handling': 'ignore'}
    )
    selected = selected_config(plan(source))
    assert selected['response-handling'] == 'ignore'
    assert selected['basic-encoding'] == 'latin1'


def test_weknora_blank_remote_kb_is_rejected():
    source = source_for('weknora-api')
    source['ai']['weknora-api']['knowledge-base-ids'] = [' ']
    assert_block(plan(source), 'invalid_value', 'ai.weknora-api.knowledge-base-ids')


@pytest.mark.parametrize('runner', ['coze-api', 'n8n-service-api', 'weknora-api'])
@pytest.mark.parametrize('value', [0, -1])
def test_external_target_requires_positive_timeout(runner, value):
    source = source_for(runner)
    source['ai'][runner]['timeout'] = value
    assert_block(plan(source), 'invalid_value', f'ai.{runner}.timeout')


@pytest.mark.parametrize(
    'runner,field',
    [
        ('dify-service-api', 'api-key'),
        ('dify-service-api', 'base-url'),
        ('coze-api', 'bot-id'),
        ('coze-api', 'api-key'),
        ('dashscope-app-api', 'api-key'),
        ('dashscope-app-api', 'app-id'),
        ('n8n-service-api', 'webhook-url'),
        ('langflow-api', 'base-url'),
        ('langflow-api', 'api-key'),
        ('langflow-api', 'flow-id'),
        ('tbox-app-api', 'api-key'),
        ('tbox-app-api', 'app-id'),
        ('weknora-api', 'api-key'),
        ('weknora-api', 'base-url'),
    ],
)
def test_required_target_strings_cannot_be_empty(runner, field):
    source = source_for(runner)
    source['ai'][runner][field] = ''
    assert_block(plan(source), 'invalid_value', f'ai.{runner}.{field}')


@pytest.mark.parametrize('runner', TARGETS)
def test_ready_all9_nested_candidates_are_detached_and_no_io(runner, monkeypatch):
    module = planner()
    source = source_for(runner)
    before = copy.deepcopy(source)

    def forbidden(*args, **kwargs):
        raise AssertionError('planner performed IO')

    monkeypatch.setattr('builtins.open', forbidden)
    result = module.plan_legacy_pipeline(source)
    selected = selected_config(result)
    selected['nested-test'] = ['changed']
    result['config']['stages'][0]['config']['nested'].append('changed')
    result['config']['ai']['runner']['expire-time'] = 999
    assert source == before
    assert set(result) == {
        'state',
        'legacy_runner',
        'target_runner_id',
        'target_plugin',
        'config',
        'changed_paths',
        'blockers',
        'warnings',
    }


def test_empty_config_is_not_legacy():
    result = planner().plan_legacy_pipeline({})
    assert result == {
        'state': 'not_legacy',
        'legacy_runner': None,
        'target_runner_id': None,
        'target_plugin': None,
        'config': None,
        'changed_paths': [],
        'blockers': [],
        'warnings': [],
    }


def test_default_local_agent_blocks_instead_of_inventing_round_translation():
    source = {
        'ai': {
            'runner': {'runner': 'local-agent', 'expire-time': 0},
            'local-agent': {'model': 'model-id', 'max-round': 10},
        }
    }
    original = copy.deepcopy(source)
    result = planner().plan_legacy_pipeline(source)
    assert planner().PLANNER_VERSION == '3'
    assert result['state'] == 'blocked'
    assert result['target_runner_id'] == 'plugin:langbot-team/LocalAgent/default'
    assert result['target_plugin'] == {'author': 'langbot-team', 'name': 'LocalAgent', 'version': '0.1.7'}
    assert {'code': 'missing_field', 'field': 'ai.local-agent.prompt'} in result['blockers']
    assert result['config'] is None
    assert source == original


@pytest.mark.parametrize('template', ['{global}', '{launcher_type}_{launcher_id}', '{sender_id}', '{project}'])
def test_local_box_reuse_templates_are_preserved_for_plugin(template):
    source = source_for('local-agent')
    source['ai']['local-agent']['box-session-id-template'] = template
    result = plan(source)
    assert result['state'] != 'blocked', result
    assert result['config']['ai']['runner_config'][result['target_runner_id']]['box-session-id-template'] == template


@pytest.mark.parametrize(
    'template', ['', ' ', '{}', '{0}', '{sender_id', '{sender_id!r}', '{query_id:04}', '{actor.id}', '{actor[id]}']
)
def test_invalid_box_templates_are_reported_before_migration(template):
    source = source_for('local-agent')
    source['ai']['local-agent']['box-session-id-template'] = template
    result = plan(source)
    assert_block(result, 'local.box_template_invalid', 'ai.local-agent.box-session-id-template')
