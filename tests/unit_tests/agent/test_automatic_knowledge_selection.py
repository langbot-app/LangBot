from __future__ import annotations

from copy import deepcopy

from langbot.pkg.agent.runner.config_schema import project_automatic_knowledge_bases
from langbot.pkg.agent.runner.descriptor import RunnerDescriptor


def descriptor():
    return RunnerDescriptor(
        usages=['agent'],
        id='plugin:test/runner/default',
        source='plugin',
        label={'en_US': 'Test'},
        plugin_author='test',
        plugin_name='runner',
        runner_name='default',
        config_schema=[
            {'name': 'documents', 'type': 'knowledge-base-multi-selector', 'default': ['default-kb']},
            {'name': 'memory', 'type': 'select-knowledge-bases'},
        ],
    )


def test_automatic_selection_only_narrows_configured_and_authorized_kbs():
    config = {'documents': ['docs-kb', 'memory-kb'], 'memory': ['memory-kb']}
    projected = project_automatic_knowledge_bases(
        descriptor(), config, ['docs-kb', 'foreign-kb'], ['docs-kb', 'memory-kb']
    )
    assert projected == {'documents': ['docs-kb'], 'memory': []}
    assert config == {'documents': ['docs-kb', 'memory-kb'], 'memory': ['memory-kb']}


def test_explicit_empty_selection_suppresses_schema_defaults():
    assert project_automatic_knowledge_bases(descriptor(), {}, [], ['default-kb']) == {
        'documents': [],
        'memory': [],
    }


def test_run_config_copies_nested_values_without_cross_run_mutation():
    config = {'documents': ['docs-kb', 'memory-kb'], 'model': {'primary': 'model-1'}}
    original = deepcopy(config)
    first = project_automatic_knowledge_bases(descriptor(), config, ['docs-kb'], ['docs-kb', 'memory-kb'])
    second = project_automatic_knowledge_bases(descriptor(), config, ['memory-kb'], ['docs-kb', 'memory-kb'])
    first['model']['primary'] = 'changed'
    assert second['documents'] == ['memory-kb']
    assert second['model']['primary'] == 'model-1'
    assert config == original
