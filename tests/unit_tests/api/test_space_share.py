"""LANG-439: credential redaction and validation before sharing to Space."""

import io
import zipfile

import pytest

from langbot.pkg.api.http.service import space_share as share


def _server(url: str, headers: dict | None = None, mode: str = 'remote') -> dict:
    return {'name': 'weather', 'mode': mode, 'extra_args': {'url': url, 'headers': headers or {}, 'timeout': 30}}


RUNTIME = {'status': 'connected', 'tools': [{'name': 'get_weather', 'description': 'Weather', 'parameters': {}}]}


def test_mcp_headers_and_query_secrets_become_placeholders():
    out = share.sanitize_mcp_server(
        _server(
            'https://mcp.example.com/v1/sse?api_key=sk-live-abcdefghijklmnopqrstuvwxyz&region=eu',
            {'Authorization': 'Bearer ghp_abcdefghijklmnopqrstuvwxyz0123456789', 'Accept': 'application/json'},
        ),
        RUNTIME,
    )
    payload = out['payload']
    assert 'sk-live' not in payload['url'] and 'region=eu' in payload['url']
    assert payload['headers']['Authorization'] == 'Bearer ${AUTHORIZATION}'
    assert payload['headers']['Accept'] == 'application/json'
    names = {i['name'] for i in payload['required_inputs']}
    assert names == {'AUTHORIZATION', 'API_KEY'}
    assert all(i['secret'] and i['required'] for i in payload['required_inputs'])
    assert payload['tools'][0]['name'] == 'get_weather'
    assert {r['placeholder'] for r in out['redactions']} == names


def test_mcp_secret_in_url_path_is_redacted():
    out = share.sanitize_mcp_server(_server('https://mcp.example.com/u/Zx9kP2mQ7vR4tY8wB3nL6cF1/mcp'), RUNTIME)
    assert 'Zx9kP2mQ7vR4tY8wB3nL6cF1' not in out['payload']['url']
    assert '${URL_TOKEN}' in out['payload']['url']


def test_mcp_existing_placeholders_are_declared_and_input_labels_applied():
    out = share.sanitize_mcp_server(
        _server('https://mcp.example.com/mcp', {'X-Api-Key': '${WEATHER_KEY}'}),
        RUNTIME,
        {'inputs': {'WEATHER_KEY': {'label': 'Weather API key', 'description': 'From the vendor console'}}},
    )
    (inp,) = out['payload']['required_inputs']
    assert inp['name'] == 'WEATHER_KEY' and inp['label'] == 'Weather API key'


@pytest.mark.parametrize(
    'server',
    [
        _server('https://mcp.example.com/mcp', mode='stdio'),
        _server('http://mcp.example.com/mcp'),
        _server('https://127.0.0.1/mcp'),
        _server('https://localhost/mcp'),
        _server('https://nas.local/mcp'),
        _server('https://user:pw@mcp.example.com/mcp'),
    ],
)
def test_mcp_unshareable_configs_are_refused(server):
    with pytest.raises(share.ShareError):
        share.sanitize_mcp_server(server, RUNTIME)


def test_prompt_payload_detects_variables_and_findings():
    payload, findings = share.build_prompt_payload(
        {
            'kind': 'messaging',
            'language': 'zh_Hans',
            'messages': [
                {
                    'role': 'system',
                    'content': '你是{{shop_name}}的客服，联系 a@b.com，密钥 sk-abcdefghijklmnopqrstuvwxyz',
                },
                {'role': 'user', 'content': 'hi'},
            ],
            'variables': [{'name': 'shop_name', 'description': '店铺名'}],
        }
    )
    assert payload['variables'] == [{'name': 'shop_name', 'description': '店铺名'}]
    kinds = {(f['kind'], f['severity']) for f in findings}
    assert ('openai_key', 'block') in kinds and ('email', 'warn') in kinds
    assert all('abcdefghijklmnop' not in f['excerpt'] for f in findings)


@pytest.mark.parametrize(
    'data',
    [
        {'kind': 'pipeline', 'messages': [{'role': 'system', 'content': 'x'}]},
        {'kind': 'agent', 'messages': [{'role': 'user', 'content': 'x'}]},
        {'kind': 'agent', 'messages': [{'role': 'system', 'content': ' '}]},
        {'kind': 'agent', 'messages': []},
        {'kind': 'agent', 'messages': [{'role': 'system', 'content': 'a' * 40000}]},
    ],
)
def test_prompt_payload_rejects_invalid(data):
    with pytest.raises(share.ShareError):
        share.build_prompt_payload(data)


def test_skill_zip_scan():
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w') as zf:
        zf.writestr('demo/SKILL.md', '---\nname: demo\n---\nUse token ghp_abcdefghijklmnopqrstuvwxyz0123456789\n')
        zf.writestr('demo/run.py', 'print(1)\n')
    info = share.inspect_skill_zip(buf.getvalue())
    assert {f['path'] for f in info['files']} == {'demo/SKILL.md', 'demo/run.py'}
    assert info['findings'][0]['kind'] == 'github_token' and info['findings'][0]['where'] == 'demo/SKILL.md'


def test_share_metadata_validation():
    meta = share.validate_share_metadata(
        {'name': 'Cs-Agent', 'label': {'zh_Hans': '客服'}, 'description': 'desc', 'tags': ['a', ' ', 'b']}
    )
    assert meta['name'] == 'cs-agent' and meta['description'] == {'en_US': 'desc'} and meta['tags'] == ['a', 'b']
    with pytest.raises(share.ShareError):
        share.validate_share_metadata({'name': 'x', 'label': 'a', 'description': 'b'})


def test_unfilled_mcp_placeholders_lists_names_only():
    from langbot.pkg.api.http.service.mcp import unfilled_mcp_placeholders

    extra = {
        'url': 'https://mcp.example.com/mcp?api_key=${API_KEY}',
        'headers': {'Authorization': 'Bearer ${TOKEN}', 'X-Trace': 'on', 'X-Again': '${TOKEN}'},
    }
    assert unfilled_mcp_placeholders(extra) == ['API_KEY', 'TOKEN']
    assert unfilled_mcp_placeholders({'url': 'https://mcp.example.com/mcp', 'headers': {'A': 'real'}}) == []
    assert unfilled_mcp_placeholders(None) == []
