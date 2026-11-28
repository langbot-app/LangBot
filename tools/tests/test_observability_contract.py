import json
from pathlib import Path
import threading
import time

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
    observations = tmp_path / 'observations.jsonl'
    actions.write_text(
        json.dumps({'trace_id': 'Y-1', 'action_id': 'a-1', 'status': 'succeeded'})
        + '\n'
        + json.dumps({'action_id': 'a-2', 'status': 'expired'})
        + '\n'
    )
    arrivals.write_text(json.dumps({'trace_id': 'Y-1', 'action_id': 'a-1', 'run_id': 'run-1', 'arrival_id': 0}) + '\n')
    observations.write_text(json.dumps({'trace_id': 'Y-1', 'observation_id': 'o-1', 'values': {}}) + '\n')

    index_path = tmp_path / 'trace-index.json'
    index = write_trace_index(index_path, [actions, arrivals, observations], run_id='run-1')

    assert index['traces'] == 1
    assert index['indexed_records'] == 3
    assert index['unindexed_records'] == 1
    entry = index['entries'][0]
    assert entry['action_ids'] == ['a-1']
    assert entry['observation_ids'] == ['o-1']
    assert entry['run_ids'] == ['run-1']
    assert {(ref['artifact'], ref['line']) for ref in entry['evidence']} == {
        ('actions.jsonl', 1),
        ('arrivals.jsonl', 1),
        ('observations.jsonl', 1),
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

    try:
        write_trace_index(tmp_path / 'trace-index.json', [evidence])
    except ValueError as exc:
        assert 'invalid JSONL' in str(exc)
    else:
        raise AssertionError('corrupt JSONL must be rejected')


def test_trace_index_keeps_missing_artifact_visible(tmp_path: Path):
    index_path = tmp_path / 'trace-index.json'
    missing = tmp_path / 'missing.jsonl'
    index = write_trace_index(index_path, [missing])

    assert index['missing_artifacts'] == [str(missing)]
    assert index['unindexed_records'] == 0
    manifest = write_manifest(
        tmp_path / 'run-manifest.json',
        run_id='run-3',
        expected_sources=[],
        artifacts=[index_path],
        trace_index=index_path,
    )
    assert manifest['completeness'] == 'incomplete'


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


def test_trace_index_and_manifest_include_service_logs_and_timings(tmp_path: Path):
    actions = tmp_path / 'actions.jsonl'
    arrivals = tmp_path / 'arrivals.jsonl'
    core_log = tmp_path / 'core.log'
    runtime_log = tmp_path / 'runtime.log'

    actions.write_text(json.dumps({'trace_id': 'Y-100', 'action_id': 'a-100', 'status': 'succeeded'}) + '\n')
    arrivals.write_text(
        json.dumps({'trace_id': 'Y-100', 'action_id': 'a-100', 'run_id': 'run-100', 'arrival_id': 0}) + '\n'
    )
    core_log.write_text(
        '\n'.join(
            [
                '[2026-11-28 12:00:00.100] INFO [CORE.agent] run (orchestrator.py:498) [10][Main][ws=w1][c-trace] '
                'agent_runner_timing run_id=run-100 runner=local-agent duration_ms=123.456',
                '[2026-11-28 12:00:00.200] INFO [CORE.agent] run (orchestrator.py:498) [10][Main][ws=w1][c-trace] '
                'agent_runner_timing run_id=run-unmatched runner=local-agent duration_ms=5.000',
                '[2026-11-28 12:00:00.300] INFO [CORE.box] execute (service.py:877) [10][Main][ws=w1][c-trace] '
                'box_execute_timing query_id=q-1 session_id=s-1 placement_ms=1.000 prepare_ms=2.000 '
                'rpc_ms=3.000 post_ms=4.000 total_ms=10.000',
                '[2026-11-28 12:00:00.400] INFO [CORE.box] select (service.py:1987) [10][Main][ws=w1][c-trace] '
                'box_selection_timing workspace_uuid=w1 settings_ms=0.500 backend_info_ms=1.500 '
                'backend_cache_hit=True total_ms=2.000',
            ]
        )
        + '\n'
    )
    runtime_log.write_text(
        '[2026-11-28 12:00:00.350] INFO [BOX.runtime] exec (runtime.py:1777) [20][Main][ws=w1][b-trace] '
        'box_execute_timing session_id=s-1 lock_wait_ms=0.100 session_acquire_ms=0.200 '
        'backend_exec_ms=2.000 runtime_ms=2.300\n'
    )

    index_path = tmp_path / 'trace-index.json'
    index = write_trace_index(
        index_path,
        [actions, arrivals],
        run_id='run-svc-1',
        service_logs={'core': core_log, 'runtime': runtime_log},
    )

    assert index['traces'] == 1
    assert index['timing_counts'] == {
        'agent_runner_timing': 2,
        'box_execute_timing': 2,
        'box_selection_timing': 1,
    }
    assert set(index['service_log_sources']) == {
        'service_log:core',
        'service_log:runtime',
        'agent_runner_timing',
        'box_execute_timing',
        'box_selection_timing',
    }

    entry = index['entries'][0]
    assert entry['trace_id'] == 'Y-100'
    assert entry['run_ids'] == ['run-100']
    assert len(entry['timings']) == 1
    runner_timing = entry['timings'][0]
    assert runner_timing['kind'] == 'agent_runner_timing'
    assert runner_timing['line'] == 1
    assert runner_timing['correlation_level'] == 'run_id'
    assert runner_timing['deterministic_trace_binding'] is True
    assert runner_timing['fields']['duration_ms'] == 123.456
    assert any(ref.get('kind') == 'agent_runner_timing' and ref['line'] == 1 for ref in entry['evidence'])

    secondary = index['secondary_indexes']
    assert 'run-unmatched' in secondary['by_run_id']
    assert secondary['by_run_id']['run-unmatched'][0]['deterministic_trace_binding'] is False
    assert secondary['by_run_id']['run-unmatched'][0]['correlation_level'] == 'uncorrelated'

    assert len(secondary['by_query_id']['q-1']) == 1
    assert secondary['by_query_id']['q-1'][0]['correlation_level'] == 'secondary_query_id'
    assert secondary['by_query_id']['q-1'][0]['deterministic_trace_binding'] is False

    assert len(secondary['by_session_id']['s-1']) == 2
    assert {item['artifact'] for item in secondary['by_session_id']['s-1']} == {'core.log', 'runtime.log'}
    assert all(
        item['correlation_level'] == 'secondary_session_id' and item['deterministic_trace_binding'] is False
        for item in secondary['by_session_id']['s-1']
    )

    assert len(secondary['by_workspace_uuid']['w1']) == 1
    selection = secondary['by_workspace_uuid']['w1'][0]
    assert selection['kind'] == 'box_selection_timing'
    assert selection['correlation_level'] == 'secondary_workspace_uuid'
    assert selection['deterministic_trace_binding'] is False
    assert selection['fields']['backend_cache_hit'] is True

    manifest = write_manifest(
        tmp_path / 'run-manifest.json',
        run_id='run-svc-1',
        expected_sources=[
            'service_log:core',
            'service_log:runtime',
            'agent_runner_timing',
            'box_execute_timing',
            'box_selection_timing',
        ],
        artifacts=[actions, arrivals, index_path],
        trace_index=index_path,
        service_logs={'core': core_log, 'runtime': runtime_log},
    )
    assert manifest['completeness'] == 'complete'
    hashed_paths = {row['path'] for row in manifest['artifacts']}
    assert {str(core_log), str(runtime_log), str(index_path)} <= hashed_paths
    assert all(row['sha256'] for row in manifest['artifacts'])
    assert manifest['trace_index']['service_logs'] == 2
    assert manifest['trace_index']['timing_counts']['agent_runner_timing'] == 2
    assert manifest['trace_index']['secondary_index_counts']['by_session_id'] == 1


def test_missing_service_log_marks_manifest_incomplete(tmp_path: Path):
    missing_log = tmp_path / 'missing-core.log'
    index_path = tmp_path / 'trace-index.json'
    index = write_trace_index(index_path, [], service_logs={'core': missing_log})
    assert index['missing_artifacts'] == [str(missing_log)]
    manifest = write_manifest(
        tmp_path / 'run-manifest.json',
        run_id='run-missing-log',
        expected_sources=['service_log:core'],
        artifacts=[index_path],
        trace_index=index_path,
        service_logs={'core': missing_log},
    )
    assert manifest['completeness'] == 'incomplete'
    assert str(missing_log) in manifest['missing_artifacts']
    assert 'service_log:core' in manifest['missing_sources']
