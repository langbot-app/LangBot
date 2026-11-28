import json
from pathlib import Path
import threading
import time

import pytest

from tools.regression.arrival_schedule import run_open_loop
from tools.regression.observability_contract import ActionWriter, ObservationWriter, write_manifest, write_trace_index


def test_action_writer_records_terminal_failure_and_manifest(tmp_path: Path):
    writer = ActionWriter(tmp_path / 'actions.jsonl')
    action = writer.begin('demo', trace_id='Y-0000000000000001')
    writer.finish(action, 'failed', error=RuntimeError('boom'))
    writer.close()

    record = json.loads((tmp_path / 'actions.jsonl').read_text())
    assert record['schema_version'] == '1'
    assert record['status'] == 'failed'
    assert record['error_type'] == 'RuntimeError'
    assert record['trace_id'].startswith('Y-')

    manifest = write_manifest(
        tmp_path / 'run-manifest.json',
        run_id='run-1',
        expected_sources=['demo'],
        observed_sources=writer.sources,
        artifacts=[tmp_path / 'actions.jsonl'],
    )
    assert manifest['completeness'] == 'complete'
    assert manifest['missing_sources'] == []
    assert manifest['artifacts'][0]['sha256']


def test_observation_writer_preserves_missing_reason(tmp_path: Path):
    writer = ObservationWriter(tmp_path / 'observations.jsonl')
    writer.write('host', {'cpu': 1.0}, missing_reasons=['cgroup_unavailable'])
    record = json.loads((tmp_path / 'observations.jsonl').read_text())
    assert record['schema_version'] == '1'
    assert record['sequence'] == 1
    assert record['missing_reasons'] == ['cgroup_unavailable']


def test_manifest_marks_missing_observation_source_incomplete(tmp_path: Path):
    manifest = write_manifest(
        tmp_path / 'run-manifest.json',
        run_id='run-2',
        expected_sources=['regression_gate'],
        observed_sources=[],
        artifacts=[],
    )
    assert manifest['completeness'] == 'incomplete'
    assert manifest['missing_sources'] == ['regression_gate']


def test_trace_index_groups_action_and_arrival_evidence(tmp_path: Path):
    actions = tmp_path / 'actions.jsonl'
    arrivals = tmp_path / 'arrivals.jsonl'
    actions.write_text(
        json.dumps({'trace_id': 'Y-1', 'action_id': 'a-1', 'status': 'succeeded'}) + '\n'
        + json.dumps({'action_id': 'a-2', 'status': 'expired'})
        + '\n'
    )
    arrivals.write_text(json.dumps({'trace_id': 'Y-1', 'action_id': 'a-1', 'arrival_id': 0}) + '\n')

    index_path = tmp_path / 'trace-index.json'
    index = write_trace_index(index_path, [actions, arrivals], run_id='run-1')

    assert index['traces'] == 1
    assert index['indexed_records'] == 2
    assert index['unindexed_records'] == 1
    entry = index['entries'][0]
    assert entry['action_ids'] == ['a-1']
    assert {(ref['artifact'], ref['line']) for ref in entry['evidence']} == {
        ('actions.jsonl', 1),
        ('arrivals.jsonl', 1),
    }
    manifest = write_manifest(
        tmp_path / 'run-manifest.json',
        run_id='run-1',
        expected_sources=[],
        artifacts=[actions, arrivals, index_path],
        trace_index=index_path,
    )
    assert manifest['completeness'] == 'complete'
    assert manifest['trace_index']['traces'] == 1


def test_trace_index_rejects_corrupt_jsonl(tmp_path: Path):
    evidence = tmp_path / 'actions.jsonl'
    evidence.write_text('{broken\n')

    with pytest.raises(ValueError, match='invalid JSONL'):
        write_trace_index(tmp_path / 'trace-index.json', [evidence])


def test_trace_index_keeps_missing_artifact_visible(tmp_path: Path):
    index = write_trace_index(tmp_path / 'trace-index.json', [tmp_path / 'missing.jsonl'])

    assert index['missing_artifacts'] == [str(tmp_path / 'missing.jsonl')]
    assert index['unindexed_records'] == 0


def test_open_loop_records_failed_action_without_breaking_accounting(tmp_path: Path):
    writer = ActionWriter(tmp_path / 'actions.jsonl')
    settled = []

    def execute(_item):
        raise RuntimeError('request failed')

    summary = run_open_loop(
        started=time.monotonic(),
        duration=0.01,
        rps=10,
        workers=1,
        queue_capacity=1,
        execute=execute,
        key_for=lambda _index: None,
        blocked=lambda _key: False,
        settle=lambda item, outcome, _row: settled.append((item['arrival_id'], outcome)),
        stop=threading.Event(),
        action_writer=writer,
    )
    writer.close()
    assert summary['failed'] == 1
    assert summary['conserved']
    assert settled == [(0, 'failed')]
    records = [json.loads(line) for line in (tmp_path / 'actions.jsonl').read_text().splitlines()]
    assert records and all(record['status'] == 'failed' for record in records)
