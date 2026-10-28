"""Coverage must measure evaluated obligations, not green request counters."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from regression_coverage import checked, collect, http_observations, load_catalog, report, route_inventory, write_report


def catalog():
    return {
        'version': 1,
        'scope': 'Test scope',
        'contracts': [
            {
                'id': 'reply',
                'area': 'conversation',
                'kind': 'blackbox',
                'priority': 'P0',
                'description': 'Reply and payload agree',
                'bindings': [{'profile': 'smoke', 'case': 'chat', 'checks': ['response', 'fields']}],
            },
            {
                'id': 'terminal',
                'area': 'execution',
                'kind': 'graybox',
                'priority': 'P0',
                'description': 'Persisted terminal state',
                'bindings': [{'profile': 'smoke', 'case': 'chat', 'checks': ['ledger']}],
            },
            {
                'id': 'recovery',
                'area': 'execution',
                'kind': 'blackbox',
                'priority': 'P0',
                'description': 'Restart recovery',
                'bindings': [],
            },
        ],
    }


def row(**overrides):
    return {'profile': 'smoke', 'case': 'chat', 'status': 'passed', **overrides}


class CoverageTest(unittest.TestCase):
    def test_old_green_rows_and_transport_failures_are_not_coverage(self):
        for r in [row(), row(status='unknown'), row(assertions={'response': 'passed'})]:
            data = report(catalog(), [r])
            self.assertEqual(data['kinds']['blackbox']['decided'], 0)
            self.assertEqual(data['contracts'][0]['status'], 'incomplete')
        r = {}
        with self.assertRaises(TimeoutError):
            checked(r, 'response', lambda: (_ for _ in ()).throw(TimeoutError('transport')))
        self.assertNotIn('response', r['assertions'])

    def test_a_failed_assertion_is_covered_but_not_passed(self):
        r = row()
        with self.assertRaises(ValueError):
            checked(r, 'response', lambda: (_ for _ in ()).throw(ValueError('wrong reply')))
        data = report(catalog(), [r])
        self.assertEqual(data['kinds']['blackbox']['coverage_percent'], 50)
        self.assertEqual(data['kinds']['blackbox']['pass_percent'], 0)
        self.assertEqual(data['contracts'][0]['status'], 'failed')

    def test_graybox_failure_does_not_erase_external_assertions(self):
        data = report(
            catalog(),
            [
                row(
                    status='failed',
                    assertions={
                        'response': 'passed',
                        'fields': 'passed',
                        'ledger': 'failed',
                    },
                )
            ],
        )
        self.assertEqual(data['contracts'][0]['status'], 'passed')
        self.assertEqual(data['contracts'][1]['status'], 'failed')
        self.assertEqual(data['contracts'][2]['status'], 'missing_test')

    def test_repetition_does_not_inflate_coverage_or_hide_incomplete_turns(self):
        good = row(assertions={'response': 'passed', 'fields': 'passed'})
        self.assertEqual(report(catalog(), [good])['kinds'], report(catalog(), [good] * 100)['kinds'])
        mixed = report(catalog(), [good, row(status='unknown')])
        self.assertEqual(mixed['contracts'][0]['status'], 'incomplete')
        self.assertEqual(report(catalog(), [row(status='skipped')])['contracts'][0]['status'], 'skipped')
        self.assertEqual(report(catalog(), [])['contracts'][0]['status'], 'not_run')

    def test_first_turn_does_not_prove_history_and_unclassified_cases_are_visible(self):
        c = catalog()
        c['contracts'][0]['bindings'][0]['min_turn'] = 2
        r = row(turn=1, assertions={'response': 'passed', 'fields': 'passed'})
        data = report(c, [r, row(case='new_case')])
        self.assertEqual(data['contracts'][0]['status'], 'not_run')
        self.assertEqual(data['unclassified_cases'], [{'profile': 'smoke', 'case': 'new_case'}])

    def test_reset_failure_and_peer_skip_cannot_be_hidden_by_first_turns(self):
        c = load_catalog()
        rows = [
            {
                'profile': 'scenarios',
                'case': 'group_reset_isolation',
                'status': 'passed',
                'group_index': group,
                'turn': 1,
                'assertions': {'response': 'passed'},
            }
            for group in (0, 1)
        ]
        rows += [
            {
                'profile': 'scenarios',
                'case': 'group_reset_isolation',
                'status': 'failed',
                'group_index': 0,
                'turn': 2,
                'assertions': {'reset': 'failed'},
            },
            {'profile': 'scenarios', 'case': 'group_reset_isolation', 'status': 'skipped', 'group_index': 1, 'turn': 2},
        ]
        selected = [
            x for x in report(c, rows)['contracts'] if any(b['case'] == 'group_reset_isolation' for b in x['bindings'])
        ]
        self.assertEqual(sorted(x['status'] for x in selected), ['failed', 'skipped'])

    def test_partial_evidence_produces_an_error_and_a_report(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / 'profile.json').write_text(json.dumps({'coverage_suite': 'smoke', 'smoke': {}}))
            (root / 'cases.json').write_text('[{"case":')
            rows, errors = collect(root)
            self.assertEqual(rows, [])
            self.assertEqual(len(errors), 1)
            result = write_report([root], root)
            self.assertTrue(result['evidence_errors'])
            self.assertEqual(result['kinds']['blackbox']['decided'], 0)
            self.assertTrue((root / 'coverage.md').is_file())

    def test_missing_phase_evidence_cannot_hide_behind_a_successful_phase(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'profile.json').write_text(
                json.dumps(
                    {
                        'coverage_suite': 'smoke',
                        'phases': [{'name': 'first'}, {'name': 'second'}],
                    }
                )
            )
            (root / 'first').mkdir()
            (root / 'first/requests.jsonl').write_text(
                json.dumps(
                    row(
                        assertions={'response': 'passed', 'fields': 'passed'},
                    )
                )
                + '\n'
            )
            rows, errors = collect(root)
            self.assertEqual(len(rows), 1)
            self.assertEqual(len(errors), 1)
            self.assertFalse(report(catalog(), rows, errors)['complete_evidence'])

    def test_empty_and_absent_planned_cases_are_explicit_evidence_errors(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / 'profile.json').write_text(
                json.dumps(
                    {
                        'coverage_suite': 'smoke',
                        'smoke': {},
                        'cases': [{'name': 'chat'}],
                    }
                )
            )
            (root / 'cases.json').write_text('[]')
            rows, errors = collect(root)
            self.assertEqual(rows, [])
            self.assertTrue(any('empty' in error for error in errors))
            self.assertTrue(any('planned cases' in error for error in errors))

    def test_http_hits_use_method_templates_and_do_not_retain_private_urls(self):
        inventory = {
            'routes': [
                {'route': value}
                for value in (
                    'GET /things/<uuid>',
                    'GET /things/new',
                    'POST /things/<uuid>',
                    'POST /bots/<id>/<path:path>',
                )
            ]
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'access.log'
            path.write_text(
                '\n'.join(
                    [
                        'GET /things/new?token=secret 1.1 200',
                        'GET /things/private-id 1.1 404',
                        'POST /things/private-id 1.1 403',
                        'POST /bots/private-bot/reset 1.1 200',
                        'GET /unknown/private-id 1.1 404',
                        'application log is not a request',
                    ]
                )
            )
            result = http_observations([path], inventory)
            self.assertEqual(result['records'], 5)
            self.assertEqual(len(result['routes']), 4)
            self.assertEqual(result['unclassified'], {'GET 404': 1})
            encoded = json.dumps(result)
            for value in ('private-id', 'private-bot', 'secret'):
                self.assertNotIn(value, encoded)
            self.assertTrue(http_observations([path.with_name('missing')], inventory)['evidence_errors'])

    def test_http_converter_and_invalid_url_do_not_create_false_hits_or_leaks(self):
        inventory = {'routes': [{'route': 'GET /keys/<int:id>'}]}
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'access.log'
            path.write_text(
                '\n'.join(
                    [
                        'GET /keys/not-an-int 1.1 404',
                        'GET http://[private-tenant]/?token=secret 1.1 400',
                        'GET /keys/42 1.1 200',
                    ]
                )
            )
            result = http_observations([path], inventory)
            self.assertEqual(result['routes'], [{'route': 'GET /keys/<int:id>', 'statuses': {'200': 1}}])
            self.assertEqual(result['unclassified'], {'GET 404': 1, 'GET 400': 1})
            self.assertEqual(len(result['evidence_errors']), 1)
            self.assertNotIn('private-tenant', json.dumps(result))
            self.assertNotIn('secret', json.dumps(result))

    def test_suite_finalization_rejects_missing_evidence_for_direct_callers(self):
        from regression_suite import Suite

        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            profile = {
                'version': 1,
                'coverage_suite': 'smoke',
                'smoke': {},
                'cli': {'config': 'unused'},
                'cases': [{'name': 'chat'}],
            }
            suite = Suite(profile, root / 'input.json', root)
            suite.write('profile.json', profile)
            result = {'errors': []}
            suite.finish(result)
            self.assertFalse(result['passed'])
            self.assertTrue((root / 'coverage.json').exists())
            self.assertFalse(json.loads((root / 'summary.json').read_text())['passed'])

    def test_new_routes_are_discovered_without_adding_test_cases(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            source = root / 'src/langbot/pkg/example.py'
            source.parent.mkdir(parents=True)
            source.write_text("""
@group.group_class('example', '/api/example')
class Routes:
    async def initialize(self):
        @self.route('/new', methods=['POST'])
        async def new_operation(): pass
        @self.route(dynamic_path)
        async def dynamic_operation(): pass
""")
            inventory = route_inventory(catalog(), root)
            self.assertEqual(inventory['routes'][0]['route'], 'POST /api/example/new')
            self.assertEqual(inventory['routes'][0]['contracts'], [])
            self.assertEqual(len(inventory['unresolved']), 1)

    def test_catalog_bindings_name_real_cases_and_required_checks(self):
        c = load_catalog()
        profiles = {}
        routes = {r['route'] for r in route_inventory(c)['routes']}
        for contract in c['contracts']:
            self.assertTrue(set(contract.get('routes', [])) <= routes)
            for binding in contract['bindings']:
                name = binding['profile']
                if name not in profiles:
                    path = Path(__file__).with_name('regression_profiles') / f'{name}.json'
                    if name == 'scenarios':
                        from regression_scenarios import expanded_profile
                        from regression_local_cases import GROUPS

                        profile = expanded_profile(GROUPS)
                        if 'lifecycle' in GROUPS:
                            from regression_lifecycle_cases import restart_profile

                            profile['cases'] += restart_profile(profile)['cases']
                    else:
                        profile = json.loads(path.read_text())
                    profiles[name] = {x['name']: x for x in profile['cases']}
                self.assertIn(binding['case'], profiles[name])
                self.assertTrue(binding['checks'])
        broken = copy.deepcopy(c)
        broken['contracts'].append(broken['contracts'][0])
        with tempfile.TemporaryDirectory() as d:
            path = Path(d) / 'catalog.json'
            path.write_text(json.dumps(broken))
            with self.assertRaises(ValueError):
                load_catalog(path)


if __name__ == '__main__':
    unittest.main()
