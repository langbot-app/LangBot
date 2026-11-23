"""Check opt-in mixload accepts only independently corroborated selected scenarios."""

from contextlib import closing
import copy
import json
from pathlib import Path
import sqlite3
import tempfile
import unittest

from tools.regression.profiled_mixload import verify_profiled_run
from tools.regression.regression_mixed import RECOVERY_QUEUES


class ProfiledEvidenceTests(unittest.TestCase):
    def setUp(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        self.root = Path(directory.name)
        self.phase = self.root / 'one-path'
        self.phase.mkdir()
        self.db = self.root / 'ledger.db'
        self.paths = {name: self.root / f'{name}-requests.jsonl' for name in ('chat', 'box', 'rag_chat')}
        self.wire = {name: [] for name in self.paths}
        self.paths['box'].touch()
        self.paths['rag_chat'].touch()
        (self.root / 'warmup.json').write_text('[]')
        self.profile = {
            'cases': [{'name': 'chat', 'expect': 'LANGBOT_CHAT_OK'}],
            'phases': [
                {
                    'name': self.phase.name,
                    'groups': 2,
                    'members_per_group': 2,
                    'min_delivery_ratio': 1,
                    'duration_seconds': 2,
                    'rps': 2,
                    'scenario_weights': [['chat', 1]],
                }
            ],
        }
        sessions = {}
        self.rows = []
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute(
                'CREATE TABLE agent_run (run_id TEXT, status TEXT, conversation_id TEXT, bot_id TEXT, workspace_id TEXT)'
            )
            for group_index, group in enumerate(('test-a', 'test-b')):
                history, previous = [], 'none'
                for turn in (1, 2):
                    token = f'{len(self.rows) + 1:032x}'
                    run_id = f'{group}-{turn}'
                    slot = group_index + 2 * (turn - 1)
                    self.rows.append(
                        {
                            'case': 'chat',
                            'group_id': group,
                            'token': token,
                            'turn': turn,
                            'offered_slot': slot,
                            'planned_elapsed_seconds': slot / 2,
                            'elapsed': slot / 2,
                            'member_id': f'qa-member-{turn - 1:03d}',
                            'status': 'ok',
                            'run': {'run_id': run_id},
                        }
                    )
                    db.execute(
                        'INSERT INTO agent_run VALUES (?,?,?,?,?)',
                        (run_id, 'completed', 'group_' + group, 'bot-chat', 'owned-workspace'),
                    )
                    history.append(
                        {
                            'role': 'user',
                            'content': f'LB_GROUP={group} LB_TURN={turn} LB_TOKEN={token} LB_PREVIOUS={previous}',
                        }
                    )
                    reply = 'LANGBOT_CHAT_OK GROUP_ACK=' + token
                    self.wire['chat'].append(
                        {
                            'path': '/v1/chat/completions',
                            'status': 200,
                            'response_complete': True,
                            'request': {'model': 'mock-chat', 'messages': copy.deepcopy(history)},
                            'response': {'content': reply},
                        }
                    )
                    history.append({'role': 'assistant', 'content': reply})
                    previous = token
                sessions[group] = {
                    'group_index': group_index,
                    'case': 'chat',
                    'failed': False,
                    'successful_turns_total': 2,
                    'requests_this_phase': 2,
                    'members_this_phase': ['qa-member-000', 'qa-member-001'],
                }
        self.summary = {
            'requests': 4,
            'successful_requests': 4,
            'verified_runs': 4,
            'verification_enabled': True,
            'ledger_closeout': {'matched': True},
            'groups': {'configured': 2, 'members_per_group': 2, 'sessions': sessions},
            'group_failures': [],
            'slot_accounting': {'chat': {'offered': 4, 'admitted': 4, 'not_admitted': 0}},
            'health_samples': 2,
            'health_failures': 0,
            'resource_observations': {
                'queues': {name: {'status': 'observed', 'cooldown_tail_max': 0} for name in RECOVERY_QUEUES},
            },
        }
        self.write()

    def write(self):
        (self.phase / 'summary.json').write_text(json.dumps(self.summary))
        (self.phase / 'requests.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in self.rows))
        for case, path in self.paths.items():
            path.write_text(''.join(json.dumps(row) + '\n' for row in self.wire[case]))

    def verify(self):
        return verify_profiled_run(self.root, self.db, self.paths, self.profile)

    def test_one_selected_case_passes_without_claiming_unselected_box_or_rag(self):
        result = self.verify()
        self.assertTrue(result['passed'], result)
        self.assertEqual(result['wire_stages'], {'chat': 4})
        self.assertEqual(result['box_groups_verified'], 0)
        self.assertEqual(result['phases'][self.phase.name]['cases'], {'chat': 4})

    def test_missing_selected_phase_is_incomplete_not_pass(self):
        (self.phase / 'requests.jsonl').unlink()
        status = self.verify()
        self.assertEqual(status['outcome'], 'INCOMPLETE', status)
        self.assertIn('Missing measured phases', status['errors'][0])

    def test_configured_case_with_no_evidence_cannot_pass_on_other_traffic(self):
        self.profile['phases'][0]['scenario_weights'].append(['box', 1])
        status = self.verify()
        self.assertFalse(status['passed'])
        self.assertIn('selected scenario never ran', status['errors'][0])

    def test_reported_admissions_cannot_exceed_offered_slots_or_actual_rows(self):
        self.summary['slot_accounting']['chat']['offered'] = 5
        self.summary['slot_accounting']['chat']['not_admitted'] = 1
        self.write()
        status = self.verify()
        self.assertFalse(status['passed'])
        self.assertIn('offered != admitted', status['errors'][0])

    def test_missing_generation_receipt_is_incomplete(self):
        self.wire['chat'].pop()
        self.write()
        status = self.verify()
        self.assertEqual(status['outcome'], 'INCOMPLETE', status)
        self.assertIn('stage receipts', status['errors'][0])

    def test_misrouted_generation_does_not_pass(self):
        self.wire['rag_chat'].append(self.wire['chat'].pop())
        self.write()
        status = self.verify()
        self.assertFalse(status['passed'])
        self.assertIn('wrong Provider/model', status['errors'][0])

    def test_independent_db_read_rejects_wrong_run_state_despite_green_summary(self):
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('UPDATE agent_run SET status=? WHERE run_id=?', ('failed', self.rows[0]['run']['run_id']))
        status = self.verify()
        self.assertFalse(status['passed'])
        self.assertIn('Incorrect persisted run identity', status['errors'][0])

    def test_stale_green_group_summary_cannot_hide_a_one_turn_group(self):
        lost = self.rows.pop()
        self.wire['chat'].pop()
        with closing(sqlite3.connect(self.db)) as db, db:
            db.execute('DELETE FROM agent_run WHERE run_id=?', (lost['run']['run_id'],))
        # All ledger/wire records for the remaining requests agree and overall
        # delivery is allowed below 100%; only the claimed group history is false.
        self.profile['phases'][0]['min_delivery_ratio'] = 0.5
        self.summary.update(requests=3, successful_requests=3, verified_runs=3)
        self.summary['slot_accounting']['chat'].update(admitted=3, not_admitted=1)
        self.write()

        status = self.verify()
        self.assertFalse(status['passed'], status)
        self.assertIn('fewer than two raw turns', status['errors'][0])

    def test_requests_cannot_be_attributed_to_another_groups_slot(self):
        first_a, first_b = self.rows[0], self.rows[2]
        # Keep all slots unique and the stated due time correct. The sole
        # inconsistency is assigning each first request to the other group.
        for row, slot in ((first_a, 1), (first_b, 0)):
            row.update(offered_slot=slot, planned_elapsed_seconds=slot / 2, elapsed=slot / 2)
        self.write()

        status = self.verify()
        self.assertFalse(status['passed'], status)
        self.assertIn('slot', status['errors'][0].lower())

    def test_delivery_floor_failure_preserves_business_wire_verdict(self):
        self.profile['phases'][0]['duration_seconds'] = 3
        self.summary['slot_accounting']['chat'].update(offered=6, admitted=4, not_admitted=2)
        self.write()

        status = self.verify()
        self.assertFalse(status['passed'], status)
        self.assertTrue(status['business_evidence_passed'], status)
        self.assertFalse(status['delivery_floor_passed'], status)
        self.assertEqual(status['wire_stages'], {'chat': 4})
        self.assertIn('below declared floor', status['errors'][0])
