"""Runner availability through a real Host, SDK runtime and HTTP pipeline."""

# Imported pytest fixtures are injected by name.
# ruff: noqa: F811

import json
import sqlite3
import zipfile

import pytest

from tests.e2e.test_runner_plugin_runtime import (  # noqa: F401
    _create_boundary_pipeline,
    _init_and_auth,
    _install_qa_plugin,
    runner_client,
    runner_e2e_config_path,
    runner_e2e_port,
    runner_e2e_tmpdir,
    runner_langbot_process,
    runner_runtime_ports,
    runner_runtime_process,
)

pytestmark = pytest.mark.e2e


def test_message_during_plugin_initialization(runner_client, runner_e2e_tmpdir):
    token = _init_and_auth(runner_client)
    pipeline_id = _create_boundary_pipeline(runner_client, token)
    original = runner_e2e_tmpdir / 'agent-runner-qa.zip'
    delayed = runner_e2e_tmpdir / 'delayed-runner.zip'
    with zipfile.ZipFile(original) as source, zipfile.ZipFile(delayed, 'w') as target:
        for item in source.infolist():
            content = source.read(item.filename)
            if item.filename == 'main.py':
                content = content.replace(b'        pass', b'        import asyncio\n        await asyncio.sleep(5)')
            target.writestr(item, content)
    _install_qa_plugin(runner_client, token, delayed)
    response = runner_client.post(
        f'/api/v1/pipelines/{pipeline_id}/run',
        headers={'Authorization': f'Bearer {token}'},
        json={'message': 'initialization window'},
    ).json()
    print(json.dumps(response, ensure_ascii=False))
    assert response['code'] == 0, response
    assert response['data']['status'] == 'completed', response


def test_missing_local_agent_has_recovery_hint(runner_client, runner_e2e_tmpdir):
    token = _init_and_auth(runner_client)
    pipeline_id = _create_boundary_pipeline(runner_client, token)
    headers = {'Authorization': f'Bearer {token}'}
    config = runner_client.get(f'/api/v1/pipelines/{pipeline_id}', headers=headers).json()['data']['pipeline']['config']
    runner_id = 'plugin:langbot-team/LocalAgent/default'
    config['ai']['runner']['id'] = runner_id
    config['ai']['runner_config'] = {runner_id: {}}
    saved = runner_client.put(f'/api/v1/pipelines/{pipeline_id}', headers=headers, json={'config': config}).json()
    assert saved['code'] == 0, saved
    response = runner_client.post(
        f'/api/v1/pipelines/{pipeline_id}/run', headers=headers, json={'message': 'missing plugin'}
    ).json()
    print(json.dumps(response, ensure_ascii=False))
    assert response['code'] == 0, response
    assert response['data']['status'] == 'failed', response
    assert 'Plugins' in response['data']['reply'], response
    with sqlite3.connect(runner_e2e_tmpdir / 'data' / 'langbot.db') as connection:
        errors = connection.execute(
            'SELECT error_message FROM monitoring_errors WHERE pipeline_id = ?', (pipeline_id,)
        ).fetchall()
    assert any('not installed in this Workspace' in row[0] for row in errors), errors
