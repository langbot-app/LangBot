"""Opt-in lifecycle soak through TCP Core -> installed Runner -> Runtime -> Box.

Each process owns its database, bucket and runtime tree. The GC observer invokes
the real ArtifactService on that same store. Expiry acceleration changes only
test-owned rows and is recorded explicitly; it does not simulate a 24-hour wait.
"""

from __future__ import annotations

import asyncio
import base64
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing
import datetime as dt
import hashlib
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import math
import os
from pathlib import Path
import random
import shutil
import signal
import statistics
import subprocess
import sys
import textwrap
import threading
import time
from types import SimpleNamespace
import uuid

import psutil
import pytest
import sqlalchemy as sa
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
import yaml

from tests.e2e import test_network_file_plugin_runtime as network
from tests.e2e import test_runner_plugin_runtime as runtime

pytestmark = [
    pytest.mark.e2e,
    pytest.mark.network_plugin,
    pytest.mark.skipif(os.environ.get('LANGBOT_ARTIFACT_SOAK') != '1', reason='explicit full-process lifecycle soak'),
]

network_process_env = network.network_process_env
runner_e2e_tmpdir = network.runner_e2e_tmpdir
runner_e2e_port = runtime.runner_e2e_port
runner_runtime_ports = runtime.runner_runtime_ports
base_network_config = network.runner_e2e_config_path
runner_langbot_process = network.runner_langbot_process
runner_client = runtime.runner_client
_data = network._data


# This Runner uses production SDK APIs only. No Host handler or database call is
# replaced. Read-only directories are a real sandbox cleanup failure stimulus.
_RUNNER = """\
import asyncio
import base64
import hashlib
import json
import shlex
from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.runner.result import RunnerResult
from langbot_plugin.api.entities.builtin.provider.message import Message

class DefaultRunner(Runner):
    async def run(self, ctx):
        request, _ = json.JSONDecoder().raw_decode(ctx.input.to_text().lstrip())
        report = {'run_id': ctx.run_id, 'operation': request['operation']}
        try:
            status = await ctx.api.get_box_status()
            box = await ctx.api.acquire_box(status.required_reuse_key or str(request.get('box_slot', ctx.config['reuse_key'])))
            await ctx.bind_box(box.id)
            report['box_id'] = box.id
            if request['operation'] == 'mixed':
                report['inputs'] = []
                for attachment in ctx.input.attachments:
                    ref = attachment.ref
                    # Platform attachments materialize only on a structured read.
                    # Verify bounded extraction before the additional cached raw read.
                    is_text_pdf = attachment.name == 'reference.pdf'
                    options = {'mode': 'text', 'max_chars': 11} if is_text_pdf else {'mode': 'native'}
                    items = await ctx.read_input_attachment_content(ref, **options)
                    metadata = json.loads(items[0]['text'])
                    asset = metadata['artifact']
                    assert asset['ref'] == ref and asset['id'] != ref, asset
                    entry = {'ref': ref, 'id': asset['id'], 'name': asset['name'],
                             'mode': metadata['mode'], 'mime': asset['mime_type']}
                    if is_text_pdf:
                        assert metadata['truncated'] and metadata['offset'] == 0 and len(metadata['text']) == 11
                        assert metadata['next_offset'] == 11, metadata
                        tail = json.loads((await ctx.read_input_attachment_content(
                            ref, mode='text', offset=metadata['next_offset']
                        ))[0]['text'])
                        assert tail['offset'] == 11 and tail['next_offset'] is None and not tail['truncated'], tail
                        assert tail['artifact']['id'] == asset['id'] and tail['page_count'] == metadata['page_count'] == 1
                        entry['text'] = metadata['text'] + tail['text']
                        entry['continuation'] = True
                        raw = await ctx.read_input_attachment(attachment)
                        assert raw is not None and raw.ref == ref
                        body = raw.data
                    else:
                        field = 'file_base64' if asset['mime_type'] == 'application/pdf' else 'image_base64'
                        assert len(items) == 2 and items[1]['type'] == field, items[0]
                        header, encoded = items[1][field].split(',', 1)
                        assert header == 'data:' + asset['mime_type'] + ';base64', header
                        body = base64.b64decode(encoded, validate=True)
                    entry.update(sha256=hashlib.sha256(body).hexdigest(), size=len(body))
                    assert entry['sha256'] == asset['digest'] and entry['size'] == asset['size']
                    report['inputs'].append(entry)
                if report['inputs']:
                    first = (await ctx.import_box_attachments([report['inputs'][0]['ref']]))[0]
                    output = '/workspace/mixed-' + ctx.run_id + '.bin'
                    made = await ctx.call_tool('exec', {'command': 'cp ' + shlex.quote(first.path) + ' ' +
                                                                  shlex.quote(output), 'timeout_sec': 15})
                    assert made['ok'], made
                    binary, = await ctx.export_box_files([output])
                    saved, = await ctx.commit_run_files([binary.id])
                    assert saved.lifecycle == 'persistent', saved
                    report['artifact_id'] = binary.artifact_id
                    await ctx.reply_files([binary.id])
            elif request['operation'] == 'foreign-file':
                for method in ('read_run_file', 'commit_run_files', 'reply_files'):
                    try:
                        argument = request['file_id'] if method == 'read_run_file' else [request['file_id']]
                        await getattr(ctx, method)(argument)
                    except Exception:
                        report[method + '_denied'] = True
            else:
                imported = await ctx.import_box_attachments()
                assert len(imported) == 1, imported
                directory = '/workspace/artifact-soak-' + ctx.run_id
                output = directory + '/payload.bin'
                text = directory + '/probe.txt'
                probe = 'Soak 甲乙😀丁 ' + request['nonce']
                command = ('mkdir -p ' + shlex.quote(directory) + ' && cp ' + shlex.quote(imported[0].path) +
                           ' ' + shlex.quote(output) + ' && printf %s ' + shlex.quote(probe) +
                           ' > ' + shlex.quote(text))
                if request['operation'] == 'cleanup-failure':
                    command += ' && chmod 555 ' + shlex.quote(directory)
                made = await ctx.call_tool('exec', {'command': command, 'timeout_sec': 15})
                assert made['ok'], made
                exported = await ctx.export_box_files([output, text])
                binary = next(item for item in exported if item.name == 'payload.bin')
                textual = next(item for item in exported if item.name == 'probe.txt')
                report.update(file_id=binary.id, artifact_id=binary.artifact_id,
                              text_artifact_id=textual.artifact_id, probe=probe,
                              cleanup_warning=bool(binary.warning or textual.warning))
                first = json.loads((await ctx.read_run_file(textual.id, max_chars=5))[0]['text'])
                rest = json.loads((await ctx.read_run_file(textual.id, offset=first['next_offset']))[0]['text'])
                assert first['text'] + rest['text'] == probe
                if request.get('commit', True):
                    for _ in range(2):
                        saved = await ctx.commit_run_files([binary.id, textual.id])
                        assert all(item.lifecycle == 'persistent' for item in saved), saved
                    report['committed'] = True
                if request['operation'] != 'cleanup-failure':
                    removed = await ctx.call_tool('exec', {'command': 'rmdir ' + shlex.quote(directory), 'timeout_sec': 10})
                    assert removed['ok'], removed
                if request.get('debug'):
                    yield RunnerResult.message_completed(ctx.run_id, Message(role='assistant', content='SOAK_STAGE ' + json.dumps(report)))
                if request.get('hold'):
                    await asyncio.sleep(request['hold'])
                    again = json.loads((await ctx.read_run_file(textual.id))[0]['text'])
                    assert again['text'] == probe, again
                    report['active_read'] = True
                if not request.get('debug'):
                    await ctx.reply_files([binary.id])
                    try:
                        await ctx.reply_files([binary.id])
                    except Exception:
                        report['repeat_reply_denied'] = True
                    else:
                        raise AssertionError('Duplicate delivery accepted')
                if request['operation'] == 'cleanup-failure':
                    fixed = await ctx.call_tool('exec', {'command': 'chmod 755 ' + shlex.quote(directory) +
                                                ' && rm -rf ' + shlex.quote(directory), 'timeout_sec': 10})
                    assert fixed['ok'], fixed
        except Exception as error:
            report['error'] = type(error).__name__ + ': ' + str(error)
        if request.get('debug'):
            yield RunnerResult.message_completed(ctx.run_id, Message(role='assistant', content='SOAK_DONE ' + json.dumps(report)))
        else:
            await ctx.reply('NETWORK_E2E ' + json.dumps(report))
        yield RunnerResult.run_completed(ctx.run_id, finish_reason='stop')
"""


def _run(coroutine):
    return asyncio.run(coroutine)


@pytest.fixture
def file_source():
    state = SimpleNamespace(body=os.urandom(2 * 1024 * 1024), requests=[], mixed={}, mixed_requests=0)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path == '/input.bin':
                content, mime = state.body, 'application/octet-stream'
                state.requests.append({'utc': dt.datetime.now(dt.timezone.utc).isoformat(), 'bytes': len(content)})
            elif (fixture := state.mixed.get(self.path)) is not None:
                content, mime = fixture.data, fixture.mime_type
                state.mixed_requests += 1
            else:
                self.send_error(404)
                return
            self.send_response(200)
            self.send_header('Content-Type', mime)
            self.send_header('Content-Length', str(len(content)))
            self.end_headers()
            self.wfile.write(content)

        def do_POST(self):
            self.send_error(500, 'Sync delivery must not fall back to callback')

        def log_message(self, *_args):
            pass

    server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
    state.url = f'http://127.0.0.1:{server.server_port}'
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield state
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)
        assert not thread.is_alive()


class StoreObserver:
    """Real production storage services plus narrowly scoped test clock control."""

    def __init__(self, config):
        self.config = config
        self.url = (
            config['database']['postgresql']['url']
            if config['database']['use'] == 'postgresql'
            else 'sqlite+aiosqlite:///' + config['database']['sqlite']['path']
        )

    def _engine(self):
        engine = create_async_engine(self.url, poolclass=NullPool)
        if engine.dialect.name == 'sqlite':

            @sa.event.listens_for(engine.sync_engine, 'connect')
            def foreign_keys(connection, _record):
                cursor = connection.cursor()
                cursor.execute('PRAGMA foreign_keys=ON')
                cursor.close()

        return engine

    async def sql(self, statement, values=None):
        engine = self._engine()
        try:
            async with engine.begin() as connection:
                result = await connection.execute(sa.text(statement), values or {})
                return [dict(row) for row in result.mappings()] if result.returns_rows else []
        finally:
            await engine.dispose()

    def query(self, statement, values=None):
        return _run(self.sql(statement, values))

    def accelerate_expiry(self, artifact_ids):
        now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) - dt.timedelta(seconds=1)
        for artifact_id in artifact_ids:
            self.query('UPDATE artifacts SET expires_at=:now WHERE id=:id', {'now': now, 'id': artifact_id})

    async def collect(self):
        from langbot.pkg.api.context import ExecutionContext, PrincipalContext, PrincipalType
        from langbot.pkg.persistence.mgr import PersistenceManager
        from langbot.pkg.storage.artifacts import ArtifactService
        from langbot.pkg.storage.content import ContentStore
        from langbot.pkg.workspace.service import WorkspaceService

        engine = self._engine()
        application = SimpleNamespace(
            instance_config=SimpleNamespace(data=self.config), logger=logging.getLogger('soak-gc')
        )
        application.persistence_mgr = PersistenceManager(application)
        application.persistence_mgr.db = SimpleNamespace(get_engine=lambda: engine)
        async with engine.connect() as connection:
            rows = (await connection.execute(sa.text('SELECT uuid, instance_uuid FROM workspaces'))).mappings().all()
        store = ContentStore(application)
        application.storage_mgr = SimpleNamespace(content_store=store)
        total = 0
        try:
            for row in rows:
                application.workspace_service = WorkspaceService(application, instance_uuid=row['instance_uuid'])
                binding = await application.workspace_service.get_execution_binding(row['uuid'])
                context = ExecutionContext(
                    binding.instance_uuid,
                    row['uuid'],
                    binding.placement_generation,
                    trigger_principal=PrincipalContext(PrincipalType.SYSTEM),
                )
                total += await ArtifactService(application).collect_expired(context, limit=1000)
            return total
        finally:
            await store.shutdown()
            await engine.dispose()

    def gc(self):
        return _run(self.collect())

    def snapshot(self):
        values = {}
        for table, condition in (
            ('artifacts', ''),
            ('artifact_references', ''),
            ('content_objects', " WHERE owner_type='artifact'"),
        ):
            values[table] = self.query(f'SELECT COUNT(*) AS n FROM {table}{condition}')[0]['n']
        values['live_runs'] = self.query("SELECT COUNT(*) AS n FROM agent_run WHERE status='running'")[0]['n']
        if self.url.startswith('postgresql'):
            values['db_connections'] = self.query(
                'SELECT COUNT(*) AS n FROM pg_stat_activity WHERE datname=current_database()'
            )[0]['n']
        else:
            path = Path(self.config['database']['sqlite']['path'])
            values['sqlite_bytes'] = path.stat().st_size
            wal = Path(str(path) + '-wal')
            values['sqlite_wal_bytes'] = wal.stat().st_size if wal.exists() else 0
        if self.config['storage']['content']['backend'] != 'database':
            import boto3

            backend = self.config['storage']['content']['backends']['archive']
            with closing(
                boto3.client(
                    's3',
                    endpoint_url=backend['endpoint_url'],
                    aws_access_key_id=backend['access_key_id'],
                    aws_secret_access_key=backend['secret_access_key'],
                    region_name=backend['region'],
                )
            ) as client:
                pages = client.get_paginator('list_objects_v2').paginate(Bucket=backend['bucket'])
                objects = [item for page in pages for item in page.get('Contents', [])]
            values['object_count'] = len(objects)
            values['object_bytes'] = sum(item['Size'] for item in objects)
        return values

    def seed_foreign_workspace(self, account_uuid):
        """Seed owned QA tenant records; HTTP still uses the real auth factories."""
        from langbot.pkg.entity.persistence.workspace import Workspace, WorkspaceExecutionState, WorkspaceMembership

        async def seed():
            engine = self._engine()
            try:
                async with engine.begin() as connection:
                    instance = (await connection.execute(sa.select(Workspace.instance_uuid))).scalar_one()
                    workspace = str(uuid.uuid4())
                    await connection.execute(
                        sa.insert(Workspace).values(
                            uuid=workspace,
                            instance_uuid=instance,
                            name='Soak isolation tenant',
                            slug='soak-' + uuid.uuid4().hex,
                            source='cloud_projection',
                        )
                    )
                    await connection.execute(
                        sa.insert(WorkspaceExecutionState).values(
                            workspace_uuid=workspace, instance_uuid=instance, source='cloud'
                        )
                    )
                    await connection.execute(
                        sa.insert(WorkspaceMembership).values(
                            workspace_uuid=workspace, account_uuid=account_uuid, role='developer', status='active'
                        )
                    )
                    return workspace
            finally:
                await engine.dispose()

        return _run(seed())

    def remove_foreign_workspace(self, workspace):
        for table, column in (
            ('workspace_memberships', 'workspace_uuid'),
            ('workspace_execution_states', 'workspace_uuid'),
            ('workspaces', 'uuid'),
        ):
            self.query(f'DELETE FROM {table} WHERE {column}=:workspace', {'workspace': workspace})


class RuntimeProcess:
    def __init__(self, directory, ports):
        self.directory, self.ports, self.process, self.files = directory, ports, None, []
        self.generation = 0

    def start(self):
        self.generation += 1
        self.files = [
            open(self.directory / f'soak-runtime-{self.generation}.{kind}.log', 'wb') for kind in ('stdout', 'stderr')
        ]
        self.process = subprocess.Popen(
            [
                sys.executable,
                '-m',
                'langbot_plugin.cli.__init__',
                'rt',
                '--ws-control-port',
                str(self.ports[0]),
                '--ws-debug-port',
                str(self.ports[1]),
            ],
            cwd=self.directory,
            stdout=self.files[0],
            stderr=self.files[1],
            start_new_session=True,
        )

    def stop(self):
        if self.process is not None and self.process.poll() is None:
            os.killpg(self.process.pid, signal.SIGTERM)
            try:
                self.process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                os.killpg(self.process.pid, signal.SIGKILL)
                self.process.wait(timeout=5)
        for stream in self.files:
            stream.close()


@pytest.fixture(scope='session')
def runner_runtime_process(runner_e2e_tmpdir, runner_runtime_ports):
    runtime_process = RuntimeProcess(runner_e2e_tmpdir, runner_runtime_ports)
    runtime_process.start()
    try:
        yield runtime_process
    finally:
        runtime_process.stop()


def _artifact_soak_profile():
    root = Path(__file__).resolve().parents[2]
    path = Path(os.environ.get('LANGBOT_SOAK_PROFILE', root / 'tools/profiles/artifact-soak.json'))
    return path.read_bytes()


@pytest.fixture(scope='session')
def runner_e2e_config_path(base_network_config, runner_e2e_tmpdir, request):
    lane = os.environ.get('LANGBOT_SOAK_LANE', 'sqlite-database')
    assert lane in {'sqlite-database', 'postgres-database', 'postgres-minio'}
    config = yaml.safe_load(base_network_config.read_text())
    config['storage'].update(use='persistent', content={'backend': 'database'})
    if os.environ.get('LANGBOT_SOAK_MIXED_MODE') in {'short', 'staircase', 'accelerated'}:
        config['box']['limits']['max_sessions'] = 4
        if os.environ['LANGBOT_SOAK_MIXED_MODE'] == 'accelerated':
            nominal = json.loads(_artifact_soak_profile())['accelerated']
            config['storage']['cleanup'].update(
                enabled=True, check_interval_hours=nominal['gc_interval_seconds'] / 3600
            )
    queue = os.environ.get('LANGBOT_SOAK_SQLITE_WRITE_QUEUE')
    if queue is not None:
        assert lane == 'sqlite-database' and queue in {'on', 'off', 'artifact_ledger'}
        config['database']['sqlite']['experimental_write_queue'] = (
            'artifact_ledger' if queue == 'artifact_ledger' else queue == 'on'
        )
        config['database']['sqlite']['experimental_write_timing'] = os.environ.get('LANGBOT_SOAK_WRITE_TIMING') == '1'
    admin_url = None
    database = None
    s3 = None
    bucket = None
    if lane.startswith('postgres'):
        admin_url = sa.engine.make_url(os.environ['LANGBOT_PERSISTENCE_POSTGRES_URL'])
        database = 'artifact_soak_' + uuid.uuid4().hex

        async def create_database():
            engine = create_async_engine(admin_url, isolation_level='AUTOCOMMIT')
            try:
                async with engine.connect() as connection:
                    await connection.execute(sa.text('CREATE DATABASE ' + database))
            finally:
                await engine.dispose()

        _run(create_database())
        config['database']['use'] = 'postgresql'
        config['database']['postgresql']['url'] = admin_url.set(database=database).render_as_string(hide_password=False)
    if lane == 'postgres-minio':
        import boto3
        from botocore.config import Config

        bucket = 'artifact-soak-' + uuid.uuid4().hex
        backend = {
            'type': 's3',
            'endpoint_url': os.environ['LANGBOT_PERSISTENCE_MINIO_ENDPOINT'],
            'access_key_id': os.environ['LANGBOT_PERSISTENCE_MINIO_ACCESS_KEY'],
            'secret_access_key': os.environ['LANGBOT_PERSISTENCE_MINIO_SECRET_KEY'],
            'region': 'us-east-1',
            'bucket': bucket,
        }
        s3 = boto3.client(
            's3',
            endpoint_url=backend['endpoint_url'],
            aws_access_key_id=backend['access_key_id'],
            aws_secret_access_key=backend['secret_access_key'],
            region_name=backend['region'],
            config=Config(
                connect_timeout=5, read_timeout=15, retries={'max_attempts': 0}, s3={'addressing_style': 'path'}
            ),
        )
        s3.create_bucket(Bucket=bucket)
        config['storage']['content'] = {'backend': 'archive', 'backends': {'archive': backend}}
    base_network_config.write_text(yaml.safe_dump(config), encoding='utf-8')
    base_network_config.chmod(0o600)
    plugin = runner_e2e_tmpdir / 'agent-runner-qa-package'
    (plugin / 'components/runner/default.py').write_text(textwrap.dedent(_RUNNER), encoding='utf-8')
    import shutil

    shutil.make_archive(str(runner_e2e_tmpdir / 'agent-runner-qa'), 'zip', root_dir=plugin)
    try:
        yield base_network_config
    finally:
        if request.session.testsfailed == 0:
            if s3 is not None:
                pages = s3.get_paginator('list_objects_v2').paginate(Bucket=bucket)
                keys = {item['Key'] for page in pages for item in page.get('Contents', [])}
                assert not keys, 'Owned soak bucket retained content after successful GC'
                s3.delete_bucket(Bucket=bucket)
            if database:

                async def drop_database():
                    engine = create_async_engine(admin_url, isolation_level='AUTOCOMMIT')
                    try:
                        async with engine.connect() as connection:
                            await connection.execute(sa.text('DROP DATABASE ' + database + ' WITH (FORCE)'))
                    finally:
                        await engine.dispose()

                _run(drop_database())
        if s3 is not None:
            s3.close()


def _headers(token, workspace=None):
    return {'Authorization': 'Bearer ' + token, **({'X-Workspace-Id': workspace} if workspace else {})}


def _policy(client, headers, agent):
    return _data(
        client.put(f'/api/v1/artifacts/producers/agent/{agent}/publication', headers=headers, json={'enabled': True})
    )


def _agent(client, headers, *, timeout=600):
    return _data(
        client.post(
            '/api/v1/agents',
            headers=headers,
            json={
                'kind': 'agent',
                'name': 'Lifecycle soak ' + uuid.uuid4().hex,
                'supported_event_patterns': ['message.*'],
                'config': {
                    'runner': {'id': runtime.QA_RUNNER_ID},
                    'runner_config': {
                        runtime.QA_RUNNER_ID: {'reuse_key': 'lifecycle-soak', 'image': '', 'timeout': timeout}
                    },
                    'allowed_tools': ['exec'],
                    'allowed_platform_tools': ['event_reply'],
                },
            },
        )
    )['uuid']


def _report(frame, prefix):
    data = frame.get('data') or {}
    if frame.get('kind') == 'result' and data.get('type') == 'message.completed':
        message = (data.get('data') or {}).get('message') or {}
        content = message.get('content', '')
        if isinstance(content, str) and content.startswith(prefix):
            return json.loads(content.removeprefix(prefix))
    return None


def _resources(core, plugin_runtime):
    processes = {}
    for process in (core.process, plugin_runtime.process):
        if process is None:
            continue
        try:
            main = psutil.Process(process.pid)
            processes.update({item.pid: item for item in [main, *main.children(recursive=True)]})
        except psutil.NoSuchProcess:
            continue
    result = dict(rss=0, fds=0, threads=0, processes=0, cpu_seconds=0)
    for process in processes.values():
        try:
            result['rss'] += process.memory_info().rss
            result['fds'] += process.num_fds()
            result['threads'] += process.num_threads()
            result['processes'] += 1
            cpu = process.cpu_times()
            result['cpu_seconds'] += cpu.user + cpu.system
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    return result


def _assert_plateau(samples):
    """Compare post-warmup windows within a process generation, not absolute RSS."""
    checked = 0
    for generation in {sample['generation'] for sample in samples}:
        rows = [sample for sample in samples if sample['generation'] == generation]
        if len(rows) < 12:
            continue
        checked += 1
        width = max(3, len(rows) // 4)
        early, late = rows[width : 2 * width], rows[-width:]
        for name, allowance in (('rss', 64 * 1024 * 1024), ('fds', 12), ('threads', 8), ('processes', 2)):
            before = statistics.median(row[name] for row in early)
            after = statistics.median(row[name] for row in late)
            assert after - before <= allowance, (generation, name, before, after, allowance)
    return checked


@pytest.mark.skipif(os.environ.get('LANGBOT_SOAK_MIXED_MODE'), reason='dedicated accelerated lifecycle mode')
def test_artifact_lifecycle_soak(
    runner_client,
    runner_langbot_process,
    runner_runtime_process,
    runner_e2e_tmpdir,
    runner_e2e_config_path,
    file_source,
):
    import hashlib

    client, core, plugin_runtime = runner_client, runner_langbot_process, runner_runtime_process
    config = yaml.safe_load(runner_e2e_config_path.read_text())
    observer = StoreObserver(config)
    lane = os.environ.get('LANGBOT_SOAK_LANE', 'sqlite-database')
    duration = float(os.environ.get('LANGBOT_SOAK_SECONDS', '3600'))
    period = float(os.environ.get('LANGBOT_SOAK_PERIOD', '15'))
    assert duration >= 1 and period > 0
    evidence = Path(os.environ.get('LANGBOT_SOAK_EVIDENCE', str(runner_e2e_tmpdir)))
    evidence.mkdir(parents=True, exist_ok=True)
    journal = evidence / (lane + '.ndjson')
    sequence = 0

    def record(event, **details):
        nonlocal sequence
        sequence += 1
        row = {
            'seq': sequence,
            'utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            'monotonic': time.monotonic(),
            'lane': lane,
            'event': event,
            **details,
        }
        with journal.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        print(json.dumps(row, ensure_ascii=False), flush=True)

    token = runtime._init_and_auth(client)
    core.token = token
    owner = _headers(token)
    runtime._ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    workspace = observer.query("SELECT uuid FROM workspaces WHERE source='local'")[0]['uuid']
    invite = _data(
        client.post(
            f'/api/v1/workspaces/{workspace}/invitations',
            headers=owner,
            json={'email': 'soak-second@langbot.test', 'role': 'developer'},
        )
    )
    _data(
        client.post(
            '/api/v1/invitations/accept',
            json={
                'token': invite['token'],
                'registration': {'email': 'soak-second@langbot.test', 'password': 'soak-account-password'},
            },
        )
    )
    second_token = _data(
        client.post('/api/v1/user/auth', json={'user': 'soak-second@langbot.test', 'password': 'soak-account-password'})
    )['token']
    second = _headers(second_token, workspace)
    account_b = observer.query("SELECT uuid FROM users WHERE normalized_email='soak-second@langbot.test'")[0]['uuid']
    other_workspace = observer.seed_foreign_workspace(account_b)
    foreign_workspace = _headers(second_token, other_workspace)
    assert _data(client.get('/api/v1/workspaces/current', headers=second))['workspace']['uuid'] == workspace
    assert (
        _data(client.get('/api/v1/workspaces/current', headers=foreign_workspace))['workspace']['uuid']
        == other_workspace
    )
    key = _data(client.post('/api/v1/apikeys', headers=owner, json={'name': 'soak-key'}))['key']['key']
    key_headers = _headers(key)
    agent = _agent(client, owner)
    _policy(client, owner, agent)
    assert (
        client.put(
            f'/api/v1/artifacts/producers/agent/{agent}/publication', headers=second, json={'enabled': True}
        ).status_code
        == 404
    )
    key_agent = _agent(client, key_headers)
    _policy(client, key_headers, key_agent)
    timeout_agent = _agent(client, owner, timeout=10)
    _policy(client, owner, timeout_agent)
    source_url, content = file_source.url, file_source.body
    digest = hashlib.sha256(content).hexdigest()
    input_digest, input_size = digest, len(content)
    bot = _data(
        client.post(
            '/api/v1/platform/bots',
            headers=owner,
            json={
                'name': 'Lifecycle soak TCP files',
                'adapter': 'http_bot',
                'enable': True,
                'adapter_config': {
                    'inbound_secret': network._SECRET,
                    'callback_url': source_url + '/no-callback',
                    'signature_required': True,
                    'callback_timeout': 90,
                    'callback_max_retries': 0,
                },
                'event_bindings': [
                    {
                        'event_pattern': 'message.received',
                        'target_type': 'agent',
                        'target_uuid': agent,
                        'filters': [],
                        'priority': 0,
                        'enabled': True,
                    }
                ],
            },
        )
    )['uuid']
    upload = _data(
        client.post(
            '/api/v1/artifacts', headers=owner, files={'file': ('input.bin', content, 'application/octet-stream')}
        )
    )['id']
    record(
        'started',
        duration_seconds=duration,
        period_seconds=period,
        payload_sizes=[256 * 1024, 1024 * 1024, 2 * 1024 * 1024],
        digest=digest,
        backend=config['storage']['content']['backend'],
        root=str(runner_e2e_tmpdir),
        core_pid=core.process.pid,
        runtime_pid=plugin_runtime.process.pid,
        expiry_acceleration='only test-owned rows; production GC and reads remain unchanged',
    )
    samples, cycles, generation, faults = [], 0, 0, {}
    started, deadline = time.monotonic(), time.monotonic() + duration

    def check_digest(artifact_id, headers=owner):
        response = client.get('/api/v1/artifacts/' + artifact_id + '/content', headers=headers)
        assert response.status_code == 200, response.text
        assert len(response.content) == len(content) and hashlib.sha256(response.content).hexdigest() == digest

    def restart_core(reason):
        nonlocal other_workspace, foreign_workspace
        # OSS bootstrap deliberately requires one legacy public-media Workspace.
        # The extra QA tenant has no assets; recreate it after startup so each
        # denial still uses a real, authorized second Workspace context.
        observer.remove_foreign_workspace(other_workspace)
        core.stop()
        for name in ('langbot.stdout.log', 'langbot.stderr.log'):
            source = runner_e2e_tmpdir / name
            (evidence / f'{lane}.generation-{generation}.{reason}.{name}').write_bytes(source.read_bytes())
        assert core.start(), core.get_logs()
        assert runtime.QA_RUNNER_ID in runtime._wait_for_qa_runner(client, token)
        other_workspace = observer.seed_foreign_workspace(account_b)
        foreign_workspace = _headers(second_token, other_workspace)
        assert (
            _data(client.get('/api/v1/workspaces/current', headers=foreign_workspace))['workspace']['uuid']
            == other_workspace
        )

    def release(artifact_id, headers=owner):
        first = _data(client.post('/api/v1/artifacts/' + artifact_id + '/release', headers=headers))
        again = _data(client.post('/api/v1/artifacts/' + artifact_id + '/release', headers=headers))
        assert first['expires_at'] == again['expires_at'] and first['expires_at'] is not None

    def denied(artifact_id):
        for headers in (second, foreign_workspace, key_headers):
            for method, suffix in (
                ('GET', ''),
                ('GET', '/content'),
                ('POST', '/retain'),
                ('POST', '/release'),
                ('DELETE', ''),
            ):
                response = client.request(method, '/api/v1/artifacts/' + artifact_id + suffix, headers=headers)
                assert response.status_code == 404, (method, suffix, response.status_code, response.text)

    def debug_request(**options):
        return {
            'text': json.dumps({'operation': 'roundtrip', 'nonce': uuid.uuid4().hex, 'debug': True, **options}),
            'artifact_ids': [upload],
        }

    def stream_case(case):
        target = timeout_agent if case == 'timeout' else agent
        report = None
        frames = []
        active_hold = 150 if duration >= 600 else 30
        next_active_gc = 0.0
        active_completed = False
        active_leases = []
        with client.stream(
            'POST',
            f'/api/v1/agents/{target}/debug/stream',
            headers=owner,
            json=debug_request(hold=active_hold if case == 'active' else 30),
            timeout=240,
        ) as response:
            assert response.status_code == 200, response.read().decode()
            for line in response.iter_lines():
                if not line:
                    if case == 'active' and report is not None and time.monotonic() >= next_active_gc:
                        observer.gc()
                        snapshot = observer.query(
                            'SELECT status, execution_lease_expires_at, '
                            '(SELECT COUNT(*) FROM artifacts WHERE owner_id=:id) AS assets '
                            'FROM agent_run WHERE run_id=:id',
                            {'id': report['run_id']},
                        )[0]
                        lease = snapshot['execution_lease_expires_at']
                        if snapshot['status'] == 'running':
                            expires = dt.datetime.fromisoformat(str(lease)).replace(tzinfo=None)
                            assert expires > dt.datetime.now(dt.timezone.utc).replace(tzinfo=None), snapshot
                            assert snapshot['assets'] == 2, snapshot
                            active_leases.append(expires)
                        record(
                            'active_lease_checkpoint',
                            run_id=report['run_id'],
                            lease_expires_at=str(lease),
                            status=snapshot['status'],
                            assets=snapshot['assets'],
                        )
                        next_active_gc = time.monotonic() + 15
                    continue
                frame = json.loads(line)
                frames.append(frame)
                staged = _report(frame, 'SOAK_STAGE ')
                if staged is not None:
                    report = staged
                    assert 'error' not in report, report
                    record('fault_staged', case=case, run_id=report['run_id'])
                    if case == 'active':
                        ids = [report['artifact_id'], report['text_artifact_id']]
                        for artifact_id in ids:
                            release(artifact_id)
                        observer.accelerate_expiry(ids)
                        with ThreadPoolExecutor(max_workers=3) as pool:
                            jobs = [
                                pool.submit(observer.gc),
                                pool.submit(observer.gc),
                                pool.submit(client.get, '/api/v1/artifacts/' + ids[0] + '/content', headers=owner),
                            ]
                            results = [job.result(timeout=30) for job in jobs]
                        assert results[2].status_code == 410
                        assert (
                            observer.query(
                                'SELECT COUNT(*) AS n FROM artifacts WHERE owner_id=:id', {'id': report['run_id']}
                            )[0]['n']
                            == 2
                        )
                    elif case == 'cancel':
                        break
                    elif case == 'disconnect':
                        plugin_runtime.stop()
                done = _report(frame, 'SOAK_DONE ')
                if done is not None:
                    record('runner_report', case=case, report=done)
                    assert 'error' not in done, done
                    if case == 'active':
                        assert done['active_read'], done
                        active_completed = True
                if frame['kind'] in {'completed', 'error'}:
                    break
        assert report is not None, frames
        if case == 'active':
            assert active_completed, frames
            if duration >= 600:
                assert len(active_leases) >= 3 and (max(active_leases) - min(active_leases)).total_seconds() >= 90, (
                    active_leases
                )
        if case in {'cancel', 'timeout', 'disconnect'}:
            end = time.monotonic() + 30
            while time.monotonic() < end:
                row = observer.query('SELECT status FROM agent_run WHERE run_id=:id', {'id': report['run_id']})[0]
                if row['status'] in {'cancelled', 'failed', 'timeout'}:
                    break
                time.sleep(0.1)
            assert row['status'] in {'cancelled', 'failed', 'timeout'}, row
        if case == 'disconnect':
            plugin_runtime.start()
            restart_core('runtime-disconnect')
        for artifact_id in (report['artifact_id'], report['text_artifact_id']):
            response = client.get('/api/v1/artifacts/' + artifact_id, headers=owner)
            if case == 'active':
                assert response.status_code in {404, 410}, response.text
            else:
                assert _data(response)['lifecycle'] == 'persistent'
                release(artifact_id)
        if case != 'active':
            survived = client.get('/api/v1/artifacts/' + report['artifact_id'] + '/content', headers=owner)
            assert survived.status_code == 200 and len(survived.content) == input_size
            assert hashlib.sha256(survived.content).hexdigest() == input_digest
        observer.accelerate_expiry([report['artifact_id'], report['text_artifact_id']])
        observer.gc()
        faults[case] = faults.get(case, 0) + 1
        record('fault_passed', case=case, run_id=report['run_id'])

    def key_case():
        key_input = _data(
            client.post(
                '/api/v1/artifacts',
                headers=key_headers,
                files={'file': ('key-input.bin', content, 'application/octet-stream')},
            )
        )['id']
        report = None
        with client.stream(
            'POST',
            f'/api/v1/agents/{key_agent}/debug/stream',
            headers=key_headers,
            json={
                'text': json.dumps({'operation': 'roundtrip', 'debug': True, 'nonce': uuid.uuid4().hex}),
                'artifact_ids': [key_input],
            },
            timeout=70,
        ) as response:
            assert response.status_code == 200, response.read().decode()
            for line in response.iter_lines():
                if not line:
                    continue
                frame = json.loads(line)
                done = _report(frame, 'SOAK_DONE ')
                if done is not None:
                    report = done
                if frame['kind'] in {'completed', 'error'}:
                    assert frame['kind'] == 'completed', frame
                    break
        record('runner_report', case='named-api-key', report=report)
        assert report is not None and 'error' not in report, report
        check_digest(report['artifact_id'], key_headers)
        assert client.get('/api/v1/artifacts/' + report['artifact_id'], headers=owner).status_code == 404
        ids = [report['artifact_id'], report['text_artifact_id']]
        for artifact_id in ids:
            release(artifact_id, key_headers)
        observer.accelerate_expiry([*ids, key_input])
        observer.gc()
        faults['named-api-key'] = faults.get('named-api-key', 0) + 1
        record('fault_passed', case='named-api-key', run_id=report['run_id'])

    try:
        while time.monotonic() < deadline or cycles < 8:
            cycle_started = time.monotonic()
            size = (256 * 1024, 1024 * 1024, 2 * 1024 * 1024)[cycles % 3]
            marker = hashlib.sha256(f'{lane}:{cycles}'.encode()).digest()
            content = (marker + bytes(range(256)) * ((size + 255) // 256))[:size]
            digest = hashlib.sha256(content).hexdigest()
            file_source.body = content
            fault_slot = cycles if cycles < 8 else cycles % max(60, int(900 / period))
            operation = 'cleanup-failure' if cycles % 8 == 2 else 'roundtrip'
            report, files = network._turn(
                client,
                bot,
                {'operation': operation, 'nonce': uuid.uuid4().hex},
                url=source_url,
                session='soak-' + str(cycles),
            )
            assert 'error' not in report and report.get('committed') and report.get('repeat_reply_denied'), report
            assert (
                len(files) == 1
                and hashlib.sha256(base64.b64decode(files[0]['base64'].split(';base64,')[-1])).hexdigest() == digest
            )
            if operation == 'cleanup-failure':
                assert report['cleanup_warning'], report
                faults['cleanup-failure'] = faults.get('cleanup-failure', 0) + 1
            check_digest(report['artifact_id'])
            denied(report['artifact_id'])
            rejected, extra = network._turn(
                client,
                bot,
                {'operation': 'foreign-file', 'file_id': report['file_id']},
                session='foreign-' + str(cycles),
            )
            assert not extra and all(
                rejected.get(name + '_denied') for name in ('read_run_file', 'commit_run_files', 'reply_files')
            ), rejected
            if fault_slot == 1:
                key_case()
            if fault_slot == 6:
                restart_core('restart')
                generation += 1
                check_digest(report['artifact_id'])
                faults['restart'] = faults.get('restart', 0) + 1
            ids = [report['artifact_id'], report['text_artifact_id']]
            with ThreadPoolExecutor(max_workers=4) as pool:
                work = [
                    pool.submit(check_digest, ids[0]),
                    pool.submit(release, ids[0]),
                    pool.submit(release, ids[1]),
                    pool.submit(observer.gc),
                ]
                for job in work:
                    job.result(timeout=30)
            with ThreadPoolExecutor(max_workers=4) as pool:
                read = pool.submit(client.get, '/api/v1/artifacts/' + ids[0] + '/content', headers=owner)
                expire = pool.submit(observer.accelerate_expiry, ids)
                collections = [pool.submit(observer.gc), pool.submit(observer.gc)]
                raced = read.result(timeout=30)
                expire.result(timeout=30)
                collected = sum(job.result(timeout=30) for job in collections)
            assert raced.status_code in {200, 404, 410}, (raced.status_code, raced.text)
            if raced.status_code == 200:
                assert hashlib.sha256(raced.content).hexdigest() == digest
            observer.gc()
            assert all(client.get('/api/v1/artifacts/' + item, headers=owner).status_code == 404 for item in ids)
            if fault_slot in {3, 4, 5, 7}:
                case = {3: 'active', 4: 'cancel', 5: 'timeout', 7: 'disconnect'}[fault_slot]
                stream_case(case)
                if case == 'disconnect':
                    generation += 1
            snapshot = observer.snapshot()
            assert (
                snapshot['artifacts'] == 1 and snapshot['artifact_references'] <= 1 and snapshot['content_objects'] == 1
            ), snapshot
            assert snapshot['live_runs'] == 0, snapshot
            if 'db_connections' in snapshot:
                assert snapshot['db_connections'] <= 30, snapshot
            if 'object_count' in snapshot:
                assert snapshot['object_count'] == 1, snapshot
            sample = {
                **_resources(core, plugin_runtime),
                'generation': generation,
                'elapsed': time.monotonic() - started,
            }
            samples.append(sample)
            cycles += 1
            record(
                'cycle_passed',
                cycle=cycles,
                bytes=len(content),
                digest=digest,
                seconds=time.monotonic() - cycle_started,
                collected=collected,
                concurrent_read_status=raced.status_code,
                store=snapshot,
                resources=sample,
            )
            time.sleep(max(0, min(period - (time.monotonic() - cycle_started), deadline - time.monotonic())))
        checked = _assert_plateau(samples)
        if duration >= 600:
            assert checked >= 1, 'No uninterrupted post-warmup resource windows were observed'
        assert {
            'active',
            'cancel',
            'timeout',
            'disconnect',
            'restart',
            'cleanup-failure',
            'named-api-key',
        } <= faults.keys(), faults
        assert time.monotonic() - started >= duration
        observer.accelerate_expiry([upload])
        observer.gc()
        final = observer.snapshot()
        assert final['artifacts'] == final['artifact_references'] == final['content_objects'] == 0, final
        assert final.get('object_count', 0) == 0, final
        summary = {
            'result': 'PASS',
            'lane': lane,
            'cycles': cycles,
            'duration_seconds': time.monotonic() - started,
            'requested_seconds': duration,
            'faults': faults,
            'final_store': final,
            'resource_samples': len(samples),
            'resource_windows_checked': checked,
            'expiry_accelerated': True,
        }
        (evidence / (lane + '.summary.json')).write_text(json.dumps(summary, indent=2), encoding='utf-8')
        record('completed', **summary)
    except BaseException as error:
        try:
            failed_store = observer.snapshot()
        except Exception as snapshot_error:
            failed_store = {'snapshot_error': type(snapshot_error).__name__ + ': ' + str(snapshot_error)}
        record(
            'failed',
            error=type(error).__name__ + ': ' + str(error),
            cycle=cycles,
            store=failed_store,
            root=str(runner_e2e_tmpdir),
        )
        raise


_MIXED_KINDS = ('png', 'text', 'jpeg', 'text_pdf', 'scanned_pdf', 'mixed')
_HOUR = 3600


def _percentiles(sizes):
    ordered = sorted(sizes)
    return (
        {f'p{value}': round(ordered[math.ceil(len(ordered) * value / 100) - 1], 4) for value in (50, 95, 99)}
        if ordered
        else {}
    )


def _mixed_process_tree(process):
    result = dict(cpu_seconds=0.0, rss=0, fds=0, threads=0, processes=0)
    try:
        root = psutil.Process(process.pid)
        children = root.children(recursive=True)
    except psutil.NoSuchProcess:
        return result
    for item in (root, *children):
        try:
            rss, fds, threads, cpu = item.memory_info().rss, item.num_fds(), item.num_threads(), item.cpu_times()
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
        result['rss'] += rss
        result['fds'] += fds
        result['threads'] += threads
        result['processes'] += 1
        result['cpu_seconds'] += cpu.user + cpu.system
    return result


def _mixed_store(observer, test_root):
    snapshot = observer.snapshot()
    now = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None)
    snapshot.update(
        observer.query(
            "SELECT COALESCE(SUM(size), 0) AS content_bytes FROM content_objects WHERE owner_type = 'artifact'"
        )[0]
    )
    backlog = observer.query(
        'SELECT COUNT(*) AS gc_backlog, MIN(COALESCE(deleted_at, expires_at)) AS oldest '
        'FROM artifacts WHERE deleted_at IS NOT NULL OR expires_at <= :now',
        {'now': now},
    )[0]
    snapshot['gc_backlog'] = backlog['gc_backlog']
    snapshot['gc_oldest_age_seconds'] = (
        max(0, (now - dt.datetime.fromisoformat(str(backlog['oldest']))).total_seconds()) if backlog['oldest'] else 0
    )
    if observer.url.startswith('postgresql'):
        snapshot.update(
            observer.query(
                'SELECT pg_database_size(current_database()) AS db_bytes, '
                "COUNT(*) FILTER (WHERE wait_event_type='Lock') AS db_lock_waiters FROM pg_stat_activity "
                'WHERE datname=current_database()'
            )[0]
        )
    else:
        snapshot['sqlite_free_pages'] = observer.query('PRAGMA freelist_count')[0]['freelist_count']
        snapshot['sqlite_page_bytes'] = observer.query('PRAGMA page_size')[0]['page_size']
    snapshot['free_bytes'] = shutil.disk_usage(test_root).free
    return snapshot


def _mixed_turn(client, bot, session, group, member, files, box_slot):
    from langbot.pkg.platform.sources import http_bot_signing as signing

    message = [{'type': 'Plain', 'text': json.dumps({'operation': 'mixed', 'box_slot': box_slot})}]
    message.extend({'type': 'File', 'name': fixture.filename, 'url': url} for fixture, url in files)
    body = json.dumps(
        {
            'session_id': session,
            'session_type': 'group' if group else 'person',
            'sender': {'id': f'qa-member-{member}'},
            'message': message,
        }
    ).encode()
    timestamp, signature = signing.sign(network._SECRET, body)
    result = _data(
        client.post(
            f'/bots/{bot}/sync',
            content=body,
            headers={
                'Content-Type': 'application/json',
                signing.HEADER_TIMESTAMP: timestamp,
                signing.HEADER_SIGNATURE: signature,
            },
            timeout=100,
        )
    )
    reports = [
        json.loads(part['text'].removeprefix('NETWORK_E2E '))
        for part in result['message']
        if part['type'] == 'Plain' and part.get('text', '').startswith('NETWORK_E2E ')
    ]
    assert len(reports) == 1, result
    return reports[0], [part for part in result['message'] if part['type'] == 'File']


@pytest.mark.skipif(not os.environ.get('LANGBOT_SOAK_MIXED_MODE'), reason='mixed soak mode not requested')
def test_artifact_mixed_soak(
    runner_client,
    runner_langbot_process,
    runner_runtime_process,
    runner_e2e_tmpdir,
    runner_e2e_config_path,
    file_source,
):
    """Fixed-seed mixed ingress and lifecycle; accelerated mode uses autonomous Core GC."""
    from langbot.pkg.storage.artifacts import DEFAULT_TTL_SECONDS
    from tests.utils.artifact_media import make_artifact_media

    mode = os.environ['LANGBOT_SOAK_MIXED_MODE']
    assert mode in {'short', 'staircase', 'accelerated'}, mode
    accelerated = mode == 'accelerated'
    lane = os.environ.get('LANGBOT_SOAK_LANE', 'sqlite-database')
    root = Path(__file__).resolve().parents[2]
    profile_bytes = _artifact_soak_profile()
    profile = json.loads(profile_bytes)
    identity = {
        'lane': lane,
        'profile_sha256': hashlib.sha256(profile_bytes).hexdigest(),
        'harness_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'media_sha256': hashlib.sha256((root / 'tests/utils/artifact_media.py').read_bytes()).hexdigest(),
        'git_sha': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=root, text=True).strip(),
    }
    weights = profile['weights']
    assert set(weights) == set(_MIXED_KINDS)
    assert all(type(value) is int and value > 0 for value in weights.values())
    assert 1 <= profile['group_slots'] <= 12 and 1 <= profile['member_slots'] <= 20
    assert 1 <= profile['long_sessions'] <= 4 and profile['long_every'] >= 2
    staircase = profile['staircase']
    assert all(1 <= step['parallel'] <= 4 and step['waves'] >= 1 and step['period_seconds'] > 0 for step in staircase)
    parallel = staircase[-1]['parallel']
    # One turn can materialize four inputs and export one output.
    rows_per_wave = parallel * 5
    if accelerated:
        fast = profile['accelerated']
        fast_period = fast['period_seconds']
        fast_load = fast['load_seconds']
        fast_ttl = fast['ttl_seconds']
        fast_gc = fast['gc_interval_seconds']
        fast_drain = fast['drain_seconds']
        assert 0 < fast_gc <= fast_ttl < fast_load and fast_drain >= fast_ttl + 2 * fast_gc
        assert fast_load >= 9 * fast_period
        assert math.ceil(fast_gc / fast_period) * rows_per_wave <= 80, 'Offered rows exceed the scheduled GC budget'
        assert (
            math.ceil((fast_ttl + 2 * fast_gc) / fast_period) * rows_per_wave + 2 <= profile['budgets']['artifact_rows']
        ), 'Worst-case accelerated backlog exceeds the live row budget'
    evidence = Path(os.environ.get('LANGBOT_SOAK_EVIDENCE', str(runner_e2e_tmpdir)))
    evidence.mkdir(parents=True, exist_ok=True)
    prefix = f'{lane}.mixed-{mode}'
    journal = evidence / (prefix + '.ndjson')
    assert not journal.exists(), f'Refusing to append to previous run evidence: {journal}'
    rng = random.Random(profile['seed'])
    config = yaml.safe_load(runner_e2e_config_path.read_text())
    if accelerated:
        cleanup = config['storage']['cleanup']
        assert cleanup['enabled'] is True and abs(cleanup['check_interval_hours'] * _HOUR - fast_gc) < 0.01
    observer = StoreObserver(config)
    client, core, plugin_runtime = runner_client, runner_langbot_process, runner_runtime_process
    token = runtime._init_and_auth(client)
    owner = _headers(token)
    core.token = token
    runtime._ensure_qa_plugin(client, token, runner_e2e_tmpdir / 'agent-runner-qa.zip')
    agent = _agent(client, owner)
    _policy(client, owner, agent)
    bot = _data(
        client.post(
            '/api/v1/platform/bots',
            headers=owner,
            json={
                'name': 'Deterministic mixed Artifact soak',
                'adapter': 'http_bot',
                'enable': True,
                'adapter_config': {
                    'inbound_secret': network._SECRET,
                    'callback_url': file_source.url + '/no-callback',
                    'signature_required': True,
                    'callback_timeout': 90,
                    'callback_max_retries': 0,
                },
                'event_bindings': [
                    {
                        'event_pattern': 'message.received',
                        'target_type': 'agent',
                        'target_uuid': agent,
                        'filters': [],
                        'priority': 0,
                        'enabled': True,
                    }
                ],
            },
        )
    )['uuid']
    started = time.monotonic()
    durations, counts, errors = defaultdict(list), Counter(), Counter()
    totals = Counter()
    sessions = set()
    previous_media = {}
    steady_windows = []
    staircase_windows = []
    load_seconds = None
    gc_ticks = []
    startup_log = runner_e2e_tmpdir / 'langbot.stdout.log'

    def elapsed():
        return time.monotonic() - started

    def record(event, **extra):
        row = {
            'event': event,
            'elapsed_seconds': round(elapsed(), 3),
            'utc': dt.datetime.now(dt.timezone.utc).isoformat(),
            **extra,
        }
        with journal.open('a', encoding='utf-8') as stream:
            stream.write(json.dumps(row, ensure_ascii=False) + '\n')
        if event != 'turn':
            print(json.dumps(row, ensure_ascii=False), flush=True)

    def asset_path(artifact_id):
        return '/api/v1/artifacts/' + artifact_id

    def read_exact(artifact_id, fixture):
        response = client.get(asset_path(artifact_id) + '/content', headers=owner)
        assert response.status_code == 200 and response.content == fixture.data, (artifact_id, response.status_code)

    def assert_full_ttl(expires_at):
        observed = dt.datetime.fromisoformat(expires_at)
        if observed.tzinfo is None:
            observed = observed.replace(tzinfo=dt.timezone.utc)
        remaining = (observed - dt.datetime.now(dt.timezone.utc)).total_seconds()
        assert abs(remaining - DEFAULT_TTL_SECONDS) <= 5, (expires_at, remaining)

    def release_asset(artifact_id):
        expires_at = _data(client.post(asset_path(artifact_id) + '/release', headers=owner))['expires_at']
        assert_full_ttl(expires_at)
        return expires_at

    def discard(artifact_id):
        release_asset(artifact_id)
        assert _data(client.delete(asset_path(artifact_id), headers=owner))['deleted'] is True
        assert client.get(asset_path(artifact_id) + '/content', headers=owner).status_code == 404

    def upload_probe(label):
        fixture = make_artifact_media(label, seed=profile['seed'])[0]
        row = _data(
            client.post(
                '/api/v1/artifacts', headers=owner, files={'file': (fixture.filename, fixture.data, fixture.mime_type)}
            )
        )
        assert row['digest'] == fixture.sha256 and row['size'] == fixture.size
        assert _data(client.post(asset_path(row['id']) + '/retain', headers=owner))['expires_at'] is None
        record('retained_probe', label=label, artifact=row['id'])
        totals['probe_bytes'] += fixture.size
        return row['id'], fixture

    def plan(wave, slot, phase):
        number = totals['planned']
        totals['planned'] += 1
        is_long = slot == 0 and wave % profile['long_every'] == 0
        member = (wave + slot) % profile['member_slots']
        if is_long:
            session = f'qa-long-{(wave // profile["long_every"]) % profile["long_sessions"]}'
            group = True
        elif slot % 2:
            session = f'qa-group-{wave % profile["group_slots"]}-short-{number}'
            group = True
        else:
            session = f'qa-person-short-{number}'
            group = False
        kind = (
            _MIXED_KINDS[number]
            if number < len(_MIXED_KINDS)
            else rng.choices(
                _MIXED_KINDS,
                weights=[weights[name] for name in _MIXED_KINDS],
                k=1,
            )[0]
        )
        fixtures = {item.kind: item for item in make_artifact_media(session + f':{number}', seed=profile['seed'])}
        history = previous_media.get(session)
        if kind == 'text' and is_long and history and wave % 2 == 0:
            kind = 'png'
        if kind == 'text':
            media = ()
        elif kind == 'mixed':
            media = tuple(fixtures.values())
        else:
            media = (fixtures[kind],)
        # Repeat an older body behind a fresh URL in an alternating turn in the
        # same long-lived session. The bounded test covers actual old-ref access.
        if history and media and wave % 2 == 0:
            media = (*media[:3], history)
            totals['old_body_reuploads'] += 1
        if media and is_long:
            previous_media[session] = media[0]
        totals['group_turns' if group else 'person_turns'] += 1
        if is_long:
            totals['long_turns'] += 1
        sessions.add(session)
        files = []
        for index, fixture in enumerate(media):
            path = f'/mixed/{number}/{index}/{fixture.filename}'
            file_source.mixed[path] = fixture
            files.append((fixture, file_source.url + path, path))
        return number, session, group, member, kind, files, phase, slot

    def execute(spec):
        number, session, group, member, kind, files, phase, slot = spec
        begin = time.monotonic()
        report, output = _mixed_turn(client, bot, session, group, member, [(file, url) for file, url, _ in files], slot)
        assert 'error' not in report, report
        entries = report['inputs']
        refs = [item['ref'] for item in entries]
        assert all(refs) and len(set(refs)) == len(refs), refs
        actual = Counter((item['sha256'], item['size']) for item in entries)
        assert actual == Counter((file.sha256, file.size) for file, _, _ in files), (actual, kind)
        expected = {file.sha256: file for file, _, _ in files}
        run_id = report['run_id']
        rows = observer.query(
            "SELECT id, digest, size, name, mime_type FROM artifacts WHERE owner_type='run' AND owner_id=:run",
            {'run': run_id},
        )
        assert {row['id'] for row in rows} == {item['id'] for item in entries}, (run_id, rows, entries)
        assert len(rows) == len(entries), (run_id, rows, entries)
        by_id = {row['id']: row for row in rows}
        for item in entries:
            fixture = expected[item['sha256']]
            row = by_id[item['id']]
            assert (row['digest'], row['size'], row['name'], row['mime_type']) == (
                fixture.sha256,
                fixture.size,
                fixture.filename,
                fixture.mime_type,
            ), row
            assert (item['name'], item['mime']) == (fixture.filename, fixture.mime_type), item
            if fixture.kind == 'text_pdf':
                assert item['mode'] == 'text' and item['continuation'] is True and fixture.marker in item['text']
            else:
                assert item['mode'] == ('native' if fixture.kind == 'scanned_pdf' else 'image'), item
        lifecycle = None
        inputs = report['inputs']
        if files:
            assert len(output) == 1, output
            exported = base64.b64decode(output[0]['base64'].split(';base64,')[-1], validate=True)
            first = expected[entries[0]['sha256']]
            assert first.data == exported, (number, session, kind, hashlib.sha256(exported).hexdigest())
            artifact = report['artifact_id']
            read_exact(artifact, first)
            # Sync reply can arrive just before the ledger commits its terminal state.
            until = time.monotonic() + 15
            while time.monotonic() < until:
                state = observer.query('SELECT status FROM agent_run WHERE run_id=:run', {'run': report['run_id']})
                if state and state[0]['status'] == 'completed':
                    break
                time.sleep(0.05)
            else:
                raise AssertionError((report['run_id'], 'completion not persisted'))
            if accelerated:
                lifecycle = {'artifact': artifact, 'expires_at': release_asset(artifact)}
                read_exact(artifact, first)
            else:
                discard(artifact)
                lifecycle = {'artifact': artifact, 'tombstoned': True}
        else:
            assert not output and 'artifact_id' not in report, report
        if entries:
            # Change expiry only on IDs verified to belong to this owned run.
            # Accelerated mode leaves collection to the Core scheduler.
            due = dt.datetime.now(dt.timezone.utc).replace(tzinfo=None) + dt.timedelta(
                seconds=fast_ttl if accelerated else -1
            )
            for item in entries:
                observer.query(
                    "UPDATE artifacts SET expires_at=:due WHERE id=:id AND owner_type='run' AND owner_id=:run",
                    {'due': due, 'id': item['id'], 'run': run_id},
                )
            if accelerated:
                observer.query(
                    "UPDATE artifacts SET expires_at=:due WHERE id=:id AND owner_type='run_output' AND owner_id=:run AND expires_at IS NOT NULL",
                    {'due': due, 'id': lifecycle['artifact'], 'run': run_id},
                )
                found = observer.query('SELECT expires_at FROM artifacts WHERE id=:id', {'id': lifecycle['artifact']})[
                    0
                ]['expires_at']
                assert abs((dt.datetime.fromisoformat(str(found)) - due).total_seconds()) < 0.01, found
        return time.monotonic() - begin, lifecycle, inputs

    def wave(number, count, phase):
        cases = [plan(number, slot, phase) for slot in range(count)]
        offered = sum(file.size for case in cases for file, _, _ in case[5])
        totals['offered_bytes'] += offered
        totals['files'] += sum(len(case[5]) for case in cases)
        assert totals['offered_bytes'] + totals['probe_bytes'] <= profile['budgets']['offered_bytes']
        with ThreadPoolExecutor(max_workers=count) as pool:
            for spec, future in zip(cases, [pool.submit(execute, spec) for spec in cases], strict=True):
                turn_id, session, _group, member, kind, files, phase, _slot = spec
                try:
                    latency, lifecycle, inputs = future.result()
                except Exception as error:
                    from httpx import TimeoutException

                    errors[kind] += 1
                    totals['timed_out_turns'] += isinstance(error, TimeoutException)
                    record('turn_failed', kind=kind, turn=turn_id, session=session, error=repr(error))
                    raise
                finally:
                    for _, _, path in files:
                        file_source.mixed.pop(path, None)
                counts[kind] += 1
                durations[kind].append(latency)
                if lifecycle:
                    totals['scheduled_ttl_outputs' if lifecycle.get('expires_at') else 'tombstoned_outputs'] += 1
                totals['materialized_inputs_created'] += len(inputs)
                for item in inputs:
                    totals[f'structured_{item["mode"]}_reads'] += 1
                record(
                    'turn',
                    kind=kind,
                    turn=turn_id,
                    session=session,
                    member=member,
                    phase=phase,
                    latency_seconds=round(latency, 4),
                    bytes=sum(file.size for file, _, _ in files),
                    digests=[file.sha256 for file, _, _ in files],
                    lifecycle=lifecycle,
                    materialized_inputs=[
                        {'id': item['id'], 'mode': item['mode'], 'size': item['size']} for item in inputs
                    ],
                )
        if not accelerated:
            totals['manual_gc_calls'] += 1
            totals['observer_collected'] += observer.gc()

    def sample(phase):
        topology = {
            'Core': _mixed_process_tree(core.process),
            'Runtime': _mixed_process_tree(plugin_runtime.process),
            'Box': 'embedded in Core process tree for host backend',
        }
        snapshot = _mixed_store(observer, runner_e2e_tmpdir)
        budgets = profile['budgets']
        assert snapshot['artifacts'] <= budgets['artifact_rows'], snapshot
        assert snapshot['content_bytes'] <= budgets['content_bytes'], snapshot
        assert snapshot['free_bytes'] >= budgets['free_bytes'], snapshot
        resource = {
            key: sum(topology[name][key] for name in ('Core', 'Runtime'))
            for key in ('rss', 'fds', 'threads', 'processes')
        }
        if phase == 'accelerated-steady':
            steady_windows.append(resource)
        record(
            'sample',
            phase=phase,
            resources=topology,
            store=snapshot,
            source_file_gets=file_source.mixed_requests,
            ttl_outputs=totals['scheduled_ttl_outputs'],
            materialized_inputs_created=totals['materialized_inputs_created'],
            tombstoned_outputs=totals['tombstoned_outputs'],
        )
        return snapshot

    def wait_until(target, phase):
        while elapsed() < target:
            time.sleep(min(fast_gc if accelerated else 60, target - elapsed()))
            if accelerated and elapsed() < target:
                sample(phase)

    def observed_gc_ticks():
        import re

        lines = startup_log.read_text(errors='replace').splitlines() if startup_log.exists() else []
        return [
            line
            for line in lines
            if 'cleaned expired storage data' in line and re.search(r"'artifacts': [1-9]\d*", line)
        ]

    import langbot_plugin
    from importlib.metadata import version

    record(
        'started',
        mode=mode,
        sqlite_write_queue=config['database']['sqlite'].get('experimental_write_queue', False),
        identity=identity,
        profile=profile,
        ttl_seconds=fast_ttl if accelerated else DEFAULT_TTL_SECONDS,
        gc_interval_seconds=fast_gc if accelerated else None,
        storage_gc_mode='scheduler' if accelerated else 'explicit iteration',
        sdk_path=str(Path(langbot_plugin.__file__).resolve()),
        sdk_version=version('langbot-plugin'),
        box_backend=config['box']['backend'],
    )
    try:
        if accelerated:
            retained_artifact, retained_fixture = upload_probe('accelerated-retained')
            # Diagnostic comparisons need equal input prefixes even if one arm misses pace.
            timing_waves = int(os.environ.get('LANGBOT_SOAK_TIMING_WAVES', '0'))
            assert 0 <= timing_waves <= fast_load // fast_period
            if timing_waves:
                assert config['database']['sqlite']['experimental_write_timing'] is True
            index = 0
            while index < timing_waves if timing_waves else elapsed() < fast_load:
                begin = elapsed()
                wave(index, parallel, 'accelerated-steady')
                sample('accelerated-steady')
                wave_seconds = elapsed() - begin
                record('wave_timing', wave=index, seconds=round(wave_seconds, 4))
                if not timing_waves:
                    assert wave_seconds < fast_period, 'Accelerated offered pace exceeded'
                index += 1
                if timing_waves == index:
                    record('diagnostic_complete', waves=index, turns=sum(counts.values()))
                    discard(retained_artifact)
                    return
                wait_until(min(index * fast_period, fast_load), 'accelerated-steady')
            load_seconds = elapsed()
            record('offered_load_complete', seconds=load_seconds, turns=sum(counts.values()))
            read_exact(retained_artifact, retained_fixture)
            discard(retained_artifact)
            drain_until = elapsed() + fast_drain
            while True:
                store = sample('accelerated-drain')
                if not store['artifacts'] and not store['content_objects']:
                    break
                assert elapsed() < drain_until, ('Scheduled GC did not drain within budget', store)
                wait_until(min(drain_until, elapsed() + fast_gc), 'accelerated-drain')
            gc_ticks = observed_gc_ticks()
            assert len(gc_ticks) >= 2 and totals['scheduled_ttl_outputs'] > 0, gc_ticks
            record(
                'accelerated_gc_observed',
                ticks=gc_ticks,
                retained_survived_load=True,
                drain_seconds=elapsed() - load_seconds,
            )
        else:
            phases = staircase if mode == 'staircase' else [{'waves': 9, 'parallel': 2, 'period_seconds': 0}]
            index = 0
            for step in phases:
                phase_start = elapsed()
                phase = f'{step["parallel"]}@{step["period_seconds"]}s'
                prior = sum(counts.values())
                wave_times = []
                for count in range(step['waves']):
                    begin = elapsed()
                    wave(index, step['parallel'], phase)
                    sample(phase)
                    wave_times.append(elapsed() - begin)
                    index += 1
                    wait_until(phase_start + (count + 1) * step['period_seconds'], phase)
                wall = elapsed() - phase_start
                completed = sum(counts.values()) - prior
                measurement = {
                    'name': phase,
                    'completed': completed,
                    'seconds': round(wall, 4),
                    'turns_per_second': round(completed / wall, 4),
                    'slowest_wave_seconds': round(max(wave_times), 4),
                    'within_offered_pace': max(wave_times) <= step['period_seconds'],
                }
                staircase_windows.append(measurement)
                record('phase', **measurement)
        store = sample('final')
        assert store['artifacts'] == store['artifact_references'] == store['content_objects'] == 0, store
        assert store.get('object_count', 0) == 0, store
        totals['materialized_inputs_reclaimed'] = totals['materialized_inputs_created']
        assert totals['materialized_inputs_created'] == totals['files'] > 0, totals
        assert totals['materialized_inputs_reclaimed'] > 0
        assert all(totals[f'structured_{mode}_reads'] > 0 for mode in ('text', 'image', 'native')), totals
        assert all(counts[kind] for kind in _MIXED_KINDS)
        assert totals['old_body_reuploads'] >= 1 and totals['group_turns'] and totals['person_turns'], totals
        latency = {kind: _percentiles(durations[kind]) for kind in _MIXED_KINDS}
        accelerated_growth = {}
        if accelerated:
            width = max(3, len(steady_windows) // 10)
            assert len(steady_windows) >= 2 * width + 1
            growth_limits = fast['max_resource_growth']
            assert set(growth_limits) == {'rss', 'fds', 'threads', 'processes'}
            for name, maximum in growth_limits.items():
                assert type(maximum) is int and maximum >= 0
                early = statistics.median(row[name] for row in steady_windows[1 : width + 1])
                late = statistics.median(row[name] for row in steady_windows[-width:])
                accelerated_growth[name] = {'early': early, 'late': late, 'delta': late - early, 'limit': maximum}
                assert late - early <= maximum, (name, early, late, maximum)
        summary = {
            'result': 'PASS',
            'identity': identity,
            'seconds': round(elapsed(), 3),
            'counts': counts,
            'errors': errors,
            'latency_seconds': latency,
            'totals': totals,
            'sessions': len(sessions),
            'source_file_gets': file_source.mixed_requests,
            'store': store,
            'scheduled_gc_maintenance': accelerated,
            'gc_ticks': len(gc_ticks),
            'manual_gc_calls': totals['manual_gc_calls'],
            'load_seconds': round(load_seconds, 3) if load_seconds is not None else None,
            'ttl_seconds': fast_ttl if accelerated else DEFAULT_TTL_SECONDS,
            'gc_interval_seconds': fast_gc if accelerated else None,
            'accelerated_steady_windows': len(steady_windows),
            'accelerated_steady_growth': accelerated_growth,
            'phases': staircase_windows,
        }
        if mode == 'staircase':
            assert staircase_windows[-1]['within_offered_pace'], staircase_windows[-1]
        (evidence / (prefix + '.summary.json')).write_text(json.dumps(summary, indent=2) + '\n', encoding='utf-8')
        record('completed', **summary)
    except BaseException as error:
        record('failed', error=repr(error), counts=counts, errors=errors, totals=totals)
        raise
