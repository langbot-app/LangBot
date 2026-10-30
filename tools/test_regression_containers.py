"""Container expiry must not hide Docker failures or expand cleanup ownership."""

import json
import subprocess
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

from regression_traffic import owned_box_containers, sample_containers


def description(container, mount):
    return json.dumps({'Id': container, 'Mounts': [{'Source': mount}]})


class ContainerSamplingTests(unittest.TestCase):
    def test_eof_resamples_survivors_and_new_containers_after_confirmed_deletion(self):
        run = Mock(
            side_effect=[
                SimpleNamespace(returncode=1, stdout='', stderr='EOF\n'),
                SimpleNamespace(
                    returncode=0,
                    stdout='{"Container":"configured","PIDs":"1"}\n'
                    '{"Container":"live","PIDs":"1"}\n{"Container":"new","PIDs":"1"}\n',
                    stderr='',
                ),
            ]
        )
        result = sample_containers(['configured'], '/owned', run, Mock(side_effect=[['old', 'live'], ['live', 'new']]))
        self.assertNotIn('container_error', result)
        self.assertEqual(result['container_churn'], {'removed': ['old'], 'added': ['new'], 'first_error': 'EOF'})
        self.assertEqual([entry['Container'] for entry in result['containers']], ['configured', 'live', 'new'])
        self.assertEqual(run.call_count, 2)
        self.assertEqual(run.call_args.args[0][-3:], ['configured', 'live', 'new'])

    def test_eof_without_confirmed_dynamic_deletion_remains_failure(self):
        for configured, discoveries in (
            ([], [['live'], ['live']]),
            ([], [['live'], ['live', 'new']]),
            (['configured'], [['configured', 'live'], ['live']]),
        ):
            with self.subTest(configured=configured, discoveries=discoveries):
                run = Mock(return_value=SimpleNamespace(returncode=1, stdout='', stderr='EOF'))
                result = sample_containers(configured, '/owned', run, Mock(side_effect=discoveries))
                self.assertEqual(result['container_error'], 'EOF')
                self.assertNotIn('container_churn', result)
                self.assertEqual(run.call_count, 1)

    def test_eof_discovery_failure_cannot_confirm_deletion(self):
        error = subprocess.CalledProcessError(1, ['docker', 'ps'], '', 'permission denied')
        run = Mock(return_value=SimpleNamespace(returncode=1, stdout='', stderr='EOF'))
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            sample_containers([], '/owned', run, Mock(side_effect=[['old'], error]))
        self.assertIs(caught.exception, error)
        self.assertEqual(run.call_count, 1)

    def test_eof_retry_failure_is_not_hidden_or_retried_again(self):
        for error in ('EOF', 'permission denied', 'Error response from daemon: No such container: configured'):
            with self.subTest(error=error):
                run = Mock(
                    side_effect=[
                        SimpleNamespace(returncode=1, stdout='', stderr='EOF'),
                        SimpleNamespace(returncode=1, stdout='', stderr=error),
                    ]
                )
                result = sample_containers(['configured'], '/owned', run, Mock(side_effect=[['old', 'live'], ['live']]))
                self.assertEqual(result['container_error'], error)
                self.assertEqual(result['container_churn']['first_error'], 'EOF')
                self.assertEqual(run.call_count, 2)
        run = Mock(
            side_effect=[
                SimpleNamespace(returncode=1, stdout='', stderr='EOF'),
                SimpleNamespace(returncode=0, stdout='{truncated', stderr=''),
            ]
        )
        with self.assertRaises(ValueError):
            sample_containers([], '/owned', run, Mock(side_effect=[['old', 'live'], ['live']]))

    def test_only_empty_output_and_pure_exit_one_eof_can_recover(self):
        for code, error, stdout in (
            (2, 'EOF', ''),
            (1, 'EOF\npermission denied', ''),
            (1, 'EOF', '{"Container":"partial"}'),
        ):
            with self.subTest(code=code, error=error, stdout=stdout):
                run = Mock(return_value=SimpleNamespace(returncode=code, stdout=stdout, stderr=error))
                discover = Mock(side_effect=[['old', 'live'], ['live']])
                result = sample_containers([], '/owned', run, discover)
                self.assertEqual(result['container_error'], error)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(discover.call_count, 1)

    def test_expiry_between_list_and_inspect_preserves_owned_survivors(self):
        for error in (
            subprocess.CalledProcessError(1, ['docker', 'inspect'], '\n', 'Error: No such object: expired'),
            RuntimeError('Error: No such object: expired\n'),
        ):
            with self.subTest(error=type(error).__name__):
                checked = Mock(
                    side_effect=[
                        'expired live foreign',
                        error,
                        description('live', '/owned/box/session'),
                        description('foreign', '/owned/box-other/session'),
                    ]
                )
                self.assertEqual(owned_box_containers('/owned/box', checked), ['live'])

    def test_inspect_errors_are_not_reported_as_expiry(self):
        for error in (
            subprocess.CalledProcessError(1, [], '', 'permission denied'),
            subprocess.CalledProcessError(1, [], '', 'Cannot connect to the Docker daemon'),
            subprocess.CalledProcessError(1, [], '', 'Error: No such object: different-id'),
            subprocess.CalledProcessError(1, [], '', 'Error: No such object: live\npermission denied'),
            subprocess.CalledProcessError(2, [], '', 'Error: No such object: live'),
            subprocess.CalledProcessError(1, [], '{"partial":true}', 'Error: No such object: live'),
            subprocess.TimeoutExpired(['docker', 'inspect'], 10),
            RuntimeError('Cannot connect to the Docker daemon'),
        ):
            with self.subTest(error=repr(error)):
                with self.assertRaises(type(error)) as caught:
                    owned_box_containers('/owned', Mock(side_effect=['live', error]))
                self.assertIs(caught.exception, error)

    def test_malformed_inspection_fails_instead_of_dropping_a_sample(self):
        for output in (
            '',
            '{truncated',
            '{}',
            '{"Mounts":null}',
            '[]',
            '{"Id":"live","Mounts":[null]}',
            '{"Id":"other","Mounts":[]}',
            '{"Id":"live","Mounts":[{"Source":42}]}',
        ):
            with self.subTest(output=output):
                with self.assertRaises((ValueError, KeyError, TypeError)):
                    owned_box_containers('/owned', Mock(side_effect=['live', output]))

    def test_discovery_failure_is_not_an_empty_inventory(self):
        error = subprocess.CalledProcessError(1, [], '', 'permission denied')
        with self.assertRaises(subprocess.CalledProcessError) as caught:
            owned_box_containers('/owned', Mock(side_effect=error))
        self.assertIs(caught.exception, error)

    def test_unrelated_stats_failure_is_not_hidden_by_concurrent_removal(self):
        for error in (
            'permission denied',
            'Cannot connect to the Docker daemon',
            'Error response from daemon: No such container: old\npermission denied',
        ):
            with self.subTest(error=error):
                run = Mock(return_value=SimpleNamespace(returncode=1, stdout='', stderr=error))
                discover = Mock(side_effect=[['old', 'live'], ['live']])
                result = sample_containers([], '/owned', run, discover)
                self.assertEqual(result['container_error'], error)
                self.assertEqual(run.call_count, 1)
                self.assertEqual(discover.call_count, 1)

    def test_configured_container_loss_remains_a_failure(self):
        error = 'Error response from daemon: No such container: configured'
        run = Mock(return_value=SimpleNamespace(returncode=1, stdout='', stderr=error))
        result = sample_containers(['configured'], '/owned', run, Mock(return_value=[]))
        self.assertEqual(result['container_error'], error)
        self.assertEqual(run.call_count, 1)

    def test_all_dynamic_containers_removed_returns_observed_churn(self):
        for error in ('Error response from daemon: No such container: old', 'EOF'):
            with self.subTest(error=error):
                run = Mock(return_value=SimpleNamespace(returncode=1, stdout='', stderr=error))
                result = sample_containers([], '/owned', run, Mock(side_effect=[['old'], []]))
                self.assertEqual(result['containers'], [])
                self.assertEqual(result['container_churn']['removed'], ['old'])
                self.assertEqual(result['container_churn']['first_error'], error)
                self.assertNotIn('container_error', result)


if __name__ == '__main__':
    unittest.main()
