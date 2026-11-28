import json
from pathlib import Path
import threading
import time

from tools.regression.arrival_schedule import run_open_loop
from tools.regression.observability_contract import ActionWriter, ObservationWriter, write_manifest


def test_action_writer_records_terminal_failure_and_manifest(tmp_path: Path):
    writer = ActionWriter(tmp_path / 'actions.jsonl')
    action = writer.begin('demo', trace_id='Y-0000000000000001')
    writer.finish(action, 'failed', error=RuntimeError('boom'))
    writer.close()

    record = json.loads((tmp_path / 'actions.jsonl').read_text())
    assert record['schema_version'] == '1'
    assert record['status'] == 'failed'
    assert record['error_type'] == 'RuntimeError'

    manifest = write_manifest(
        tmp_path / 'run-manifest.json',
        run_id='run-1',
        expected_sources=['demo'],
        artifacts=[tmp_path / 'actions.jsonl'],
    )
    assert manifest['completeness'] == 'complete'
    assert manifest['artifacts'][0]['sha256']


def test_observation_writer_preserves_missing_reason(tmp_path: Path):
    writer = ObservationWriter(tmp_path / 'observations.jsonl')
    writer.write('host', {'cpu': 1.0}, missing_reasons=['cgroup_unavailable'])
    record = json.loads((tmp_path / 'observations.jsonl').read_text())
    assert record['schema_version'] == '1'
    assert record['sequence'] == 1
    assert record['missing_reasons'] == ['cgroup_unavailable']


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
