"""Deterministic media checks over real HTTP, installed Runner, Runtime and Artifact storage."""

from __future__ import annotations

import base64
from concurrent.futures import ThreadPoolExecutor
from hashlib import sha256
import json
import os
from pathlib import Path
from queue import Queue
import shutil
import textwrap
import threading

import pytest
import yaml

from tests.e2e import test_artifact_lifecycle_soak as soak
from tests.e2e import test_network_file_plugin_runtime as network
from tests.e2e import test_runner_plugin_runtime as runtime
from tests.utils.artifact_media import make_artifact_media


pytestmark = [
    pytest.mark.e2e,
    pytest.mark.artifact_mixed,
    pytest.mark.contract('mixed_media_runner_lifecycle'),
    pytest.mark.skipif(
        os.environ.get('LANGBOT_ARTIFACT_MIXED_E2E') != '1', reason='explicit full-process mixed media test'
    ),
]

network_process_env = network.network_process_env
runner_e2e_tmpdir = network.runner_e2e_tmpdir
runner_e2e_port = runtime.runner_e2e_port
runner_runtime_ports = runtime.runner_runtime_ports
base_network_config = network.runner_e2e_config_path
runner_langbot_process = network.runner_langbot_process
runner_client = runtime.runner_client
_data = network._data


# This is a real SDK Runner in a separately started Runtime. It returns digests
# and extracted text, never passing expected media bytes or markers as inputs.
_RUNNER = """\
import asyncio
import base64
from hashlib import sha256
import json
import shlex

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult


class DefaultRunner(Runner):
    @staticmethod
    def report(ctx, prefix, report):
        return RunnerResult.message_completed(ctx.run_id, Message(role='assistant', content=prefix + json.dumps(report)))

    @staticmethod
    def media(content, kind, mime):
        assert content['type'] == kind, content['type']
        header, encoded = content[kind].split(',', 1)
        assert header == 'data:' + mime + ';base64', header
        body = base64.b64decode(encoded, validate=True)
        return {'sha256': sha256(body).hexdigest(), 'size': len(body)}

    async def run(self, ctx):
        request, _ = json.JSONDecoder().raw_decode(ctx.input.to_text().lstrip())
        report = {'run_id': ctx.run_id, 'attachments': []}
        try:
            for attachment in ctx.input.attachments:
                assert attachment.ref and not any((attachment.content, attachment.url, attachment.path))
                ref = attachment.ref
                mime = attachment.mime_type
                if ref in request.get('bad_pdf', []):
                    for mode in ('native', 'text'):
                        try:
                            await ctx.read_input_attachment_content(ref, mode=mode)
                        except Exception as error:
                            report.setdefault('rejected_pdfs', {}).setdefault(ref, {})[mode] = str(error)
                        else:
                            raise AssertionError('Invalid PDF unexpectedly readable in ' + mode + ' mode')
                    continue
                native = await ctx.read_input_attachment_content(ref, mode='native')
                metadata = json.loads(native[0]['text'])
                assert metadata['artifact']['id'] == ref and metadata['artifact']['ref'] == ref, metadata
                assert metadata['artifact']['name'] == attachment.name, metadata
                entry = {'id': ref, 'name': attachment.name, 'mime': mime, 'mode': metadata['mode']}
                if mime == 'application/pdf':
                    entry.update(self.media(native[1], 'file_base64', mime))
                    first = json.loads((await ctx.read_input_attachment_content(ref, mode='text', max_chars=11))[0]['text'])
                    entry['text_only'] = first['text_only']
                    entry['notice'] = first['notice']
                    entry['pages'] = first['page_count']
                    entry['text'] = first['text']
                    if first['truncated']:
                        more = await ctx.read_input_attachment_content(ref, mode='text', offset=first['next_offset'])
                        more = json.loads(more[0]['text'])
                        assert not more['truncated'], more
                        entry['text'] += more['text']
                    if request.get('unsupported'):
                        try:
                            await ctx.read_input_attachment_content(ref, mode='pages')
                        except Exception as error:
                            entry['unsupported'] = str(error)
                        else:
                            raise AssertionError('Unsupported page rendering reported success')
                else:
                    entry.update(self.media(native[1], 'image_base64', mime))
                assert metadata['artifact']['digest'] == entry['sha256'], metadata
                assert metadata['artifact']['size'] == entry['size'] == attachment.size, metadata
                report['attachments'].append(entry)
            for absent in request.get('deny', []):
                try:
                    await ctx.read_input_attachment_content(absent, mode='native')
                except Exception as error:
                    report.setdefault('denied', {})[absent] = str(error)
                else:
                    raise AssertionError('A ref not bound to this run was readable')
            if request.get('hold'):
                yield self.report(ctx, 'MIXED_STAGE ', report)
                await asyncio.sleep(request['hold'])
                shared = await ctx.read_input_attachment_content(request['shared'], mode='native')
                report['shared_after_gc'] = self.media(shared[1], 'image_base64', 'image/jpeg')
            if request.get('export'):
                box_status = await ctx.api.get_box_status()
                box = await ctx.api.acquire_box(box_status.required_reuse_key or ctx.config['reuse_key'])
                await ctx.bind_box(box.id)
                path = '/workspace/' + ctx.run_id + '-media-manifest.json'
                entries = [{'id': item['id'], 'sha256': item['sha256']} for item in report['attachments']]
                command = 'printf %s ' + shlex.quote(json.dumps(entries, sort_keys=True)) + ' > ' + shlex.quote(path)
                execution = await ctx.call_tool('exec', {'command': command, 'timeout_sec': 10})
                assert execution['ok'], execution
                exported = (await ctx.export_box_files([path]))[0]
                assert exported.artifact_id and not exported.warning, exported
                out = json.loads((await ctx.read_run_file(exported.id, mode='text'))[0]['text'])
                assert out['text'] == json.dumps(entries, sort_keys=True), out
                committed = (await ctx.commit_run_files([exported.id]))[0]
                assert committed.lifecycle == 'persistent' and committed.artifact_id == exported.artifact_id, committed
                report['output'] = {'id': committed.artifact_id, 'file_id': exported.id}
        except Exception as error:
            report['error'] = type(error).__name__ + ': ' + str(error)
        yield self.report(ctx, 'MIXED_DONE ', report)
        yield RunnerResult.run_completed(ctx.run_id, finish_reason='stop')
"""


@pytest.fixture(scope='session')
def runner_runtime_process(runner_e2e_tmpdir, runner_runtime_ports):
    # Core and Runtime each use a distinct cwd and transfer location. Only
    # the registered plugin's real WebSocket protocol bridges requester and worker.
    directory = runner_e2e_tmpdir / 'separate-runtime'
    directory.mkdir()
    instance = soak.RuntimeProcess(directory, runner_runtime_ports)
    with pytest.MonkeyPatch.context() as patch:
        patch.setenv('LANGBOT_PLUGIN_FILE_STORAGE_DIR', str(directory / 'rpc-transfers'))
        instance.start()
    try:
        yield instance
    finally:
        instance.stop()


@pytest.fixture(scope='session')
def runner_e2e_config_path(base_network_config, runner_e2e_tmpdir):
    assert os.environ.get('LANGBOT_CORE_NETWORK_BACKEND', 'host') == 'host', 'mixed lane currently uses the host Box'
    config = yaml.safe_load(base_network_config.read_text())
    config['storage'].update(use='persistent', content={'backend': 'database'})
    base_network_config.write_text(yaml.safe_dump(config), encoding='utf-8')
    plugin = runner_e2e_tmpdir / 'agent-runner-qa-package'
    (plugin / 'components/runner/default.py').write_text(textwrap.dedent(_RUNNER), encoding='utf-8')
    shutil.make_archive(str(runner_e2e_tmpdir / 'agent-runner-qa'), 'zip', root_dir=plugin)
    return base_network_config


def _url(ref, suffix=''):
    return '/api/v1/artifacts/' + ref + suffix


def _post_refs(client, agent, headers, conversation, files=(), **command):
    return client.post(
        f'/api/v1/agents/{agent}/debug',
        headers=headers,
        json={'text': json.dumps(command), 'conversation_id': conversation, 'artifact_ids': list(files)},
    )


def _run_turn(client, agent, headers, conversation, files=(), *, stage=None, **command):
    report = None
    with client.stream(
        'POST',
        f'/api/v1/agents/{agent}/debug/stream',
        headers=headers,
        json={'text': json.dumps(command), 'conversation_id': conversation, 'artifact_ids': list(files)},
        timeout=65,
    ) as response:
        assert response.status_code == 200, response.read()
        for line in response.iter_lines():
            if not line:
                continue
            frame = json.loads(line)
            assert frame.get('kind') != 'error', frame
            seen = soak._report(frame, 'MIXED_STAGE ')
            if seen is not None:
                assert stage is not None
                stage.put(seen)
            done = soak._report(frame, 'MIXED_DONE ')
            if done is not None:
                assert report is None, done
                report = done
    assert report is not None and 'error' not in report, report
    return report


def _assert_media(report, fixtures):
    records = {value['id']: value for value in report['attachments']}
    assert len(records) == len(report['attachments']) == len(fixtures), report
    for ref, media in fixtures.items():
        result = records[ref]
        assert (result['name'], result['mime'], result['sha256'], result['size']) == (
            media.filename,
            media.mime_type,
            media.sha256,
            len(media.data),
        )
        if media.mime_type == 'application/pdf':
            assert result['mode'] == 'native' and result['pages'] == 1
            assert result['text_only'] and 'excludes images' in result['notice']
            if media.kind == 'text_pdf':
                assert media.marker in result['text']
            else:
                assert media.marker not in result['text'] and result['text'].strip() == '[Page 1]'
        else:
            assert result['mode'] == 'image'


def test_real_mixed_media_sessions_and_published_output(
    runner_client, runner_langbot_process, runner_e2e_tmpdir, runner_e2e_config_path
):
    client, core = runner_client, runner_langbot_process
    token = runtime._init_and_auth(client)
    core.token = token
    headers = soak._headers(token)
    runtime._ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    observer = soak.StoreObserver(yaml.safe_load(runner_e2e_config_path.read_text()))
    workspace = observer.query("SELECT uuid FROM workspaces WHERE source='local'")[0]['uuid']

    def upload(media, principal=headers):
        meta = _data(
            client.post(
                '/api/v1/artifacts', headers=principal, files={'file': (media.filename, media.data, media.mime_type)}
            )
        )
        assert meta['digest'] == media.sha256 and meta['size'] == len(media.data), meta
        assert media.marker not in json.dumps(meta), meta
        return meta['id']

    agent = soak._agent(client, headers, timeout=20)
    soak._policy(client, headers, agent)
    groups = [{upload(media): media for media in make_artifact_media(name)} for name in ('alpha', 'beta')]
    by_name = [{media.filename: media.sha256 for media in group.values()} for group in groups]
    assert by_name[0].keys() == by_name[1].keys()
    assert all(by_name[0][name] != by_name[1][name] for name in by_name[0])
    shared_media = next(item for item in groups[0].values() if item.kind == 'jpeg')
    shared = upload(shared_media)
    _data(client.post(_url(shared, '/retain'), headers=headers))

    # The same bytes uploaded by a different authenticated principal create
    # independent authorization even before/after serving from the same store.
    invitation = _data(
        client.post(
            f'/api/v1/workspaces/{workspace}/invitations',
            headers=headers,
            json={'email': 'mixed-second@langbot.test', 'role': 'developer'},
        )
    )
    _data(
        client.post(
            '/api/v1/invitations/accept',
            json={
                'token': invitation['token'],
                'registration': {'email': 'mixed-second@langbot.test', 'password': 'mixed-local-password'},
            },
        )
    )
    second_token = _data(
        client.post('/api/v1/user/auth', json={'user': 'mixed-second@langbot.test', 'password': 'mixed-local-password'})
    )['token']
    second = soak._headers(second_token, workspace)
    assert _data(client.get('/api/v1/workspaces/current', headers=second))['workspace']['uuid'] == workspace
    duplicate = upload(shared_media, second)
    assert shared != duplicate
    assert client.get(_url(shared, '/content'), headers=headers).content == shared_media.data
    assert client.get(_url(duplicate, '/content'), headers=second).content == shared_media.data
    assert client.get(_url(shared, '/content'), headers=second).status_code == 404
    assert client.get(_url(duplicate, '/content'), headers=headers).status_code == 404

    # Validate overlap via actual run pins, not just concurrently issued HTTP
    # requests. Releasing and expiring the public source cannot evict live reads.
    stages = Queue()
    barrier = threading.Barrier(2)

    def start(position):
        barrier.wait(timeout=10)
        return _run_turn(
            client,
            agent,
            headers,
            ('alpha', 'beta')[position],
            [*groups[position], shared],
            stage=stages,
            hold=6,
            shared=shared,
            deny=[next(iter(groups[1 - position]))],
            unsupported=True,
        )

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(start, position) for position in range(2)]
        staged = [stages.get(timeout=25) for _ in futures]
        run_ids = {row['run_id'] for row in staged}
        pins = observer.query(
            "SELECT holder_id FROM artifact_references WHERE artifact_id=:ref AND holder_type='run_input'",
            {'ref': shared},
        )
        assert {row['holder_id'] for row in pins} == run_ids and len(run_ids) == 2, pins
        scopes = observer.query(
            "SELECT run_id, conversation_id, workspace_id, status FROM agent_run WHERE status='running'"
        )
        assert {row['run_id'] for row in scopes} == run_ids, scopes
        assert {row['conversation_id'] for row in scopes} == {'alpha', 'beta'}, scopes
        assert {row['workspace_id'] for row in scopes} == {workspace}, scopes
        assert _data(client.post(_url(shared, '/release'), headers=headers))['lifecycle'] == 'temporary'
        observer.accelerate_expiry([shared])
        observer.gc()
        assert client.get(_url(shared, '/content'), headers=headers).status_code == 410
        expired = _post_refs(client, agent, headers, 'new', [shared])
        assert expired.status_code == 410 and expired.json()['code'] == 'artifact_expired', expired.text
        assert len(observer.query('SELECT id FROM artifacts WHERE id=:ref', {'ref': shared})) == 1
        results = [future.result(timeout=25) for future in futures]
    for position, report in enumerate(results):
        _assert_media(report, {**groups[position], shared: shared_media})
        assert report['shared_after_gc'] == {'sha256': shared_media.sha256, 'size': len(shared_media.data)}
        assert list(report['denied']) == [next(iter(groups[1 - position]))]
        assert all(
            'rendering is unavailable' in item['unsupported']
            for item in report['attachments']
            if item['mode'] == 'native'
        )
    observer.gc()
    assert client.get(_url(shared), headers=headers).status_code == 404
    assert client.get(_url(duplicate, '/content'), headers=second).content == shared_media.data

    old_ref = next(iter(groups[0]))
    valid_pdf = next(media for media in groups[0].values() if media.kind == 'text_pdf')
    damaged = [
        _data(
            client.post(
                '/api/v1/artifacts',
                headers=headers,
                files={'file': ('invalid.pdf', data, 'application/pdf')},
            )
        )['id']
        for data in (valid_pdf.data[:60], b'Plain text falsely declared as PDF')
    ]
    valid_amid_invalid = _run_turn(
        client,
        agent,
        headers,
        'beta',
        [*damaged, old_ref],
        bad_pdf=damaged,
    )
    _assert_media(valid_amid_invalid, {old_ref: groups[0][old_ref]})
    assert set(valid_amid_invalid['rejected_pdfs']) == set(damaged)
    for failures in valid_amid_invalid['rejected_pdfs'].values():
        assert set(failures) == {'native', 'text'}
        assert all('PDF could not be read' in message for message in failures.values()), failures
    text = _run_turn(client, agent, headers, 'alpha', deny=[old_ref])
    assert not text['attachments'] and set(text['denied']) == {old_ref}
    later = _run_turn(client, agent, headers, 'alpha', [old_ref], export=True)
    _assert_media(later, {old_ref: groups[0][old_ref]})
    output = later['output']['id']
    expected = json.dumps([{'id': old_ref, 'sha256': groups[0][old_ref].sha256}], sort_keys=True).encode()
    meta = _data(client.get(_url(output), headers=headers))
    assert meta['lifecycle'] == 'persistent' and meta['digest'] == sha256(expected).hexdigest()
    assert client.get(_url(output, '/content'), headers=headers).content == expected
    assert client.delete(_url(output), headers=headers).status_code == 409
    assert client.get(_url(output, '/content'), headers=second).status_code == 404
    cross_run = _post_refs(client, agent, headers, 'alpha', [duplicate])
    assert cross_run.status_code == 404 and cross_run.json()['code'] == 'resource_not_found', cross_run.text
    with client.stream(
        'POST',
        f'/api/v1/agents/{agent}/debug/stream',
        headers=headers,
        json={'text': '{}', 'conversation_id': 'alpha', 'artifact_ids': [duplicate]},
    ) as response:
        assert response.status_code == 200, response.read()
        stream_frames = [json.loads(line) for line in response.iter_lines() if line]
    assert stream_frames == [{'kind': 'error', 'code': 'resource_not_found', 'msg': 'Resource not found'}], (
        stream_frames
    )

    account = observer.query("SELECT uuid FROM users WHERE normalized_email='mixed-second@langbot.test'")[0]['uuid']
    other = observer.seed_foreign_workspace(account)
    try:
        foreign = soak._headers(second_token, other)
        assert _data(client.get('/api/v1/workspaces/current', headers=foreign))['workspace']['uuid'] == other
        assert client.get(_url(duplicate, '/content'), headers=foreign).status_code == 404
        assert client.get(_url(output, '/content'), headers=foreign).status_code == 404
    finally:
        observer.remove_foreign_workspace(other)

    core.stop()
    for logfile in ('langbot.stdout.log', 'langbot.stderr.log'):
        shutil.copyfile(runner_e2e_tmpdir / logfile, runner_e2e_tmpdir / ('before-restart-' + logfile))
    assert core.start(), core.get_logs()
    assert runtime.QA_RUNNER_ID in runtime._wait_for_qa_runner(client, token)
    assert client.get(_url(output, '/content'), headers=headers).content == expected
    assert client.get(_url(output, '/content'), headers=second).status_code == 404
    again = _run_turn(client, agent, headers, 'alpha', [old_ref])
    _assert_media(again, {old_ref: groups[0][old_ref]})

    for ref in [*groups[0], *groups[1], *damaged, output]:
        if ref == output:
            first = _data(client.post(_url(ref, '/release'), headers=headers))
            next_release = _data(client.post(_url(ref, '/release'), headers=headers))
            assert first['lifecycle'] == 'temporary' and first['expires_at'] == next_release['expires_at']
        _data(client.delete(_url(ref), headers=headers))
    _data(client.delete(_url(duplicate), headers=second))
    observer.gc()
    counts = observer.snapshot()
    assert counts['artifacts'] == counts['artifact_references'] == counts['content_objects'] == 0, counts

    # The bytes traveled over SDK RPC but never traveled as an inline input,
    # an ordinary log body or persisted run event data.
    history = str(
        observer.query('SELECT * FROM agent_run')
        + observer.query('SELECT data_json, metadata_json FROM agent_run_event')
    )
    runtime_logs = [*Path(runner_e2e_tmpdir).glob('*.log'), *Path(runner_e2e_tmpdir).glob('separate-runtime/*.log')]
    for media in (item for group in groups for item in group.values()):
        encoded = base64.b64encode(media.data).decode('ascii')
        probe = encoded[128:288]
        assert len(probe) == 160 and probe not in history
        for log in runtime_logs:
            assert probe not in log.read_text(encoding='utf-8', errors='replace'), log.name
