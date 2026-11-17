from pathlib import Path
import json

import pytest
import yaml


_REPO_ROOT = Path(__file__).resolve().parents[3]


def test_deployed_image_commands_preserve_the_built_environment():
    image_command = next(
        json.loads(line.removeprefix('CMD '))
        for line in (_REPO_ROOT / 'Dockerfile').read_text().splitlines()
        if line.startswith('CMD ')
    )
    deployments = [
        item
        for item in yaml.safe_load_all((_REPO_ROOT / 'docker/kubernetes.yaml').read_text())
        if item and item.get('kind') == 'Deployment'
    ]
    assert {item['metadata']['name'] for item in deployments} == {
        'langbot',
        'langbot-plugin-runtime',
        'langbot-box',
    }
    containers = [item['spec']['template']['spec']['containers'][0] for item in deployments]
    compose = yaml.safe_load((_REPO_ROOT / 'docker/docker-compose.yaml').read_text())
    services = [compose['services'][name] for name in ('langbot', 'langbot_plugin_runtime', 'langbot_box')]
    for container in [*containers, *services]:
        assert container.get('command', image_command)[:3] == ['uv', 'run', '--no-sync']


def test_kubernetes_startup_probe_protects_pre_http_migration():
    documents = yaml.safe_load_all((_REPO_ROOT / 'docker/kubernetes.yaml').read_text())
    deployment = next(
        item
        for item in documents
        if item and item.get('kind') == 'Deployment' and item['metadata']['name'] == 'langbot'
    )
    container = deployment['spec']['template']['spec']['containers'][0]
    startup = container['startupProbe']
    assert startup['httpGet'] == {'path': '/healthz', 'port': 5300}
    assert startup['httpGet'] == container['livenessProbe']['httpGet'] == container['readinessProbe']['httpGet']
    assert startup['periodSeconds'] == 10
    assert startup['timeoutSeconds'] == 5
    assert startup['periodSeconds'] * startup['failureThreshold'] >= 30 * 60


def test_kubernetes_network_artifact_root_is_visible_to_docker_daemon():
    documents = yaml.safe_load_all((_REPO_ROOT / 'docker/kubernetes.yaml').read_text())
    deployment = next(
        item
        for item in documents
        if item and item.get('kind') == 'Deployment' and item['metadata']['name'] == 'langbot-box'
    )
    spec = deployment['spec']['template']['spec']
    container = next(item for item in spec['containers'] if item['name'] == 'langbot-box')
    environment = {item['name']: item.get('value') for item in container['env']}
    local = json.loads(environment['LANGBOT_BOX_CONFIG'])['local']
    root = local['host_root']
    mount = next(item for item in container['volumeMounts'] if item['mountPath'] == root)
    volume = next(item for item in spec['volumes'] if item['name'] == mount['name'])
    assert Path(root).is_absolute()
    assert local['allowed_mount_roots'] == [root]
    assert volume['hostPath']['path'] == root


_CONTROL_LINKS = [
    pytest.param(('langbot_box', 'langbot-box', 'LANGBOT_BOX_CONTROL_TOKEN', 'langbot-box-control'), id='core-box'),
    pytest.param(
        (
            'langbot_plugin_runtime',
            'langbot-plugin-runtime',
            'LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN',
            'langbot-plugin-runtime-control',
        ),
        id='core-plugin-runtime',
    ),
]


def _compose_control_token(service, variable):
    environment = service['environment']
    if isinstance(environment, dict):
        return environment[variable]
    # Compose accepts both a mapping and a list of KEY=VALUE entries.
    matches = []
    for entry in environment:
        name, separator, value = entry.partition('=')
        if name == variable:
            matches.append(value if separator else None)
    assert len(matches) == 1, f'Expected a single {variable} environment binding'
    return matches[0]


def _kubernetes_control_token(deployment, variable):
    deployment_name = deployment['metadata']['name']
    containers = deployment['spec']['template']['spec']['containers']
    container = next(item for item in containers if item['name'] == deployment_name)
    matches = [item for item in container['env'] if item['name'] == variable]
    assert len(matches) == 1, f'Expected a single {variable} binding in {deployment_name}'
    assert 'value' not in matches[0], f'{deployment_name} must consume a Secret, not a literal'
    return matches[0]['valueFrom']['secretKeyRef']


@pytest.mark.parametrize('link', _CONTROL_LINKS)
def test_compose_control_links_use_the_same_interpolated_token(link):
    service_name, _, variable, _ = link
    compose = yaml.safe_load((_REPO_ROOT / 'docker/docker-compose.yaml').read_text(encoding='utf-8'))
    services = compose['services']
    # With the variable unset, both OSS processes must take the same empty default.
    expected = '${' + variable + ':-}'
    assert _compose_control_token(services['langbot'], variable) == expected
    assert _compose_control_token(services[service_name], variable) == expected


@pytest.mark.parametrize('link', _CONTROL_LINKS)
def test_kubernetes_control_links_use_the_same_secret(link):
    _, deployment_name, variable, secret_name = link
    text = (_REPO_ROOT / 'docker/kubernetes.yaml').read_text(encoding='utf-8')
    deployments = {
        item['metadata']['name']: item for item in yaml.safe_load_all(text) if item and item['kind'] == 'Deployment'
    }
    core = deployments['langbot']
    target = deployments[deployment_name]
    assert core['metadata']['namespace'] == target['metadata']['namespace']
    for deployment in (core, target):
        ref = _kubernetes_control_token(deployment, variable)
        assert (ref['name'], ref['key']) == (secret_name, 'token')
        assert ref.get('optional', False) is False

    # Verify the documented bootstrap names the same object. This is separate
    # from the structured wiring check: comments cannot satisfy it.
    assert f'create secret generic {secret_name}' in text
    assert '--from-literal=token="$(openssl rand -hex 32)"' in text
