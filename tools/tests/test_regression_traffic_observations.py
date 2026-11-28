"""Independent interval and sampled-resource oracles for mixed group load evidence."""

import copy
import unittest

from tools.entrypoints.regression_traffic import http_concurrency, resource_observations


def request(case, group, begin, seconds, status='ok'):
    return {'case': case, 'group_id': group, 'elapsed': begin, 'seconds': seconds, 'status': status}


def sample(phase, elapsed, pids, sessions, queued):
    return {
        'phase': phase,
        'elapsed': elapsed,
        'containers': [{'PIDs': str(value)} for value in pids],
        'health': {
            'core': {'body.resources.query_pool.queued': queued},
            'box': {
                'body.resources.sessions': sessions,
                'body.resources.blocking_executor.pending': queued,
                'body.resources.creating_session_tasks': queued,
                'body.resources.closing_session_tasks': queued,
            },
        },
    }


class TrafficObservationsTest(unittest.TestCase):
    def test_actual_roundtrip_intervals_show_overall_and_box_overlap(self):
        rows = [request('box', 'a', 0, 4), request('chat', 'b', 1, 2), request('box', 'c', 2, 3)]
        rows += [
            request('failed', 'd', 0, 100, 'unknown'),
            {'case': 'cli', 'elapsed': 0, 'seconds': 100, 'status': 'ok'},
        ]
        observed = http_concurrency(rows)
        self.assertEqual(observed['peak_in_flight'], 3)
        self.assertEqual(observed['overlap_seconds'], 3)
        self.assertEqual(observed['cases']['box']['peak_in_flight'], 2)
        self.assertEqual(observed['cases']['box']['overlap_seconds'], 2)
        self.assertEqual(observed['cases']['chat']['peak_in_flight'], 1)
        self.assertEqual(observed['cases']['failed']['status'], 'unknown')
        self.assertEqual(observed['requests'], 3)
        self.assertNotIn('cli', observed['cases'])

    def test_touching_requests_are_serial_and_missing_intervals_are_unknown(self):
        observed = http_concurrency([request('box', 'a', 0, 1), request('box', 'b', 1, 1)])
        self.assertEqual(observed['peak_in_flight'], 1)
        self.assertEqual(observed['overlap_seconds'], 0)
        for rows in ([], [request('box', 'a', 0, None)], [request('box', 'a', 0, float('nan'))]):
            with self.subTest(rows=rows):
                self.assertEqual(http_concurrency(rows)['status'], 'unknown')
                self.assertIsNone(http_concurrency(rows)['peak_in_flight'])

    def test_container_scale_and_session_scale_remain_distinct_from_queue_recovery(self):
        rows = [
            sample('load', 0, [2, 1, 0], 4, 3),
            sample('load', 3, [1, 1, 1], 5, 5),
            sample('cooldown', 10, [1], 5, 2),
            sample('cooldown', 50, [1], 5, 0),
            sample('cooldown', 53, [1], 5, 0),
        ]
        observed = resource_observations(rows)
        self.assertEqual(observed['running_containers']['peak'], 3)
        self.assertEqual(observed['box_sessions']['peak'], 5)
        for queue in observed['queues'].values():
            self.assertEqual(queue['status'], 'observed')
            self.assertEqual(queue['load_peak'], 5)
            self.assertEqual(queue['cooldown_tail_max'], 0)
            self.assertEqual(queue['cooldown_tail_samples'], 2)

    def test_missing_metrics_or_cooldown_never_become_zero_recovery(self):
        rows = [sample('load', 0, [], 0, 0), sample('cooldown', 30, [], 0, 0)]
        for key in ('containers', 'health'):
            missing = copy.deepcopy(rows)
            del missing[-1][key]
            observed = resource_observations(missing)
            if key == 'containers':
                self.assertEqual(observed['running_containers']['status'], 'unknown')
            else:
                self.assertEqual(observed['box_sessions']['status'], 'unknown')
                self.assertTrue(all(queue['status'] == 'unknown' for queue in observed['queues'].values()))
        for queue in resource_observations(rows[:1])['queues'].values():
            self.assertEqual(queue['status'], 'unknown')
            self.assertIsNone(queue['cooldown_tail_max'])
        zero = resource_observations(rows)
        self.assertEqual(zero['running_containers']['status'], 'observed')
        self.assertEqual(zero['running_containers']['peak'], 0)
        self.assertEqual(zero['box_sessions']['peak'], 0)
        self.assertEqual(resource_observations([])['running_containers']['status'], 'unknown')


if __name__ == '__main__':
    unittest.main()
