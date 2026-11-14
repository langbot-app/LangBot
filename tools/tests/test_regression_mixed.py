"""Independent persisted events and wire receipts for the mixed workload oracle."""

import copy
from datetime import datetime, timedelta
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tools.regression.regression_mixed import verify_mixed


class MixedEvidenceTest(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.suite = self.root / 'suite'
        self.phase = self.suite / 'load'
        self.phase.mkdir(parents=True)
        self.db = self.root / 'ledger.db'
        self.paths = {case: self.root / (case + '.jsonl') for case in ('chat', 'box', 'rag_chat')}
        self.rows = []
        self.wire = {case: [] for case in self.paths}
        self.phase_summary = {
            'resource_observations': {
                'queues': {
                    metric: {'status': 'observed', 'load_peak': 3, 'cooldown_tail_max': 0}
                    for metric in (
                        'core.body.resources.query_pool.queued',
                        'box.body.resources.blocking_executor.pending',
                        'box.body.resources.creating_session_tasks',
                        'box.body.resources.closing_session_tasks',
                    )
                }
            }
        }
        with sqlite3.connect(self.db) as db:
            db.executescript("""
                CREATE TABLE agent_run (run_id TEXT, status TEXT, conversation_id TEXT,
                    bot_id TEXT, started_at TEXT, finished_at TEXT);
                CREATE TABLE agent_run_event (run_id TEXT, sequence INTEGER,
                    type TEXT, data_json TEXT, created_at TEXT);
            """)
            # Box a/b tool windows overlap; the next turn starts after both finish.
            for case, group, offset in (('chat', 'c', 0), ('box', 'a', 0), ('box', 'b', 1), ('rag_chat', 'r', 0)):
                previous = 'none'
                prior_messages = []
                for turn in (1, 2):
                    token = f'{len(self.rows) + 1:032x}'
                    run = f'{group}-{turn}'
                    begin = offset + (turn - 1) * 10
                    self.rows.append(
                        {
                            'case': case,
                            'group_id': group,
                            'token': token,
                            'turn': turn,
                            'status': 'ok',
                            'run': {'run_id': run},
                            'elapsed': begin,
                            'seconds': 5,
                        }
                    )
                    db.execute(
                        'INSERT INTO agent_run VALUES (?,?,?,?,?,?)',
                        (
                            run,
                            'completed',
                            'group_' + group,
                            'bot-' + case,
                            self.stamp(begin),
                            self.stamp(begin + 5),
                        ),
                    )
                    messages = prior_messages + [
                        {
                            'role': 'user',
                            'content': f'LB_GROUP={group} LB_TURN={turn} LB_TOKEN={token} LB_PREVIOUS={previous}',
                        }
                    ]
                    model = {'chat': 'mock-chat', 'box': 'mock-smoke-box', 'rag_chat': 'mock-rag'}[case]
                    reply = {'chat': 'LANGBOT_CHAT_OK', 'box': 'LANGBOT_BOX_OK', 'rag_chat': 'LANGBOT_RAG_OK'}[case]
                    for stage in range(3 if case == 'box' else 1):
                        final = stage == (2 if case == 'box' else 0)
                        self.wire[case].append(
                            {
                                'time': begin + 2 * stage,
                                'duration_seconds': 1.5,
                                'path': '/v1/chat/completions',
                                'status': 200,
                                'response_complete': True,
                                'request': {'model': model, 'messages': copy.deepcopy(messages)},
                                'response': {'content': reply + ' GROUP_ACK=' + token if final else None},
                            }
                        )
                        if case == 'box' and not final:
                            call = f'exec-{stage}'
                            messages.extend(
                                [
                                    {'role': 'assistant', 'tool_calls': [{'id': call}]},
                                    {'role': 'tool', 'tool_call_id': call, 'content': 'LANGBOT_BOX_SENTINEL'},
                                ]
                            )
                            for sequence, kind, when, result in (
                                (2 * stage, 'tool.call.started', begin + 2 * stage, {}),
                                (
                                    2 * stage + 1,
                                    'tool.call.completed',
                                    begin + 2 * stage + 2,
                                    {
                                        'backend': 'docker',
                                        'exit_code': 0,
                                        'stdout': f'LB_BOX_HOST=host-{group}\nLANGBOT_BOX_SENTINEL',
                                    },
                                ),
                            ):
                                db.execute(
                                    'INSERT INTO agent_run_event VALUES (?,?,?,?,?)',
                                    (
                                        run,
                                        sequence,
                                        kind,
                                        json.dumps({'tool_name': 'exec', 'tool_call_id': call, 'result': result}),
                                        self.stamp(when),
                                    ),
                                )
                    prior_messages = messages + [{'role': 'assistant', 'content': reply + ' GROUP_ACK=' + token}]
                    previous = token
        self.write()

    @staticmethod
    def stamp(seconds):
        return (datetime(2026, 1, 1) + timedelta(seconds=seconds)).isoformat()

    def write(self):
        (self.phase / 'summary.json').write_text(json.dumps(self.phase_summary))
        (self.phase / 'requests.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in self.rows))
        for case, path in self.paths.items():
            path.write_text(''.join(json.dumps(row) + '\n' for row in self.wire[case]))

    def verdict(self):
        return verify_mixed(self.suite, self.db, self.paths)

    def test_real_receipts_identify_three_routes_and_overlapping_distinct_boxes(self):
        result = self.verdict()
        self.assertTrue(result['passed'], result)
        self.assertTrue(result['box_tool_event_overlap'])
        self.assertEqual(set(result['provider_service_overlap']), set(self.paths))
        self.assertTrue(all(item['overlap_seconds'] > 0 for item in result['provider_service_overlap'].values()))
        self.assertTrue(all(value == 0 for value in result['cooldown_recovery']['load'].values()))
        self.assertEqual(result['counts'], {'requests': 8, 'groups': 4, 'bots': 3, 'box_groups': 2})
        self.assertEqual(result['provider_requests'], {'chat': 2, 'box': 12, 'rag_chat': 2})

    def test_serial_provider_service_fails_despite_concurrent_http_and_box_runs(self):
        for index, rows in enumerate(self.wire.values()):
            for record in rows:
                record['time'] += 1000 * index
        self.write()
        result = self.verdict()
        self.assertFalse(result['passed'])
        self.assertEqual(result['outcome'], 'FAIL')
        self.assertIn('never served generation concurrently', result['errors'][0])

    def test_provider_overlap_requires_real_finite_service_timing(self):
        original = copy.deepcopy(self.wire)
        for value in (None, 0, float('nan'), False):
            with self.subTest(value=value):
                self.wire = copy.deepcopy(original)
                self.wire['chat'][0]['duration_seconds'] = value
                self.write()
                result = self.verdict()
                self.assertFalse(result['passed'])
                self.assertEqual(result['outcome'], 'INCOMPLETE')

    def test_cooldown_residual_and_missing_queue_evidence_cannot_pass(self):
        original = copy.deepcopy(self.phase_summary)
        for metric in original['resource_observations']['queues']:
            for mutation, expected in (('residual', 'FAIL'), ('unknown', 'INCOMPLETE'), ('missing', 'INCOMPLETE')):
                with self.subTest(metric=metric, mutation=mutation):
                    self.phase_summary = copy.deepcopy(original)
                    queues = self.phase_summary['resource_observations']['queues']
                    if mutation == 'residual':
                        queues[metric]['cooldown_tail_max'] = 1
                    elif mutation == 'unknown':
                        queues[metric]['status'] = 'unknown'
                    else:
                        del queues[metric]
                    self.write()
                    result = self.verdict()
                    self.assertFalse(result['passed'])
                    self.assertEqual(result['outcome'], expected)
        self.phase_summary = original
        self.write()
        (self.phase / 'summary.json').unlink()
        self.assertEqual(self.verdict()['outcome'], 'INCOMPLETE')

    def test_missing_paired_tool_timestamps_is_incomplete(self):
        original = self.db.read_bytes()
        for mutation in (
            "DELETE FROM agent_run_event WHERE run_id='a-1' AND type='tool.call.started'",
            "UPDATE agent_run_event SET created_at=NULL WHERE run_id='a-1'",
        ):
            with self.subTest(mutation=mutation):
                with sqlite3.connect(self.db) as db:
                    db.execute(mutation)
                result = self.verdict()
                self.assertFalse(result['passed'])
                self.assertEqual(result['outcome'], 'INCOMPLETE')
                self.db.write_bytes(original)

    def test_wrong_provider_duplicate_or_missing_model_stage_cannot_pass(self):
        original = copy.deepcopy(self.wire)
        for mutation in ('wrong-provider', 'duplicate', 'missing', 'unowned'):
            with self.subTest(mutation=mutation):
                self.wire = copy.deepcopy(original)
                if mutation == 'wrong-provider':
                    self.wire['rag_chat'].append(self.wire['chat'].pop())
                elif mutation == 'duplicate':
                    self.wire['box'].append(self.wire['box'][0])
                elif mutation == 'missing':
                    self.wire['box'].pop()
                else:
                    foreign = copy.deepcopy(self.wire['chat'][0])
                    foreign['request']['messages'][0]['content'] = (
                        'LB_GROUP=foreign LB_TURN=1 LB_TOKEN=ffffffff LB_PREVIOUS=none'
                    )
                    self.wire['chat'].append(foreign)
                self.write()
                self.assertFalse(self.verdict()['passed'])

    def test_serial_tool_execution_fails_even_when_http_and_agent_runs_overlap(self):
        with sqlite3.connect(self.db) as db:
            for run in ('b-1', 'b-2'):
                db.execute(
                    "UPDATE agent_run_event SET created_at=datetime(created_at,'+5 seconds') WHERE run_id=?",
                    (run,),
                )
        result = self.verdict()
        self.assertFalse(result['passed'])
        self.assertEqual(result['outcome'], 'FAIL')
        self.assertFalse(result['box_tool_event_overlap'])

    def test_only_recorded_warmup_groups_are_excluded_from_measured_tokens(self):
        warmup = copy.deepcopy(self.wire['chat'][0])
        warmup['request']['messages'][0]['content'] = (
            'LB_GROUP=qa-warmup-own LB_TURN=1 LB_TOKEN=ffffffff LB_PREVIOUS=none'
        )
        self.wire['chat'].append(warmup)
        self.write()
        self.assertFalse(self.verdict()['passed'])
        (self.suite / 'warmup.json').write_text(
            json.dumps(
                [
                    {'case': 'chat', 'output': {'data': {'session_id': 'qa-warmup-own'}}},
                ]
            )
        )
        self.assertTrue(self.verdict()['passed'])


if __name__ == '__main__':
    unittest.main()
