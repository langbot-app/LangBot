"""Migration output must be accepted by the guarded current editor."""

import copy
import json
from pathlib import Path

import pytest

from langbot.pkg.pipeline.legacy_config_migration import plan_legacy_pipeline


FIXTURES = json.loads((Path(__file__).parents[2] / 'fixtures/pipeline_migration/synthetic_legacy.json').read_text())


@pytest.mark.parametrize('runner', FIXTURES)
def test_migrated_ai_is_canonical_and_complete_source_remains_available_for_snapshot(runner):
    source = {
        'ai': {'runner': {'runner': runner, 'expire-time': 0}, **copy.deepcopy(FIXTURES)},
        'output': {'misc': {'remove-think': False}},
        'trigger': {'untouched': [False, 0, None]},
    }
    original = copy.deepcopy(source)
    result = plan_legacy_pipeline(source)
    assert result['state'] == 'ready', result['blockers']
    assert set(result['config']['ai']) == {'runner', 'runner_config'}
    assert {'code': 'migration.legacy_sections_archived', 'field': 'ai'} in result['warnings']
    assert result['config']['trigger'] == original['trigger']
    assert source == original
    assert set(result['changed_paths']) == {
        'ai.runner.runner',
        'ai.runner.id',
        'ai.runner_config',
        *[f'ai.{name}' for name in FIXTURES],
    }


def test_sdk_valid_omitted_prompt_content_is_preserved_exactly():
    from langbot_plugin.api.entities.builtin.provider.message import Message

    prompt = [{'role': 'assistant', 'tool_calls': [], 'name': 'edited', 'provider_specific_fields': {'cache': False}}]
    Message.model_validate(prompt[0])
    source = {'ai': {'runner': {'runner': 'local-agent'}, 'local-agent': copy.deepcopy(FIXTURES['local-agent'])}}
    source['ai']['local-agent']['prompt'] = prompt
    result = plan_legacy_pipeline(source)
    assert result['state'] == 'ready', result['blockers']
    migrated = result['config']['ai']['runner_config'][result['target_runner_id']]['prompt']
    assert migrated == prompt
    assert 'content' not in migrated[0]


@pytest.mark.parametrize('template', ['{global}', '{launcher_type}_{launcher_id}', '{launcher_id}', '{workspace}'])
def test_box_reuse_template_is_preserved_for_runner(template):
    source = {'ai': {'runner': {'runner': 'local-agent'}, 'local-agent': copy.deepcopy(FIXTURES['local-agent'])}}
    source['ai']['local-agent']['box-session-id-template'] = template
    result = plan_legacy_pipeline(source)
    assert result['state'] == 'ready', result['blockers']
    assert result['config']['ai']['runner_config'][result['target_runner_id']]['box-session-id-template'] == template


def test_empty_box_template_requires_correction():
    source = {'ai': {'runner': {'runner': 'local-agent'}, 'local-agent': copy.deepcopy(FIXTURES['local-agent'])}}
    source['ai']['local-agent']['box-session-id-template'] = ''
    result = plan_legacy_pipeline(source)
    assert result['state'] == 'blocked'
    assert {'code': 'local.box_template_invalid', 'field': 'ai.local-agent.box-session-id-template'} in result[
        'blockers'
    ]
