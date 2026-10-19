import ast

import yaml

from langbot_plugin.api.entities.builtin.runner.manifest import RunnerManifest
from langbot_plugin.api.definition.components.manifest import ComponentManifest

from tests.e2e.test_runner_plugin_runtime import _write_qa_runner_plugin


def test_real_runtime_fixture_contains_all_four_component_kinds(tmp_path):
    _write_qa_runner_plugin(tmp_path)
    manifest = yaml.safe_load((tmp_path / 'manifest.yaml').read_text())
    assert set(manifest['spec']['components']) == {'Runner', 'Tool', 'Command', 'EventListener'}
    kinds = set()
    for path in (tmp_path / 'components').rglob('*.yaml'):
        raw = yaml.safe_load(path.read_text())
        component = ComponentManifest(
            owner='e2e/agent-runner-qa', manifest=raw, rel_path=str(path.relative_to(tmp_path))
        )
        kinds.add(component.kind)
        if component.kind == 'Runner':
            spec = raw['spec']
            runner = RunnerManifest(
                id=f'plugin:e2e/agent-runner-qa/{raw["metadata"]["name"]}',
                name=raw['metadata']['name'],
                label=raw['metadata']['label'],
                usages=spec['usages'],
                supported_event_patterns=spec.get('events') or ['*'],
                capabilities=spec.get('capabilities') or {},
                permissions=spec.get('permissions') or {},
                config_schema=spec.get('config') or [],
            )
            if path.stem == 'default':
                assert runner.capabilities.tool_calling is True
                assert set(runner.permissions.tools) == {'detail', 'call'}
    assert kinds == {'Runner', 'Tool', 'Command', 'EventListener'}
    for path in tmp_path.rglob('*.py'):
        ast.parse(path.read_text(), filename=str(path))
