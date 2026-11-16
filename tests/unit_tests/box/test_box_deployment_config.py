from pathlib import Path
import json

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


def test_compose_injects_the_same_box_control_token_into_host_and_runtime():
    compose = (_REPO_ROOT / 'docker' / 'docker-compose.yaml').read_text(encoding='utf-8')
    box_service = compose.split('  langbot_box:', 1)[1].split('  langbot:', 1)[0]
    langbot_service = compose.split('  langbot:', 1)[1]
    token_env = 'LANGBOT_BOX_CONTROL_TOKEN=${LANGBOT_BOX_CONTROL_TOKEN:-}'

    assert token_env in box_service
    assert token_env in langbot_service


def test_kubernetes_uses_one_secret_for_box_runtime_and_langbot():
    manifest = (_REPO_ROOT / 'docker' / 'kubernetes.yaml').read_text(encoding='utf-8')
    box_deployment = manifest.split('name: langbot-box', 1)[1].split('# Service for LangBot Box runtime', 1)[0]
    langbot_deployment = manifest.split('# Deployment for LangBot\n', 1)[1]
    secret_reference = '\n'.join(
        [
            '- name: LANGBOT_BOX_CONTROL_TOKEN',
            '          valueFrom:',
            '            secretKeyRef:',
            '              name: langbot-box-control',
            '              key: token',
        ]
    )

    assert secret_reference in box_deployment
    assert secret_reference in langbot_deployment
    assert '--from-literal=token="$(openssl rand -hex 32)"' in manifest


def test_compose_injects_same_plugin_runtime_control_token_into_both_services():
    compose = (_REPO_ROOT / 'docker' / 'docker-compose.yaml').read_text(encoding='utf-8')
    runtime_service = compose.split('  langbot_plugin_runtime:', 1)[1].split('  langbot_box:', 1)[0]
    langbot_service = compose.split('  langbot:', 1)[1]
    token_env = 'LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN=${LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN:-}'

    assert token_env in runtime_service
    assert token_env in langbot_service


def test_kubernetes_uses_one_secret_for_plugin_runtime_and_langbot():
    manifest = (_REPO_ROOT / 'docker' / 'kubernetes.yaml').read_text(encoding='utf-8')
    runtime_deployment = manifest.split('# Deployment for LangBot Plugin Runtime', 1)[1].split(
        '# Service for LangBot Plugin Runtime',
        1,
    )[0]
    langbot_deployment = manifest.split('# Deployment for LangBot\n', 1)[1]
    secret_reference = '\n'.join(
        [
            '- name: LANGBOT_PLUGIN_RUNTIME_CONTROL_TOKEN',
            '          valueFrom:',
            '            secretKeyRef:',
            '              name: langbot-plugin-runtime-control',
            '              key: token',
        ]
    )

    assert secret_reference in runtime_deployment
    assert secret_reference in langbot_deployment
    assert 'create secret generic langbot-plugin-runtime-control' in manifest
