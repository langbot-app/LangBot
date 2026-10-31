from pathlib import Path


_REPO_ROOT = Path(__file__).resolve().parents[3]


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
