"""Upload and score BEIR SciFact through an isolated LangBot Core."""

import argparse
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, datetime
import json
import os
from pathlib import Path
from time import monotonic, sleep
from uuid import uuid4

from tools.regression.vdb_benchmark_counts import count_chroma
from tools.regression.vdb_benchmark_http import (
    ARTIFACTS,
    KB,
    LANGRAG,
    PARSER,
    RETRIEVAL,
    CoreHTTP,
    bounded_error,
    checked_id,
    elapsed_ms,
    remaining,
    write_json,
    write_row,
)
from tools.regression.vdb_benchmark_public import plan, score_chunks

TOP_K = 10


def latency(rows):
    if not rows:
        return None
    values = sorted(rows)

    def percentile(p):
        index = (len(values) - 1) * p
        lo = int(index)
        hi = min(lo + 1, len(values) - 1)
        return round(values[lo] + (values[hi] - values[lo]) * (index - lo), 3)

    return {'samples': len(values), **{f'p{p}': percentile(p / 100) for p in (50, 95, 99)}, 'max': round(values[-1], 3)}


def run(manifest, docs, queries, api, model, output, sqlite, provenance):
    output.mkdir(mode=0o700)
    write_json(output / 'manifest.json', manifest)
    profile = manifest['profile']
    settings = {**RETRIEVAL, 'top_k': TOP_K}
    origins = {}
    cleanup = {'kb': None, 'artifacts': []}
    results = {'passed': False, 'errors': [], 'started_at': datetime.now(UTC).isoformat()}
    results.update(
        backend='chroma',
        path='Core HTTP Artifact upload and knowledge.retrieve → GeneralParsers/LangRAG → Core Chroma',
        provenance=provenance,
        dataset=manifest['dataset'],
        population=manifest['population'],
        planned_documents=len(manifest['documents']),
        planned_test_queries=len(manifest['scored_query_ids']),
        planned_warmup_queries=len(manifest['warmup_query_ids']),
    )
    owned_file = output / 'owned.json'
    summary = output / 'summary.json'
    write_json(owned_file, cleanup)
    write_json(summary, results)
    write_rows = []
    query_rows = []
    warmup_rows = []

    def raw_query(text):
        start = monotonic()
        response = api.request('POST', path + '/retrieve', {'query': text, 'retrieval_settings': settings})
        return response['results'], elapsed_ms(start)

    def query(qid, warmup=False):
        start = monotonic()
        row = {'qid': qid, 'phase': 'warmup' if warmup else 'measure', 'status': 'failed'}
        try:
            chunks, duration = raw_query(queries[qid]['text'])
            if not isinstance(chunks, list) or not chunks:
                raise ValueError('Expected nonempty LangRAG retrieval from the completed corpus')
            file_ids = [checked_id(hit['metadata']['file_id']) for hit in chunks]
            if warmup:
                if any(doc not in origins for doc in file_ids):
                    raise ValueError('Warmup returned an unowned file')
            else:
                row.update(score_chunks(file_ids, origins, manifest['qrels'][qid], TOP_K))
            row.update(status='ok', chunks_returned=len(chunks), latency_ms=duration)
        except Exception as exc:
            row.update(error=bounded_error(exc), latency_ms=elapsed_ms(start))
        return row

    with (output / 'ingest.jsonl').open('x') as ingest, (output / 'queries.jsonl').open('x') as scored:
        try:
            begin = monotonic()
            receipt = api.request(
                'POST',
                KB,
                {
                    'name': 'QA public retrieval ' + uuid4().hex,
                    'knowledge_engine_plugin_id': LANGRAG,
                    'creation_settings': {
                        'embedding_model_uuid': checked_id(model),
                        'index_type': 'chunk',
                        'chunk_size': 512,
                        'overlap': 50,
                    },
                    'retrieval_settings': settings,
                },
            )
            cleanup['kb'] = checked_id(receipt['uuid'])
            write_json(owned_file, cleanup)
            path = KB + '/' + cleanup['kb']
            if api.request('GET', path)['base']['knowledge_engine_plugin_id'] != LANGRAG or raw_query('empty')[0]:
                raise ValueError('Expected a fresh Core LangRAG KB')
            results['setup_ms'] = elapsed_ms(begin)
            start_ingest = monotonic()
            artifact_to_doc = {}
            for i, did in enumerate(manifest['documents']):
                begun = monotonic()
                row = {'doc_id': did, 'status': 'failed'}
                try:
                    doc = docs[did]
                    text = f'{doc["title"]}\n\n{doc["text"]}'
                    artifact = api.upload(f'beir-scifact-{checked_id(did)}.txt', text)
                    row.update(upload_ms=elapsed_ms(begun), utf8_bytes=len(text.encode()))
                    if artifact in artifact_to_doc:
                        raise ValueError('Distinct public document unexpectedly reused an Artifact')
                    artifact_to_doc[artifact] = did
                    cleanup['artifacts'].append(artifact)
                    write_json(owned_file, cleanup)
                    start_index = monotonic()
                    deadline = start_index + profile['index_timeout_seconds']
                    timeout = profile['request_timeout_seconds']
                    task = api.request(
                        'POST',
                        path + '/files/artifact',
                        {'artifact_id': artifact, 'parser_plugin_id': PARSER},
                        timeout=remaining(deadline, timeout),
                    )['task_id']
                    if type(task) is not int or task < 0:
                        raise ValueError('Malformed indexing task receipt')
                    while True:
                        state = api.request(
                            'GET', f'/api/v1/system/tasks/{task}', timeout=remaining(deadline, timeout)
                        )['runtime']
                        if state['done']:
                            if state.get('cancelled') or state.get('exception'):
                                raise ValueError('LangRAG indexing task failed')
                            break
                        sleep(min(0.1, remaining(deadline, timeout)))
                    row.update(status='task_done', index_ms=elapsed_ms(start_index))
                except Exception as exc:
                    row['error'] = bounded_error(exc)
                row.update(total_ms=elapsed_ms(begun))
                write_row(ingest, row)
                write_rows.append(row)
                if row['status'] != 'task_done':
                    raise ValueError('Public document ingestion failed: ' + row['error'])
                if (i + 1) % 20 == 0:
                    results['completed_index_tasks'] = i + 1
                    write_json(summary, results)
            results['ingest_ms'] = elapsed_ms(start_ingest)
            results['indexed_payload_bytes'] = sum(r['utf8_bytes'] for r in write_rows)
            files = api.request('GET', path + '/files')['files']
            if len(files) != len(artifact_to_doc) or {f.get('artifact_id') for f in files} != set(artifact_to_doc):
                raise ValueError('Persisted file receipts differ from the exact expected public corpus')
            for file in files:
                if file['status'] != 'completed':
                    raise ValueError('A persisted public file is not completed')
                origins[checked_id(file['engine_document_id'])] = artifact_to_doc[file['artifact_id']]
            if len(origins) != len(files):
                raise ValueError('Multiple public files share a LangRAG document receipt')
            results['confirmed_indexed_documents'] = len(origins)
            results['persisted_chroma'] = count_chroma(sqlite)
            if (
                results['persisted_chroma']['vectors'] < len(origins)
                or results['persisted_chroma']['dimensions'] != 384
            ):
                raise ValueError('Chroma cardinality or dimension mismatches independently checked corpus')
            for qid in manifest['warmup_query_ids']:
                row = query(qid, warmup=True)
                write_row(scored, row)
                warmup_rows.append(row)
                if row['status'] != 'ok':
                    raise ValueError('Public warmup retrieval failed: ' + row['error'])
            with ThreadPoolExecutor(max_workers=profile['workers']) as pool:
                start_measure = monotonic()
                for row in pool.map(query, manifest['scored_query_ids']):
                    write_row(scored, row)
                    query_rows.append(row)
                results['measure_ms'] = elapsed_ms(start_measure)
            if any(row['status'] != 'ok' for row in query_rows):
                raise ValueError('At least one selected test query failed')
        except Exception as exc:
            results['errors'].append(bounded_error(exc))
        finally:
            results.update(
                completed_index_tasks=sum(row['status'] == 'task_done' for row in write_rows),
                ingest_failures=sum(row['status'] != 'task_done' for row in write_rows),
                actual_test_queries=len(query_rows),
                successful_test_queries=sum(row['status'] == 'ok' for row in query_rows),
                actual_warmup_queries=len(warmup_rows),
                upload_http_ms=latency([r['upload_ms'] for r in write_rows if 'upload_ms' in r]),
                index_to_task_done_ms=latency([r['index_ms'] for r in write_rows if 'index_ms' in r]),
                retrieval_http_ms=latency([r['latency_ms'] for r in query_rows if r['status'] == 'ok']),
            )
            if query_rows and results['successful_test_queries'] == results['planned_test_queries']:
                for key in ('recall_at_10', 'ndcg_at_10'):
                    results[key] = sum(r[key] for r in query_rows) / len(query_rows)
                results['retrieval_queries_per_second'] = 1000 * len(query_rows) / results['measure_ms']
            if results.get('ingest_ms'):
                results['ingest_docs_per_second'] = 1000 * results['completed_index_tasks'] / results['ingest_ms']
            write_json(summary, results)
            if cleanup['kb']:
                try:
                    path = KB + '/' + cleanup['kb']
                    owned_artifacts = set(cleanup['artifacts'])
                    for file in api.request('GET', path + '/files')['files']:
                        if file.get('artifact_id') not in owned_artifacts:
                            raise ValueError('Unowned file found in private benchmark KB')
                        api.request('DELETE', path + '/files/' + checked_id(file['uuid']))
                    if api.request('GET', path + '/files')['files']:
                        raise ValueError('Persisted KB files remained after cleanup')
                    if sqlite.exists() and count_chroma(sqlite)['vectors']:
                        raise ValueError('Committed vectors remained after cleanup')
                    api.request('DELETE', path)
                    api.request('GET', path, expected=404)
                    cleanup['kb'] = None
                except Exception as exc:
                    results['errors'].append('Owned KB cleanup failed: ' + bounded_error(exc))
            if cleanup['artifacts']:
                unrecovered = []
                for artifact in cleanup['artifacts']:
                    try:
                        path = ARTIFACTS + '/' + artifact
                        if api.request('DELETE', path).get('deleted') is not True:
                            raise ValueError('Missing Artifacts deletion receipt')
                        api.request('GET', path, expected=404)
                    except Exception:
                        unrecovered.append(artifact)
                cleanup['artifacts'] = unrecovered
                if unrecovered:
                    results['errors'].append('Could not verify deletion of one or more owned Artifacts')
            write_json(owned_file, cleanup)
            results['cleanup_verified'] = not cleanup['kb'] and not cleanup['artifacts']
            results['passed'] = not results['errors'] and results['cleanup_verified'] and 'recall_at_10' in results
            write_json(summary, results)
    return results['passed']


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('validate', 'run'))
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--assets', required=True, type=Path)
    parser.add_argument('--endpoint')
    parser.add_argument('--workspace')
    parser.add_argument('--token-env')
    parser.add_argument('--embedding-model')
    parser.add_argument('--output', type=Path)
    parser.add_argument('--chroma-sqlite', type=Path)
    parser.add_argument('--provenance', type=Path)
    args = parser.parse_args()
    manifest, docs, queries = plan(args.profile, args.assets)
    if args.command == 'validate':
        print(json.dumps(manifest))
        return 0
    if not all((args.endpoint, args.workspace, args.token_env, args.embedding_model, args.output, args.chroma_sqlite)):
        parser.error('Disposable Core endpoint, workspace, token env, model, output and Chroma SQLite are required')
    api = CoreHTTP(
        args.endpoint, args.workspace, os.environ.get(args.token_env), manifest['profile']['request_timeout_seconds']
    )
    provenance = json.loads(args.provenance.read_text()) if args.provenance else None
    return (
        0 if run(manifest, docs, queries, api, args.embedding_model, args.output, args.chroma_sqlite, provenance) else 1
    )


if __name__ == '__main__':
    raise SystemExit(main())
