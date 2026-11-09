"""Real end-to-end check for the inbound-file gaps of #2835.

Not a mock-level test. This boots a real LangBot process, creates a real WeCom
bot through the real HTTP API, then POSTs a genuinely encrypted callback built
with the repository's own `WXBizMsgCrypt` to `/bots/<uuid>` — the same public
path WeCom hits. The assertion reads the resulting `event_log` row straight out
of the live SQLite database.

Why this shape:

- The reported symptom is "callback answered, but no event at all". Only a real
  ingress + real persistence can distinguish that from a mocked converter pass.
- `event_log.input_json` is the sanitized `MessageReceivedEvent` dump, so the
  `message_chain` and its `File(MediaId, name)` survive there.

Run: `uv run pytest tests/e2e/test_wecom_inbound_file.py -v -m e2e`
"""

from __future__ import annotations

import json
import socket
import sqlite3
import time
import uuid
import xml.etree.ElementTree as ET

import pytest

pytestmark = pytest.mark.e2e


PDF_BYTES = (
    b'%PDF-1.4\n'
    b'1 0 obj\n<< /Type /Catalog /Pages 2 0 R >>\nendobj\n'
    b'2 0 obj\n<< /Type /Pages /Kids [] /Count 0 >>\nendobj\n'
    b'trailer\n<< /Root 1 0 R >>\n%%EOF\n'
)

CORP_ID = 'ww-e2e-corp-id'
APP_SECRET = 'e2e-app-secret'
CALLBACK_TOKEN = 'e2e-callback-token'
# Exactly 43 chars -> 32 bytes once base64-padded, as WeCom requires.
AES_KEY = 'MDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDAwMDA'


def _free_port() -> int:
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0))
        return listener.getsockname()[1]


@pytest.fixture(scope='module')
def e2e_tmpdir(tmp_path_factory):
    return tmp_path_factory.mktemp('langbot_wecom_file')


@pytest.fixture(scope='module')
def e2e_port():
    return _free_port()


@pytest.fixture(scope='module')
def langbot_process(e2e_tmpdir, e2e_port):
    from tests.e2e.utils.config_factory import create_minimal_config, create_test_directories
    from tests.e2e.utils.process_manager import LangBotProcess, find_project_root

    create_minimal_config(e2e_tmpdir, port=e2e_port)
    create_test_directories(e2e_tmpdir)
    process = LangBotProcess(
        project_root=find_project_root(),
        work_dir=e2e_tmpdir,
        port=e2e_port,
        timeout=180,
        collect_coverage=False,
    )
    try:
        assert process.start(), process.get_logs()
        yield process
    finally:
        process.stop()


@pytest.fixture(scope='module')
def e2e_client(e2e_port, langbot_process):
    import httpx

    with httpx.Client(base_url=f'http://127.0.0.1:{e2e_port}', timeout=30.0, trust_env=False) as client:
        yield client


@pytest.fixture(scope='module')
def auth_headers(e2e_client):
    credentials = {'user': 'wecom-file-e2e@example.com', 'password': 'wecom-file-e2e-password'}
    state = e2e_client.get('/api/v1/user/init')
    assert state.status_code == 200
    if not state.json()['data']['initialized']:
        created = e2e_client.post('/api/v1/user/init', json=credentials)
        assert created.status_code == 200, created.text
    authed = e2e_client.post('/api/v1/user/auth', json=credentials)
    assert authed.status_code == 200, authed.text
    headers = {'Authorization': f'Bearer {authed.json()["data"]["token"]}'}
    bootstrap = e2e_client.get('/api/v1/workspaces/bootstrap', headers=headers)
    assert bootstrap.status_code == 200, bootstrap.text
    headers['X-Workspace-Id'] = bootstrap.json()['data']['workspaces'][0]['workspace']['uuid']
    return headers


@pytest.fixture(scope='module')
def wecom_bot(e2e_client, auth_headers):
    """Create a real enabled WeCom bot and wait until its webhook is routable."""

    payload = {
        'name': 'wecom-file-e2e',
        # The EBA adapter registers as `wecom-omni`; plain `wecom` is the legacy
        # adapter in pkg/platform/sources and does not use these converters.
        'adapter': 'wecom-omni',
        'enable': True,
        'adapter_config': {
            'corpid': CORP_ID,
            'secret': APP_SECRET,
            'token': CALLBACK_TOKEN,
            'EncodingAESKey': AES_KEY,
            'contacts_secret': '',
            # Deliberately unroutable: the test proves ingress + persistence,
            # not outbound delivery.
            'api_base_url': 'http://127.0.0.1:1/cgi-bin',
        },
    }
    created = e2e_client.post('/api/v1/platform/bots', json=payload, headers=auth_headers)
    assert created.status_code == 200, created.text
    bot_uuid = created.json()['data']['uuid']

    for _ in range(160):
        probe = e2e_client.post(f'/bots/{bot_uuid}', content=b'<xml></xml>', headers={'Content-Type': 'text/xml'})
        if probe.status_code != 404:
            break
        time.sleep(0.25)
    else:  # pragma: no cover - diagnostic only
        pytest.fail(f'bot never became routable on the public webhook, last={probe.status_code} {probe.text}')

    yield {'uuid': bot_uuid, 'client': e2e_client, 'headers': auth_headers}

    e2e_client.delete(f'/api/v1/platform/bots/{bot_uuid}', headers=auth_headers)


def _encrypted_callback(xml_body: str, *, nonce: str) -> tuple[bytes, dict]:
    """Encrypt a plaintext callback exactly as WeCom does."""

    from langbot.libs.wecom_api.WXBizMsgCrypt3 import WXBizMsgCrypt

    timestamp = str(int(time.time()))
    crypt = WXBizMsgCrypt(CALLBACK_TOKEN, AES_KEY, CORP_ID)
    ret, envelope = crypt.EncryptMsg(xml_body, nonce, timestamp)
    assert ret == 0, f'EncryptMsg failed: {ret}'
    signature = ET.fromstring(envelope).find('MsgSignature')
    assert signature is not None and signature.text
    return envelope.encode('utf-8'), {
        'msg_signature': signature.text,
        'timestamp': timestamp,
        'nonce': nonce,
    }


def _file_callback_xml(media_id: str, file_name: str = 'report.pdf') -> str:
    return (
        '<xml>'
        f'<ToUserName><![CDATA[{CORP_ID}]]></ToUserName>'
        '<FromUserName><![CDATA[zhangsan]]></FromUserName>'
        '<CreateTime>1714000000</CreateTime>'
        '<MsgType><![CDATA[file]]></MsgType>'
        f'<MediaId><![CDATA[{media_id}]]></MediaId>'
        f'<FileName><![CDATA[{file_name}]]></FileName>'
        f'<FileSize>{len(PDF_BYTES)}</FileSize>'
        f'<MsgId>{uuid.uuid4().int % 10**12}</MsgId>'
        '<AgentID>1000002</AgentID>'
        '</xml>'
    )


def _post_callback(wecom_bot, media_id: str, file_name: str, nonce: str):
    body, query = _encrypted_callback(_file_callback_xml(media_id, file_name), nonce=nonce)
    return wecom_bot['client'].post(
        f'/bots/{wecom_bot["uuid"]}',
        content=body,
        headers={'Content-Type': 'text/xml'},
        params=query,
    )


def _rows_for_bot(e2e_tmpdir, bot_uuid: str) -> list[dict]:
    """Read the bot's ingress rows straight from the live database."""

    database = e2e_tmpdir / 'data' / 'langbot.db'
    with sqlite3.connect(f'file:{database}?mode=ro', uri=True) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            'SELECT id, event_type, input_json FROM event_log WHERE bot_id = ? ORDER BY id',
            (bot_uuid,),
        ).fetchall()
    return [dict(row) for row in rows]


def _wait_for_rows(e2e_tmpdir, bot_uuid: str, minimum: int) -> list[dict]:
    rows: list[dict] = []
    for _ in range(80):
        rows = _rows_for_bot(e2e_tmpdir, bot_uuid)
        if len(rows) >= minimum:
            return rows
        time.sleep(0.25)
    return rows


def test_file_callback_is_accepted_with_success(e2e_tmpdir, wecom_bot):
    """WeCom retries anything that is not a 200 `success`."""

    response = _post_callback(wecom_bot, 'media-e2e-1', 'report.pdf', nonce='nonce-1')

    assert response.status_code == 200, response.text
    assert response.text.strip() == 'success'
    assert _wait_for_rows(e2e_tmpdir, wecom_bot['uuid'], 1), 'file callback did not append an event_log row'


def test_file_callback_records_a_message_event_with_the_media_id(e2e_tmpdir, wecom_bot):
    """The reported bug: the file produced no `message.received` event at all."""

    response = _post_callback(wecom_bot, 'media-e2e-2', 'contract.pdf', nonce='nonce-2')
    assert response.status_code == 200, response.text

    rows = _wait_for_rows(e2e_tmpdir, wecom_bot['uuid'], 2)
    assert len(rows) >= 2, f'expected a second event_log row, got {rows}'

    # Before the fix this was a `platform.specific` event, so no pipeline ran and
    # the MediaId never survived into the event.
    assert all(row['event_type'] == 'message.received' for row in rows), [row['event_type'] for row in rows]

    payload = json.loads(rows[-1]['input_json'])
    chain = payload.get('message_chain') or []
    files = [item for item in chain if item.get('type') == 'File']
    assert files, f'no File component in the recorded chain: {chain!r}'
    assert files[-1]['id'] == 'media-e2e-2'
    assert files[-1]['name'] == 'contract.pdf'


def test_recorded_file_component_keeps_the_media_id_when_download_fails(e2e_tmpdir, wecom_bot):
    """The bot's api_base_url is unroutable, so `media/get` fails here.

    The component must still be recorded with name, size and MediaId rather
    than being dropped — the certified seed for a retry.
    """

    response = _post_callback(wecom_bot, 'media-e2e-3', 'unsigned.pdf', nonce='nonce-3')
    assert response.status_code == 200, response.text

    rows = _wait_for_rows(e2e_tmpdir, wecom_bot['uuid'], 3)
    payload = json.loads(rows[-1]['input_json'])
    files = [item for item in payload.get('message_chain') or [] if item.get('type') == 'File']
    assert files, f'no File component recorded: {payload.get("message_chain")!r}'
    assert files[-1]['id'] == 'media-e2e-3'
    assert files[-1]['name'] == 'unsigned.pdf'
    assert files[-1]['size'] == len(PDF_BYTES)
