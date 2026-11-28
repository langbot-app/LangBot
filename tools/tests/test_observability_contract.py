import asyncio
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import threading
import time
import unittest

from tools.regression.arrival_schedule import run_open_loop
from tools.regression.observability_contract import (
    ActionWriter,
    ObservationWriter,
    inflight_journal_path,
    inspect_action_artifacts,
    reconcile_inflight_actions,
    write_manifest,
    write_trace_index,
)
from tools.regression.service_logs import records as parse_service_log_records


class ObservabilityContractTests(unittest.TestCase):
    def test_action_writer_records_terminal_failure_and_manifest(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            writer = ActionWriter(tmp_path / 'actions.jsonl')
            action = writer.begin('demo', trace_id='Y-0000000000000001')
            writer.finish(action, 'failed', error=RuntimeError('boom'))
            writer.close()

            record = json.loads((tmp_path / 'actions.jsonl').read_text())
            self.assertEqual(record['schema_version'], '1')
            self.assertEqual(record['status'], 'failed')
            self.assertEqual(record['error_type'], 'RuntimeError')
            self.assertTrue(record['trace_id'].startswith('Y-'))

            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-1',
                expected_sources=['demo'],
                observed_sources=writer.sources,
                artifacts=[tmp_path / 'actions.jsonl'],
            )
            self.assertEqual(manifest['completeness'], 'complete')
            self.assertEqual(manifest['missing_sources'], [])
            self.assertTrue(manifest['artifacts'][0]['sha256'])

    def test_observation_writer_preserves_missing_reason(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            writer = ObservationWriter(tmp_path / 'observations.jsonl')
            writer.write('host', {'cpu': 1.0}, missing_reasons=['cgroup_unavailable'])
            record = json.loads((tmp_path / 'observations.jsonl').read_text())
            self.assertEqual(record['schema_version'], '1')
            self.assertEqual(record['sequence'], 1)
            self.assertEqual(record['missing_reasons'], ['cgroup_unavailable'])

    def test_manifest_marks_missing_observation_source_incomplete(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-2',
                expected_sources=['regression_gate'],
                observed_sources=[],
                artifacts=[],
            )
            self.assertEqual(manifest['completeness'], 'incomplete')
            self.assertEqual(manifest['missing_sources'], ['regression_gate'])

    def test_trace_index_groups_action_and_arrival_evidence(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            actions = tmp_path / 'actions.jsonl'
            arrivals = tmp_path / 'arrivals.jsonl'
            observations = tmp_path / 'observations.jsonl'
            actions.write_text(
                json.dumps({'trace_id': 'Y-1', 'action_id': 'a-1', 'status': 'succeeded'})
                + '\n'
                + json.dumps({'action_id': 'a-2', 'status': 'expired'})
                + '\n'
            )
            arrivals.write_text(
                json.dumps({'trace_id': 'Y-1', 'action_id': 'a-1', 'run_id': 'run-1', 'arrival_id': 0}) + '\n'
            )
            observations.write_text(json.dumps({'trace_id': 'Y-1', 'observation_id': 'o-1', 'values': {}}) + '\n')

            index_path = tmp_path / 'trace-index.json'
            index = write_trace_index(index_path, [actions, arrivals, observations], run_id='run-1')

            self.assertEqual(index['traces'], 1)
            self.assertEqual(index['indexed_records'], 3)
            self.assertEqual(index['unindexed_records'], 1)
            entry = index['entries'][0]
            self.assertEqual(entry['action_ids'], ['a-1'])
            self.assertEqual(entry['observation_ids'], ['o-1'])
            self.assertEqual(entry['run_ids'], ['run-1'])
            self.assertEqual(
                {(ref['artifact'], ref['line']) for ref in entry['evidence']},
                {
                    ('actions.jsonl', 1),
                    ('arrivals.jsonl', 1),
                    ('observations.jsonl', 1),
                },
            )
            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-1',
                expected_sources=[],
                artifacts=[actions, arrivals, index_path],
                trace_index=index_path,
            )
            self.assertEqual(manifest['completeness'], 'complete')
            self.assertEqual(manifest['trace_index']['traces'], 1)

    def test_trace_index_rejects_corrupt_jsonl(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            evidence = tmp_path / 'actions.jsonl'
            evidence.write_text('{broken\n')

            with self.assertRaises(ValueError) as raised:
                write_trace_index(tmp_path / 'trace-index.json', [evidence])
            self.assertIn('invalid JSONL', str(raised.exception))

    def test_trace_index_keeps_missing_artifact_visible(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            index_path = tmp_path / 'trace-index.json'
            missing = tmp_path / 'missing.jsonl'
            index = write_trace_index(index_path, [missing])

            self.assertEqual(index['missing_artifacts'], [str(missing)])
            self.assertEqual(index['unindexed_records'], 0)
            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-3',
                expected_sources=[],
                artifacts=[index_path],
                trace_index=index_path,
            )
            self.assertEqual(manifest['completeness'], 'incomplete')

    def test_open_loop_records_failed_action_without_breaking_accounting(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
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
            self.assertEqual(summary['failed'], 1)
            self.assertTrue(summary['conserved'])
            self.assertEqual(settled, [(0, 'failed')])
            records = [json.loads(line) for line in (tmp_path / 'actions.jsonl').read_text().splitlines()]
            self.assertTrue(records and all(record['status'] == 'failed' for record in records))

    def test_trace_index_and_manifest_include_service_logs_and_timings(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
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

            self.assertEqual(index['traces'], 1)
            self.assertEqual(
                index['timing_counts'],
                {
                    'agent_runner_timing': 2,
                    'box_execute_timing': 2,
                    'box_selection_timing': 1,
                },
            )
            self.assertEqual(
                set(index['service_log_sources']),
                {
                    'service_log:core',
                    'service_log:runtime',
                    'agent_runner_timing',
                    'box_execute_timing',
                    'box_selection_timing',
                },
            )

            entry = index['entries'][0]
            self.assertEqual(entry['trace_id'], 'Y-100')
            self.assertEqual(entry['run_ids'], ['run-100'])
            self.assertEqual(len(entry['timings']), 1)
            runner_timing = entry['timings'][0]
            self.assertEqual(runner_timing['kind'], 'agent_runner_timing')
            self.assertEqual(runner_timing['line'], 1)
            self.assertEqual(runner_timing['correlation_level'], 'run_id')
            self.assertTrue(runner_timing['deterministic_trace_binding'])
            self.assertEqual(runner_timing['fields']['duration_ms'], 123.456)
            self.assertTrue(
                any(ref.get('kind') == 'agent_runner_timing' and ref['line'] == 1 for ref in entry['evidence'])
            )

            secondary = index['secondary_indexes']
            self.assertIn('run-unmatched', secondary['by_run_id'])
            self.assertFalse(secondary['by_run_id']['run-unmatched'][0]['deterministic_trace_binding'])
            self.assertEqual(secondary['by_run_id']['run-unmatched'][0]['correlation_level'], 'uncorrelated')

            self.assertEqual(len(secondary['by_query_id']['q-1']), 1)
            self.assertEqual(secondary['by_query_id']['q-1'][0]['correlation_level'], 'secondary_query_id')
            self.assertFalse(secondary['by_query_id']['q-1'][0]['deterministic_trace_binding'])

            self.assertEqual(len(secondary['by_session_id']['s-1']), 2)
            self.assertEqual(
                {item['artifact'] for item in secondary['by_session_id']['s-1']},
                {'core.log', 'runtime.log'},
            )
            self.assertTrue(
                all(
                    item['correlation_level'] == 'secondary_session_id' and item['deterministic_trace_binding'] is False
                    for item in secondary['by_session_id']['s-1']
                )
            )

            self.assertEqual(len(secondary['by_workspace_uuid']['w1']), 1)
            selection = secondary['by_workspace_uuid']['w1'][0]
            self.assertEqual(selection['kind'], 'box_selection_timing')
            self.assertEqual(selection['correlation_level'], 'secondary_workspace_uuid')
            self.assertFalse(selection['deterministic_trace_binding'])
            self.assertTrue(selection['fields']['backend_cache_hit'])

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
            self.assertEqual(manifest['completeness'], 'complete')
            hashed_paths = {row['path'] for row in manifest['artifacts']}
            self.assertTrue({str(core_log), str(runtime_log), str(index_path)} <= hashed_paths)
            self.assertTrue(all(row['sha256'] for row in manifest['artifacts']))
            self.assertEqual(manifest['trace_index']['service_logs'], 2)
            self.assertEqual(manifest['trace_index']['timing_counts']['agent_runner_timing'], 2)
            self.assertEqual(manifest['trace_index']['secondary_index_counts']['by_session_id'], 1)

    def test_truncated_timing_and_embedded_cr_preserve_line_numbers(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            arrivals = tmp_path / 'arrivals.jsonl'
            arrivals.write_text(
                json.dumps({'trace_id': 'Y-101', 'action_id': 'a-101', 'run_id': 'run-101', 'arrival_id': 0}) + '\n'
            )
            core_log = tmp_path / 'core.log'
            core_log.write_bytes(
                (
                    '[2026-11-28 12:00:00.100] INFO [CORE.agent] run (orchestrator.py:498) [10][Main][ws=w1][c-trace] '
                    'progress\r50%\n'
                    '[2026-11-28 12:00:00.200] INFO [CORE.agent] run (orchestrator.py:498) [10][Main][ws=w1][c-trace] '
                    'agent_runner_timing run_id=run-101 runner=local-agent dur\n'
                    '[2026-11-28 12:00:00.300] INFO [CORE.agent] run (orchestrator.py:498) [10][Main][ws=w1][c-trace] '
                    'agent_runner_timing run_id=run-101 runner=local-agent duration_ms=12.500\n'
                ).encode('utf-8')
            )
            with core_log.open(encoding='utf-8', newline='\n') as stream:
                parsed = list(parse_service_log_records(stream, 'core'))
            self.assertEqual([item.log_line for item in parsed], [1, 2, 3])

            index_path = tmp_path / 'trace-index.json'
            index = write_trace_index(index_path, [arrivals], service_logs={'core': core_log})
            self.assertEqual(index['timing_counts']['agent_runner_timing'], 1)
            self.assertEqual(len(index['secondary_indexes']['malformed_timings']), 1)
            self.assertEqual(index['secondary_indexes']['malformed_timings'][0]['line'], 2)
            self.assertEqual(len(index['entries'][0]['timings']), 1)
            self.assertEqual(index['entries'][0]['timings'][0]['line'], 3)

    def test_missing_service_log_marks_manifest_incomplete(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            missing_log = tmp_path / 'missing-core.log'
            index_path = tmp_path / 'trace-index.json'
            index = write_trace_index(index_path, [], service_logs={'core': missing_log})
            self.assertEqual(index['missing_artifacts'], [str(missing_log)])
            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-missing-log',
                expected_sources=['service_log:core'],
                artifacts=[index_path],
                trace_index=index_path,
                service_logs={'core': missing_log},
            )
            self.assertEqual(manifest['completeness'], 'incomplete')
            self.assertIn(str(missing_log), manifest['missing_artifacts'])
            self.assertIn('service_log:core', manifest['missing_sources'])

    def test_observation_scope_splits_global_samples_from_missing_trace_defects(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            observations = tmp_path / 'observations.jsonl'
            actions = tmp_path / 'actions.jsonl'
            writer = ObservationWriter(observations)
            writer.write('regression_gate', {'cpu': 0.5}, scope='global')
            writer.write('request_probe', {'latency_ms': 12.0}, trace_id='Y-200', scope='request')

            with self.assertRaises(ValueError) as raised:
                writer.write('regression_gate', {'cpu': 0.5}, trace_id='Y-200', scope='global')
            self.assertIn('global observations', str(raised.exception))

            with self.assertRaises(ValueError) as raised:
                writer.write('request_probe', {'latency_ms': 1.0}, trace_id='   ', scope='request')
            self.assertIn('non-empty string', str(raised.exception))

            with self.assertRaises(ValueError) as raised:
                writer.write('regression_gate', {'cpu': 0.5}, scope='unknown')
            self.assertIn('unknown observation scope', str(raised.exception))

            actions.write_text(json.dumps({'action_id': 'a-legacy', 'status': 'expired'}) + '\n')

            index_path = tmp_path / 'trace-index.json'
            index = write_trace_index(index_path, [observations, actions], run_id='run-scope-ok')
            self.assertEqual(index['traces'], 1)
            self.assertEqual(index['indexed_records'], 1)
            self.assertEqual(index['global_observations'], 1)
            self.assertEqual(index['missing_trace_observations'], 0)
            self.assertEqual(index['unindexed_legacy_records'], 1)
            self.assertEqual(index['unindexed_records'], 1)

            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-scope-ok',
                expected_sources=['regression_gate', 'request_probe'],
                observed_sources=writer.sources,
                artifacts=[observations, actions, index_path],
                trace_index=index_path,
            )
            self.assertEqual(manifest['completeness'], 'complete')
            self.assertEqual(manifest['trace_index']['global_observations'], 1)
            self.assertEqual(manifest['trace_index']['missing_trace_observations'], 0)
            self.assertEqual(manifest['trace_index']['unindexed_legacy_records'], 1)
            self.assertEqual(manifest['trace_index']['unindexed_records'], 1)

            writer.write('request_probe', {'latency_ms': 30.0}, scope='request')
            index_with_defect = write_trace_index(index_path, [observations, actions], run_id='run-scope-defect')
            self.assertEqual(index_with_defect['global_observations'], 1)
            self.assertEqual(index_with_defect['missing_trace_observations'], 1)
            self.assertEqual(index_with_defect['unindexed_legacy_records'], 1)
            self.assertEqual(index_with_defect['unindexed_records'], 2)

            defect_manifest = write_manifest(
                tmp_path / 'run-manifest-defect.json',
                run_id='run-scope-defect',
                expected_sources=['regression_gate', 'request_probe'],
                observed_sources=writer.sources,
                artifacts=[observations, actions, index_path],
                trace_index=index_path,
            )
            self.assertEqual(defect_manifest['completeness'], 'incomplete')
            self.assertEqual(defect_manifest['trace_index']['missing_trace_observations'], 1)

    def test_global_scope_rejects_non_observation_request_identity_and_whitespace_trace(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            observations = tmp_path / 'observations.jsonl'
            observations.write_text(
                '\n'.join(
                    [
                        json.dumps({'scope': 'global', 'action_id': 'a-1', 'trace_id': None}),
                        json.dumps({'observation_id': 'o-1', 'scope': 'global', 'run_id': 'run-1', 'trace_id': None}),
                        json.dumps({'observation_id': 'o-2', 'scope': 'request', 'trace_id': '   '}),
                        json.dumps({'observation_id': 'o-3', 'scope': 'global', 'trace_id': 123}),
                    ]
                )
                + '\n'
            )
            index_path = tmp_path / 'trace-index.json'
            index = write_trace_index(index_path, [observations], run_id='run-bad-global')
            self.assertEqual(index['traces'], 0)
            self.assertEqual(index['global_observations'], 0)
            self.assertEqual(index['missing_trace_observations'], 4)
            self.assertEqual(index['unindexed_records'], 4)

            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-bad-global',
                expected_sources=[],
                artifacts=[observations, index_path],
                trace_index=index_path,
            )
            self.assertEqual(manifest['completeness'], 'incomplete')

    def test_action_writer_sigkill_recovery_and_manifest_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            actions_path = tmp_path / 'actions.jsonl'
            ready_path = tmp_path / 'ready.json'
            child_code = (
                'import json, time; from pathlib import Path; '
                'from tools.regression.observability_contract import ActionWriter; '
                f'w = ActionWriter(Path({str(actions_path)!r})); '
                'a = w.begin("sigkill_op", trace_id="Y-deadbeef00000001", metadata={"step": 1}); '
                f'Path({str(ready_path)!r}).write_text(json.dumps({{"action_id": a.action_id}})); '
                'time.sleep(30)'
            )
            proc = subprocess.Popen([sys.executable, '-c', child_code], cwd=Path.cwd())
            try:
                deadline = time.monotonic() + 5
                while not ready_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready_path.exists(), 'child did not register inflight action in time')
                action_id = json.loads(ready_path.read_text())['action_id']
                os.kill(proc.pid, signal.SIGKILL)
                proc.wait(timeout=5)
            finally:
                if proc.poll() is None:
                    os.kill(proc.pid, signal.SIGKILL)
                    proc.wait(timeout=5)

            journal = inflight_journal_path(actions_path)
            self.assertTrue(journal.is_file())
            self.assertFalse(actions_path.exists())

            pre_manifest = write_manifest(
                tmp_path / 'pre-manifest.json',
                run_id='run-sigkill-pre',
                expected_sources=[],
                artifacts=[actions_path],
            )
            self.assertEqual(pre_manifest['completeness'], 'interrupted')
            self.assertEqual(pre_manifest['actions']['unclosed_inflight'], 1)
            self.assertEqual(pre_manifest['actions']['unclosed_action_ids'], [action_id])

            recovered = reconcile_inflight_actions(actions_path, reason='sigkill')
            self.assertEqual(len(recovered), 1)
            self.assertEqual(recovered[0]['action_id'], action_id)
            self.assertEqual(recovered[0]['trace_id'], 'Y-deadbeef00000001')
            self.assertEqual(recovered[0]['status'], 'interrupted')
            self.assertEqual(recovered[0]['metadata']['interrupt_reason'], 'sigkill')
            self.assertTrue(recovered[0]['metadata']['recovered_from_inflight'])
            self.assertFalse(journal.exists())
            self.assertEqual(reconcile_inflight_actions(actions_path, reason='sigkill'), [])

            index_path = tmp_path / 'trace-index.json'
            index = write_trace_index(index_path, [actions_path], run_id='run-sigkill')
            self.assertEqual(index['traces'], 1)
            self.assertEqual(index['entries'][0]['trace_id'], 'Y-deadbeef00000001')
            self.assertEqual(index['entries'][0]['action_ids'], [action_id])

            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-sigkill',
                expected_sources=['sigkill_op'],
                observed_sources=['sigkill_op'],
                artifacts=[actions_path, index_path],
                trace_index=index_path,
            )
            self.assertEqual(manifest['completeness'], 'interrupted')
            self.assertEqual(manifest['actions']['interrupted'], 1)
            self.assertEqual(manifest['actions']['unclosed_inflight'], 0)
            self.assertEqual(manifest['actions']['interrupt_reasons'], {'sigkill': 1})
            self.assertIn('interrupted_actions:1', manifest['incomplete_reasons'])

    def test_sigkill_truncated_jsonl_tail_recovers_valid_records_and_preserves_corrupt_journal(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            actions_path = tmp_path / 'actions.jsonl'
            journal_path = inflight_journal_path(actions_path)

            actions_path.write_text(
                json.dumps({'action_id': 'a-done', 'action_name': 'op', 'status': 'succeeded', 'trace_id': 'Y-done'})
                + '\n{"action_id":"a-half-written'
            )
            journal_path.write_text(
                json.dumps(
                    {
                        'schema_version': '1',
                        'event': 'action_started',
                        'action_id': 'a-good',
                        'action_name': 'op',
                        'status': 'running',
                        'started_at': '2026-11-28T00:00:00+00:00',
                        'started_monotonic_ns': 10,
                        'trace_id': 'Y-good',
                    }
                )
                + '\n{"event":"action_started","action_id":"a-trunc'
            )

            recovered = reconcile_inflight_actions(actions_path, reason='sigkill')
            self.assertEqual(len(recovered), 2)
            self.assertEqual(recovered[0]['action_id'], 'a-good')
            self.assertEqual(recovered[0]['trace_id'], 'Y-good')
            self.assertEqual(recovered[0]['status'], 'interrupted')
            self.assertEqual(recovered[1]['action_name'], 'corrupt_inflight')
            self.assertEqual(recovered[1]['status'], 'interrupted')
            self.assertEqual(recovered[1]['metadata']['corrupt_line'], 2)
            self.assertTrue(journal_path.exists())
            self.assertEqual(reconcile_inflight_actions(actions_path, reason='sigkill'), [])

            summary = inspect_action_artifacts([actions_path])
            self.assertEqual(summary['interrupted'], 2)
            self.assertEqual(summary['corrupt_lines'], 2)
            self.assertIn('actions.jsonl:2', summary['corrupt_locations'])
            self.assertIn('actions.inflight.jsonl:2', summary['corrupt_locations'])

            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-corrupt',
                expected_sources=[],
                artifacts=[actions_path],
            )
            self.assertEqual(manifest['completeness'], 'interrupted')
            self.assertEqual(manifest['actions']['corrupt_lines'], 2)
            self.assertIn('corrupt_action_lines:2', manifest['incomplete_reasons'])

    def test_sole_truncated_inflight_line_without_reconcile_marks_manifest_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            actions_path = tmp_path / 'actions.jsonl'
            journal_path = inflight_journal_path(actions_path)
            journal_path.write_text('{"event":"action_started","action_id":"a-cut')

            direct_summary = inspect_action_artifacts([journal_path])
            self.assertEqual(direct_summary['total'], 0)
            self.assertEqual(direct_summary['corrupt_lines'], 1)

            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-sole-corrupt',
                expected_sources=[],
                artifacts=[actions_path],
            )
            self.assertEqual(manifest['completeness'], 'interrupted')
            self.assertEqual(manifest['actions']['corrupt_lines'], 1)

    def test_action_writer_context_cancellation_and_timeout_emit_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            for label, exc, expected_reason in (
                ('keyboard', KeyboardInterrupt('stop now'), 'cancelled'),
                ('cancelled', asyncio.CancelledError(), 'cancelled'),
                ('timeout', TimeoutError('budget exceeded'), 'timeout'),
            ):
                actions_path = tmp_path / f'{label}-actions.jsonl'
                try:
                    with ActionWriter(actions_path) as writer:
                        writer.begin(f'op_{label}', trace_id=f'Y-{label}')
                        raise exc
                except BaseException as raised:
                    self.assertIs(raised, exc)
                else:
                    self.fail(f'expected {label} exception to propagate')

                self.assertFalse(inflight_journal_path(actions_path).exists())
                records = [json.loads(line) for line in actions_path.read_text().splitlines()]
                self.assertEqual(len(records), 1)
                self.assertEqual(records[0]['status'], 'interrupted')
                self.assertEqual(records[0]['metadata']['interrupt_reason'], expected_reason)

                manifest = write_manifest(
                    tmp_path / f'{label}-manifest.json',
                    run_id=f'run-{label}',
                    expected_sources=[f'op_{label}'],
                    observed_sources=[f'op_{label}'],
                    artifacts=[actions_path],
                )
                self.assertEqual(manifest['completeness'], 'interrupted')
                self.assertEqual(manifest['actions']['interrupted'], 1)
                self.assertEqual(manifest['actions']['interrupt_reasons'], {expected_reason: 1})

    def test_open_loop_drain_timeout_marks_stuck_action_interrupted(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            release = threading.Event()
            started_worker = threading.Event()
            actions_path = tmp_path / 'actions.jsonl'
            writer = ActionWriter(actions_path)
            settled = []

            def stuck_execute(_item):
                started_worker.set()
                release.wait(timeout=5)
                return {'status': 'ok'}

            try:
                summary = run_open_loop(
                    started=time.monotonic(),
                    duration=0.02,
                    rps=50,
                    workers=1,
                    queue_capacity=None,
                    execute=stuck_execute,
                    key_for=lambda _index: None,
                    blocked=lambda _key: False,
                    settle=lambda item, outcome, _row: settled.append((item['arrival_id'], outcome)),
                    stop=threading.Event(),
                    drain_all=True,
                    drain_timeout=0.08,
                    action_writer=writer,
                    action_name='stuck_arrival',
                )
                writer.close()
            finally:
                release.set()

            self.assertTrue(started_worker.is_set())
            self.assertEqual(summary['interrupted'], 1)
            self.assertTrue(summary['conserved'])
            self.assertTrue(any(outcome == 'interrupted' for _, outcome in settled))
            records = [json.loads(line) for line in actions_path.read_text().splitlines()]
            interrupted = [record for record in records if record['status'] == 'interrupted']
            self.assertEqual(len(interrupted), 1)
            self.assertEqual(interrupted[0]['metadata']['interrupt_reason'], 'timeout')
            self.assertFalse(inflight_journal_path(actions_path).exists())

            manifest = write_manifest(
                tmp_path / 'run-manifest.json',
                run_id='run-drain-timeout',
                expected_sources=['stuck_arrival'],
                observed_sources=writer.sources,
                artifacts=[actions_path],
            )
            self.assertEqual(manifest['completeness'], 'interrupted')
            self.assertEqual(manifest['actions']['interrupt_reasons'], {'timeout': 1})

    def test_regression_traffic_sigterm_cancels_inflight_action_and_preserves_signal_exit(self):
        with tempfile.TemporaryDirectory() as folder:
            tmp_path = Path(folder)
            ready_path = tmp_path / 'cli-started.txt'
            cli = tmp_path / 'lbctl-slow'
            cli.write_text(
                f'#!{sys.executable}\n'
                'import time; from pathlib import Path; '
                f'Path({str(ready_path)!r}).write_text("started"); '
                'time.sleep(30)\n'
            )
            cli.chmod(0o700)
            cases = tmp_path / 'cases.json'
            cases.write_text(
                json.dumps([{'name': 'chat', 'args': ['pipeline', 'run', 'demo', '--message', 'hi'], 'expect': 'OK'}])
            )
            output = tmp_path / 'traffic'
            proc = subprocess.Popen(
                [
                    sys.executable,
                    '-m',
                    'tools.entrypoints.regression_traffic',
                    '--lbctl',
                    str(cli),
                    '--config',
                    'unused',
                    '--cases',
                    str(cases),
                    '--output',
                    str(output),
                    '--duration',
                    '5',
                    '--rps',
                    '1',
                    '--workers',
                    '1',
                    '--cooldown',
                    '0',
                    '--arrival-mode',
                    'open-loop',
                ],
                cwd=Path.cwd(),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                start_new_session=True,
            )
            try:
                deadline = time.monotonic() + 5
                while not ready_path.exists() and time.monotonic() < deadline:
                    time.sleep(0.02)
                self.assertTrue(ready_path.exists(), 'fake CLI never started')
                proc.send_signal(signal.SIGTERM)
                proc.wait(timeout=5)
            finally:
                if proc.poll() is None:
                    proc.kill()
                    proc.wait(timeout=5)
                try:
                    os.killpg(proc.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                if proc.stdout:
                    proc.stdout.close()
                if proc.stderr:
                    proc.stderr.close()

            self.assertEqual(proc.returncode, -signal.SIGTERM)
            records = [json.loads(line) for line in (output / 'actions.jsonl').read_text().splitlines()]
            interrupted = [record for record in records if record['status'] == 'interrupted']
            self.assertGreaterEqual(len(interrupted), 1)
            self.assertEqual(interrupted[0]['metadata']['interrupt_reason'], 'cancelled')
            manifest = json.loads((output / 'run-manifest.json').read_text())
            self.assertEqual(manifest['completeness'], 'interrupted')
            self.assertEqual(manifest['interrupted_reason'], 'cancelled')
            self.assertGreaterEqual(manifest['actions']['interrupted'], 1)


if __name__ == '__main__':
    unittest.main()
