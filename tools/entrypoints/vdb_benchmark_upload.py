"""Measure bounded raw Artifact upload and RAG indexing on an owned local Core."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from hashlib import file_digest
from http.client import HTTPConnection
import json
import os
from pathlib import Path
import re
from time import monotonic, monotonic_ns, sleep
from uuid import uuid4

from tools.regression.vdb_benchmark_counts import count_chroma
from tools.regression.vdb_benchmark_http import (
    ARTIFACTS,
    KB,
    LANGRAG,
    PARSER,
    RETRIEVAL,
    CoreHTTP,
    checked_id,
    write_json,
)

MIB = 1024 * 1024
FIELDS = {'id', 'file_bytes', 'files', 'workers', 'attach'}


def load_profile(path):
    raw = json.loads(Path(path).read_text())
    if (
        not isinstance(raw, dict)
        or set(raw) != {'version', 'idle_seconds', 'chunk_size', 'cases'}
        or raw['version'] != 1
    ):
        raise ValueError('Unsupported upload-memory profile')
    if type(raw['idle_seconds']) is not int or not 4 <= raw['idle_seconds'] <= 120:
        raise ValueError('idle_seconds must be 4..120')
    if type(raw['chunk_size']) is not int or not 512 <= raw['chunk_size'] <= 4096:
        raise ValueError('chunk_size must be 512..4096')
    if not isinstance(raw['cases'], list) or not 1 <= len(raw['cases']) <= 12:
        raise ValueError('Expected 1..12 bounded cases')
    seen, total = set(), 0
    for case in raw['cases']:
        if not isinstance(case, dict) or set(case) != FIELDS or type(case['attach']) is not bool:
            raise ValueError('Invalid upload-memory case fields')
        key = checked_id(case['id'])
        if not re.fullmatch(r'[a-z][a-z0-9_-]{0,39}', key):
            raise ValueError('Case ID must be a lower-case phase label of at most 40 characters')
        if key in seen:
            raise ValueError('Duplicate upload-memory case ID')
        seen.add(key)
        for field, minimum, maximum in (
            ('files', 1, 16),
            ('workers', 1, 8),
            ('file_bytes', 1024, 2 * MIB if case['attach'] else 9 * MIB),
        ):
            if type(case[field]) is not int or not minimum <= case[field] <= maximum:
                raise ValueError(f'Invalid {field} for {key}')
        if case['workers'] > case['files']:
            raise ValueError('workers must not exceed the item count')
        total += case['file_bytes'] * case['files']
    if total > 256 * MIB:
        raise ValueError('Upload-memory profile aggregate payload exceeds 256 MiB')
    return raw


def load_public_inputs(manifest, profile):
    data = json.loads(manifest.read_text())
    if data.get('version') != 1 or set(data.get('cases', {})) != {case['id'] for case in profile['cases']}:
        raise ValueError('Public corpus case IDs differ from the selected profile')
    work = {}
    root = manifest.resolve().parent
    for case in profile['cases']:
        files = data['cases'][case['id']]
        if len(files) != case['files']:
            raise ValueError('Public corpus file count differs from the selected profile')
        paths = []
        for item in files:
            path = (root / item['path']).resolve()
            if (
                not path.is_relative_to(root)
                or item['bytes'] != case['file_bytes']
                or path.stat().st_size != item['bytes']
            ):
                raise ValueError('Public corpus path or file bytes mismatch')
            with path.open('rb') as source:
                if file_digest(source, 'sha256').hexdigest() != item['sha256']:
                    raise ValueError('Public corpus file checksum mismatch')
            paths.append(path)
        work[case['id']] = paths
    return data, work


def check_headroom(path=Path('/proc/meminfo')):
    """Abort large new fixture cases on low observed host headroom, not an OOM claim."""
    for line in path.read_text().splitlines():
        if line.startswith('MemAvailable:'):
            kib = int(line.split()[1])
            if kib < 1536 * 1024:
                raise ValueError('Host MemAvailable below the 1536 MiB admission floor')
            return kib * 1024
    raise ValueError('Host MemAvailable is unavailable')


def upload(api, name, size, source):
    boundary = 'lb-rss-' + uuid4().hex
    prefix = (
        f'--{boundary}\r\nContent-Disposition: form-data; name="file"; '
        f'filename="{name}.txt"\r\nContent-Type: text/plain\r\n\r\n'
    ).encode()
    suffix = f'\r\n--{boundary}--\r\n'.encode()

    def body():
        yield prefix
        with source.open('rb') as corpus:
            yield from iter(lambda: corpus.read(64 * 1024), b'')
        yield suffix

    headers = {
        **api.headers,
        'Content-Type': 'multipart/form-data; boundary=' + boundary,
        'Content-Length': str(len(prefix) + size + len(suffix)),
    }
    with closing_connection(api.host, api.port) as conn:
        conn.request('POST', ARTIFACTS, body=body(), headers=headers)
        response = conn.getresponse()
        if response.status != 200:
            raise ValueError(f'Artifact upload HTTP {response.status}')
        result = json.loads(response.read(65536))
        if result.get('code') != 0:
            raise ValueError('Artifact upload rejected')
        return checked_id(result['data']['id'])


@contextmanager
def closing_connection(host, port):
    conn = HTTPConnection(host, port, timeout=45)
    try:
        yield conn
    finally:
        conn.close()


def attach(api, kb, artifact):
    task = api.request('POST', f'{KB}/{kb}/files/artifact', {'artifact_id': artifact, 'parser_plugin_id': PARSER})[
        'task_id'
    ]
    if type(task) is not int:
        raise ValueError('Missing ingest task receipt')
    deadline = monotonic() + 450
    while monotonic() < deadline:
        data = api.request('GET', f'/api/v1/system/tasks/{task}')['runtime']
        if data['done']:
            if data.get('exception') or data.get('cancelled'):
                raise ValueError('Ingest task failed')
            return task
        sleep(0.25)
    raise TimeoutError('Ingest task deadline exhausted')


def peak_inflight(receipts):
    changes = [(row['began_ns'], 1) for row in receipts] + [(row['ended_ns'], -1) for row in receipts]
    active = peak = 0
    for _, change in sorted(changes):
        active += change
        peak = max(peak, active)
    return peak


def case_run(case, profile, api, model, directory, stage, owned, sqlite, suffix, sources):
    row = {**case, 'uploaded': 0, 'indexed': 0, 'errors': []}
    kb_path = None
    row['host_available_before_bytes'] = check_headroom()

    def collection():
        result = api.request(
            'POST',
            KB,
            {
                'name': 'QA upload RSS ' + suffix,
                'knowledge_engine_plugin_id': LANGRAG,
                'creation_settings': {
                    'index_type': 'chunk',
                    'embedding_model_uuid': model,
                    'chunk_size': profile['chunk_size'],
                    'overlap': 0,
                },
                'retrieval_settings': {**RETRIEVAL, 'top_k': 2},
            },
        )
        kb = checked_id(result['uuid'])
        owned['kb'] = kb
        write_json(directory / 'owned.json', owned)
        return f'{KB}/{kb}'

    if case['attach']:
        with stage(case['id'] + ':setup'):
            kb_path = collection()
            result = api.request(
                'POST', kb_path + '/retrieve', {'query': 'empty volume baseline', 'retrieval_settings': RETRIEVAL}
            )
            if result['results']:
                raise ValueError('New KB was not empty')
    with stage(case['id'] + ':baseline'):
        sleep(profile['idle_seconds'])

    def record(operation, item):
        start = monotonic_ns()
        try:
            output = operation(item)
            return {'ok': True, 'item': item, 'receipt': output, 'began_ns': start, 'ended_ns': monotonic_ns()}
        except Exception as exc:
            error = str(exc) if type(exc) is ValueError else type(exc).__name__
            return {'ok': False, 'item': item, 'error': error, 'began_ns': start, 'ended_ns': monotonic_ns()}

    with stage(case['id'] + ':upload'):
        with ThreadPoolExecutor(max_workers=case['workers']) as pool:

            def do_upload(item):
                return upload(
                    api,
                    f'rss-{suffix}-{case["id"]}-{item}',
                    case['file_bytes'],
                    sources[item],
                )

            uploads = list(pool.map(lambda item: record(do_upload, item), range(case['files'])))
        for item in uploads:
            if item['ok']:
                owned['artifacts'].append(item['receipt'])
        write_json(directory / 'owned.json', owned)
    with stage(case['id'] + ':upload_readback'):
        sizes = [api.request('GET', f'{ARTIFACTS}/{artifact}').get('size') for artifact in owned['artifacts']]
    if any(size != case['file_bytes'] for size in sizes):
        row['errors'].append('Artifact size readback did not match the submitted file')
    row['uploaded'] = len(sizes)
    row['uploaded_bytes'] = sum(size for size in sizes if type(size) is int)
    row['peak_upload_inflight'] = peak_inflight(uploads)
    row['errors'].extend(item['error'] for item in uploads if not item['ok'])
    row['upload_receipts'] = [{k: v for k, v in item.items() if k != 'receipt'} for item in uploads]
    if case['attach'] and not row['errors']:
        with stage(case['id'] + ':ingest'):
            with ThreadPoolExecutor(max_workers=case['workers']) as pool:

                def do_attach(item):
                    return attach(api, owned['kb'], owned['artifacts'][item])

                receipts = list(pool.map(lambda item: record(do_attach, item), range(case['files'])))
            row['errors'].extend(item['error'] for item in receipts if not item['ok'])
            files = api.request('GET', kb_path + '/files')['files']
            indexed = {
                item['artifact_id']
                for item in files
                if item.get('status') == 'completed' and item.get('engine_document_id')
            }
            row['indexed'] = len(indexed & set(owned['artifacts']))
            if row['indexed'] != case['files']:
                row['errors'].append('Requested files were not confirmed indexed')
            row['vector_count'] = count_chroma(sqlite)
            if row['vector_count']['vectors'] <= 0:
                row['errors'].append('No persisted Chroma vectors observed')
            row['peak_ingest_inflight'] = peak_inflight(receipts)
            row['index_receipts'] = [{k: v for k, v in item.items() if k != 'receipt'} for item in receipts]
    with stage(case['id'] + ':idle_retained'):
        sleep(profile['idle_seconds'])
    return row


def run(profile, api, model, output, sqlite, manifest):
    corpus = load_public_inputs(manifest, profile)
    output.mkdir(mode=0o700, parents=True)
    owned = {'kb': None, 'artifacts': []}
    result = {'passed': False, 'cases': [], 'errors': []}
    suffix = uuid4().hex[:12]
    write_json(output / 'profile.json', profile)
    write_json(output / 'corpus-manifest.json', corpus[0])
    with (output / 'stages.jsonl').open('x') as stream:

        @contextmanager
        def stage(name):
            def log(event):
                stream.write(json.dumps({'stage': name, 'event': event, 'monotonic_ns': monotonic_ns()}) + '\n')
                stream.flush()

            log('start')
            try:
                yield
            finally:
                log('end')

        for case in profile['cases']:
            row = {'id': case['id'], 'errors': []}
            try:
                row = case_run(
                    case,
                    profile,
                    api,
                    model,
                    output,
                    stage,
                    owned,
                    sqlite,
                    suffix,
                    corpus[1][case['id']],
                )
            except Exception as exc:
                row['errors'].append(f'Case aborted: {str(exc) if type(exc) is ValueError else type(exc).__name__}')
            finally:
                with stage(case['id'] + ':cleanup'):
                    if owned['kb']:
                        try:
                            path = f'{KB}/{owned["kb"]}'
                            files = api.request('GET', path + '/files')['files']
                            # Dedicated benchmark KB. Remove attached files through
                            # their public lifecycle before deleting the KB itself.
                            for file in files:
                                if file.get('artifact_id') not in owned['artifacts']:
                                    raise ValueError('Unowned document found in the private benchmark KB')
                                file_id = checked_id(file['uuid'])
                                api.request('DELETE', path + '/files/' + file_id)
                            if api.request('GET', path + '/files')['files']:
                                raise ValueError('Files remained after owned document cleanup')
                            if sqlite.exists() and count_chroma(sqlite)['vectors']:
                                raise ValueError('Vectors remained after owned document cleanup')
                            api.request('DELETE', path)
                            api.request('GET', path, expected=404)
                            owned['kb'] = None
                            if sqlite.exists() and count_chroma(sqlite)['vectors']:
                                row['errors'].append('Indexed vectors remained after owned KB deletion')
                        except Exception as exc:
                            row['errors'].append('KB cleanup failed: ' + type(exc).__name__)
                    for artifact in list(owned['artifacts']):
                        try:
                            path = f'{ARTIFACTS}/{artifact}'
                            if api.request('DELETE', path).get('deleted') is not True:
                                raise ValueError('Missing Artifact deletion receipt')
                            api.request('GET', path, expected=404)
                            owned['artifacts'].remove(artifact)
                        except Exception as exc:
                            row['errors'].append('Artifact cleanup failed: ' + type(exc).__name__)
                    write_json(output / 'owned.json', owned)
                with stage(case['id'] + ':idle_after_cleanup'):
                    sleep(profile['idle_seconds'])
                result['cases'].append(row)
                write_json(output / 'summary.json', result)
            if row['errors']:
                break
    result['passed'] = len(result['cases']) == len(profile['cases']) and all(
        not row['errors'] for row in result['cases']
    )
    write_json(output / 'summary.json', result)
    return result['passed']


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'run'))
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--endpoint')
    parser.add_argument('--workspace')
    parser.add_argument('--token-env')
    parser.add_argument('--embedding-model')
    parser.add_argument('--chroma-sqlite', type=Path)
    parser.add_argument('--public-corpus-manifest', type=Path)
    args = parser.parse_args(argv)
    try:
        profile = load_profile(args.profile)
        if args.command == 'validate':
            return 0
        if not all(
            (
                args.output,
                args.endpoint,
                args.workspace,
                args.token_env,
                args.embedding_model,
                args.chroma_sqlite,
                args.public_corpus_manifest,
            )
        ):
            parser.error(
                'run requires endpoint, workspace, token-env, embedding-model, chroma-sqlite, public-corpus-manifest and output'
            )
        api = CoreHTTP(args.endpoint, args.workspace, os.environ.get(args.token_env), 45)
        return (
            0
            if run(
                profile,
                api,
                checked_id(args.embedding_model),
                args.output,
                args.chroma_sqlite,
                args.public_corpus_manifest,
            )
            else 1
        )
    except (OSError, RuntimeError, ValueError) as exc:
        parser.exit(1, f'Upload-memory benchmark failed: {exc}\n')


if __name__ == '__main__':
    raise SystemExit(main())
