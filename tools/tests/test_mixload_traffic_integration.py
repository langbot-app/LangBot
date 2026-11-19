"""Exercise opt-in slot accounting with a deliberately slow case and real workers."""

from contextlib import redirect_stdout
import io
import json
import os
from pathlib import Path
import sys
import tempfile
import time
import unittest
from unittest.mock import patch

from tools.entrypoints.regression_traffic import main


class MixloadTrafficIntegrationTest(unittest.TestCase):
    def test_slow_group_sheds_its_slot_without_slowing_or_reassigning_fast_group(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            cases, output = root / 'cases.json', root / 'run'
            fixture = {'url': 'http://127.0.0.1:1', 'secret_env': 'TEST_MIXLOAD_SECRET', 'message': 'fixture'}
            cases.write_text(
                json.dumps([{'name': name, 'expect': 'OK', 'http_group': fixture} for name in ('slow', 'fast')])
            )
            argv = [
                'traffic',
                '--lbctl',
                'unused',
                '--config',
                'unused',
                '--cases',
                str(cases),
                '--output',
                str(output),
                '--duration',
                '2.2',
                '--rps',
                '4',
                '--workers',
                '2',
                '--groups',
                '2',
                '--cooldown',
                '0',
                '--max-requests',
                '8',
                '--open-loop-groups',
            ]

            def respond(case, group, _member, turn, _token, _previous):
                # The slow group is offered every 0.5s. Hold its first
                # request across the next nominal slot while fast stays free.
                if case['name'] == 'slow' and turn == 1:
                    time.sleep(0.7)
                return {'data': {'session_id': group}}

            with (
                patch.object(sys, 'argv', argv),
                patch.dict(os.environ, {'TEST_MIXLOAD_SECRET': 'test-only-fake'}),
                patch('tools.entrypoints.regression_traffic.group_request', side_effect=respond),
                redirect_stdout(io.StringIO()),
            ):
                main()

            summary = json.loads((output / 'summary.json').read_text())
            rows = [json.loads(line) for line in (output / 'requests.jsonl').read_text().splitlines()]
            accounting = summary['slot_accounting']
            self.assertEqual(summary['planned_requests'], 8)
            self.assertEqual(summary['requests'], len(rows))
            self.assertEqual(summary['status'], {'ok': len(rows)})
            self.assertEqual(set(accounting), {'slow', 'fast'})
            group_indices = {
                group_id: session['group_index'] for group_id, session in summary['groups']['sessions'].items()
            }
            self.assertEqual(set(group_indices.values()), {0, 1})
            slots = {row['offered_slot'] for row in rows}
            self.assertEqual(len(slots), len(rows))
            for row in rows:
                slot = row['offered_slot']
                self.assertIs(type(slot), int)
                self.assertTrue(0 <= slot < 8)
                self.assertEqual(row['planned_elapsed_seconds'], slot / 4)
                self.assertEqual(slot % 2, group_indices[row['group_id']])
            self.assertGreaterEqual(accounting['slow']['not_admitted'], 1)
            self.assertGreaterEqual(accounting['fast']['admitted'], 2)
            for case, counter in accounting.items():
                selected = [row for row in rows if row['case'] == case]
                self.assertEqual(counter['offered'], 4)
                self.assertEqual(counter['not_admitted'] + counter['admitted'], 4)
                self.assertEqual(counter['admitted'], len(selected))
                self.assertEqual(sorted(row['turn'] for row in selected), list(range(1, len(selected) + 1)))
                self.assertEqual(len({row['token'] for row in selected}), len(selected))
