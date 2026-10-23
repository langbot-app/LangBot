"""Challenge the smoke verdict independently of a successful model reply."""

import base64
import copy
import json
from pathlib import Path
import sqlite3
import unittest

from regression_smoke import UnresolvedRun, check_attachment, check_run, completed_run
from regression_suite import validate


class SmokeOracleTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(':memory:')
        self.db.row_factory = sqlite3.Row
        self.addCleanup(self.db.close)
        self.db.executescript("""
            CREATE TABLE agent_run (id INTEGER, run_id TEXT, workspace_id TEXT,
                conversation_id TEXT, status TEXT, status_reason TEXT, finished_at TEXT);
            CREATE TABLE agent_run_event (run_id TEXT, sequence INTEGER, type TEXT, data_json TEXT);
            INSERT INTO agent_run VALUES (1, 'run', 'workspace', 'conversation', 'completed', '', 'now');
            INSERT INTO agent_run_event VALUES ('run', 1, 'run.completed', '{}');
        """)

    def run_row(self, workspace='workspace', after=0):
        return completed_run(self.db, workspace, 'conversation', after, 0)

    def test_terminal_status_and_event_are_both_required(self):
        self.assertTrue(check_run(self.db, self.run_row(), {})['terminal_event'])
        self.db.execute("UPDATE agent_run SET status='failed'")
        with self.assertRaises(ValueError):
            check_run(self.db, self.run_row(), {})
        self.db.execute("UPDATE agent_run SET status='completed'")
        self.db.execute('DELETE FROM agent_run_event')
        with self.assertRaises(ValueError):
            check_run(self.db, self.run_row(), {})

    def test_missing_stale_wrong_workspace_and_ambiguous_runs_are_unknown(self):
        for workspace, after in [('other', 0), ('workspace', 1)]:
            with self.subTest(workspace=workspace, after=after), self.assertRaises(UnresolvedRun):
                self.run_row(workspace, after)
        self.db.execute("UPDATE agent_run SET status='running', finished_at=NULL")
        with self.assertRaises(UnresolvedRun):
            self.run_row()
        self.db.execute('INSERT INTO agent_run SELECT * FROM agent_run')
        with self.assertRaises(UnresolvedRun):
            self.run_row()

    def test_box_requires_actual_backend_success_and_output(self):
        case = {'box_exec': {'count': 1, 'backend': 'docker', 'stdout': 'sentinel'}}
        good = {'backend': 'docker', 'exit_code': 0, 'stdout': 'sentinel'}
        for result, passes in [
            (good, True),
            ({**good, 'backend': 'host'}, False),
            ({**good, 'exit_code': 1}, False),
            ({**good, 'stdout': ''}, False),
            (None, False),
        ]:
            self.db.execute('DELETE FROM agent_run_event WHERE sequence=2')
            self.db.execute(
                'INSERT INTO agent_run_event VALUES (?, ?, ?, ?)',
                ('run', 2, 'tool.call.completed', json.dumps({'tool_name': 'exec', 'result': result})),
            )
            with self.subTest(result=result):
                if passes:
                    check_run(self.db, self.run_row(), case)
                else:
                    with self.assertRaises(ValueError):
                        check_run(self.db, self.run_row(), case)
        with self.assertRaises(ValueError):
            check_run(self.db, self.run_row(), {'box_exec': {**case['box_exec'], 'count': 2}})

    def test_attachment_requires_exact_bytes_and_single_file(self):
        expected = {'name': 'out.txt', 'text': 'sentinel'}
        part = {'type': 'File', 'name': 'out.txt', 'base64': base64.b64encode(b'sentinel').decode()}
        data = {'replies': [{'message_chain': [part]}]}
        self.assertTrue(check_attachment(data, expected)['content_matched'])
        for parts in [
            [],
            [part, part],
            [{**part, 'base64': '!!!'}],
            [{**part, 'base64': 'd3Jvbmc='}],
            [{**part, 'name': 'other'}],
            [None],
        ]:
            with self.subTest(parts=parts), self.assertRaises(ValueError):
                check_attachment({'replies': [{'message_chain': parts}]}, expected)

    def test_profile_supports_mixed_cases_and_rejects_ignored_oracles(self):
        profile = json.loads(Path(__file__).with_name('regression_profiles').joinpath('smoke.json').read_text())
        validate(profile)
        for changes in [{'thresholds': {'min_rps_ratio': 1}}, {'smoke': {'ledger_db': ''}}, {'phases': None}]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                validate({**profile, **changes})
        wrong = copy.deepcopy(profile)
        wrong['cases'][4]['box_exec'] = {'count': 1, 'backend': 'docker', 'stdout': 'x'}
        with self.assertRaises(ValueError):
            validate(wrong)


if __name__ == '__main__':
    unittest.main()
