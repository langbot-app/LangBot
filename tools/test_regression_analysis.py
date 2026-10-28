"""Counterexamples for load resource recovery and compatible-run comparisons."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from regression_analysis import compare, container_metrics, resource_verdict, workload_contract


class AnalysisTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.limits = {
            'warmup_seconds': 10,
            'window_seconds': 10,
            'min_samples': 3,
            'targets': {'core': {'rss_bytes': 100, 'open_fds': 2}},
        }

    def resources(self, tail_fds=10, omit=False):
        samples = [
            {'phase': phase, 'elapsed': second, 'targets': {'core': {'rss_bytes': 1000, 'open_fds': fds}}}
            for phase, seconds, fds in [('load', range(10, 20), 10), ('cooldown', range(30, 40), tail_fds)]
            for second in seconds
        ]
        if omit:
            samples = [row for row in samples if row['phase'] == 'load']
        (self.root / 'resources.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in samples))

    def test_healthy_responses_cannot_hide_retained_fds(self):
        self.resources()
        self.assertEqual(resource_verdict(self.root, self.limits)['errors'], [])
        self.resources(tail_fds=40)
        self.assertIn('retained growth', resource_verdict(self.root, self.limits)['errors'][0])

    def test_missing_cooldown_is_unknown_not_zero_growth(self):
        self.resources(omit=True)
        self.assertIn('unknown', resource_verdict(self.root, self.limits)['errors'][0])
        self.resources()
        data = (self.root / 'resources.jsonl').read_text().replace('"core"', '"other"')
        (self.root / 'resources.jsonl').write_text(data)
        self.assertTrue(resource_verdict(self.root, self.limits)['errors'])

    def test_docker_memory_is_independent_of_service_process_rss(self):
        row = {'containers': [{'MemUsage': '10MiB / 1GiB', 'PIDs': '2'}, {'MemUsage': '5MiB / 1GiB', 'PIDs': '3'}]}
        self.assertEqual(container_metrics(row), {'memory_bytes': 15 * 1024**2, 'pids': 5, 'count': 2})
        self.assertEqual(container_metrics({'container_error': 'EOF', **row}), {})
        self.resources()
        rows = [json.loads(line) for line in (self.root / 'resources.jsonl').read_text().splitlines()]
        for sample in rows:
            sample['containers'] = [
                {'MemUsage': ('10MiB' if sample['phase'] == 'load' else '100MiB') + ' / 1GiB', 'PIDs': '1'}
            ]
        (self.root / 'resources.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
        verdict = resource_verdict(self.root, {**self.limits, 'containers': {'memory_bytes': 1024**2}})
        self.assertIn('docker_containers/memory_bytes', verdict['errors'][0])

    def test_empty_observed_container_set_is_successful_recovery(self):
        self.resources()
        rows = [json.loads(line) for line in (self.root / 'resources.jsonl').read_text().splitlines()]
        for row in rows:
            row['containers'] = [{'MemUsage': '10MiB / 1GiB', 'PIDs': '2'}] if row['phase'] == 'load' else []
        limits = {**self.limits, 'containers': {'memory_bytes': 0, 'pids': 0, 'count': 0}}

        def verdict():
            (self.root / 'resources.jsonl').write_text(''.join(json.dumps(row) + '\n' for row in rows))
            return resource_verdict(self.root, limits)

        result = verdict()
        self.assertEqual(result['errors'], [])
        for metric in limits['containers']:
            self.assertEqual(result['targets']['docker_containers'][metric]['cooldown_median'], 0)
        rows[-1]['container_error'] = 'collection failed'
        self.assertTrue(verdict()['errors'])
        del rows[-1]['container_error']
        del rows[-1]['containers']
        self.assertTrue(verdict()['errors'])

    def test_stimulus_variables_are_compared_but_target_origin_is_not(self):
        profile = {
            'vars': {'prompt': 'first', 'endpoint': 'http://127.0.0.1:1'},
            'cases': [
                {'args': ['pipeline', 'run', '--message', '${prompt}'], 'http_group': {'url': '${endpoint}/sync'}}
            ],
        }
        before = workload_contract(profile, self.root / 'profile.json')
        profile['vars']['endpoint'] = 'http://127.0.0.1:2'
        self.assertEqual(before, workload_contract(profile, self.root / 'profile.json'))
        profile['vars']['prompt'] = 'changed'
        self.assertNotEqual(before, workload_contract(profile, self.root / 'profile.json'))

    def fixture_runs(self):
        summary = {
            'passed': True,
            'phases': [
                {
                    'name': 'sustained',
                    'achieved_rps': 1,
                    'verification_enabled': True,
                    'verified_runs': 100,
                    'ledger_closeout': {'matched': True},
                    'runner_requests': 100,
                    'cases': {'chat': {'requests': 100, 'p95_seconds': 1}},
                }
            ],
        }
        for name in ['baseline', 'candidate']:
            root = self.root / name
            root.mkdir()
            (root / 'summary.json').write_text(json.dumps(summary))
            (root / 'workload.json').write_text(json.dumps({'verified_runs': True, 'fixture': 'golden'}))
            (root / 'environment.json').write_text(
                json.dumps(
                    {
                        'plugins': {
                            'plugins': [
                                {
                                    'author': 'team',
                                    'name': 'Runner',
                                    'version': '1',
                                    'enabled': True,
                                    'status': 'initialized',
                                }
                            ]
                        }
                    }
                )
            )
        return self.root / 'baseline', self.root / 'candidate', summary

    def test_comparison_rejects_slow_underfed_missing_or_unverified_samples(self):
        baseline, candidate, original = self.fixture_runs()
        self.assertTrue(compare(baseline, candidate)['passed'])
        for field, value in [('p95_seconds', 1.5), ('requests', 2), ('p95_seconds', float('nan'))]:
            summary = copy.deepcopy(original)
            summary['phases'][0]['cases']['chat'][field] = value
            (candidate / 'summary.json').write_text(json.dumps(summary))
            with self.subTest(field=field, value=value):
                self.assertFalse(compare(baseline, candidate)['passed'])
        for field, value in [
            ('achieved_rps', 0.5),
            ('achieved_rps', float('nan')),
            ('verified_runs', 99),
            ('ledger_closeout', {'matched': False}),
        ]:
            summary = copy.deepcopy(original)
            summary['phases'][0][field] = value
            (candidate / 'summary.json').write_text(json.dumps(summary))
            with self.subTest(field=field):
                self.assertFalse(compare(baseline, candidate)['passed'])

    def test_comparison_refuses_different_workload_or_failed_baseline(self):
        baseline, candidate, summary = self.fixture_runs()
        (candidate / 'workload.json').write_text(json.dumps({'verified_runs': True, 'fixture': 'changed'}))
        self.assertIn('not comparable', compare(baseline, candidate)['errors'][0])
        (candidate / 'workload.json').write_text((baseline / 'workload.json').read_text())
        summary['passed'] = False
        (baseline / 'summary.json').write_text(json.dumps(summary))
        self.assertFalse(compare(baseline, candidate)['passed'])

    def test_fixture_content_changes_contract_even_at_same_path(self):
        fixture = self.root / 'fixture.txt'
        fixture.write_text('before')
        profile = {'resources': [{'documents': [{'file': 'fixture.txt'}]}]}
        before = workload_contract(profile, self.root / 'profile.json')
        fixture.write_text('after')
        self.assertNotEqual(before, workload_contract(profile, self.root / 'profile.json'))


if __name__ == '__main__':
    unittest.main()
