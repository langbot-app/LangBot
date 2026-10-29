"""Expanded finite daily cases built from the maintained PR smoke fixtures."""

import copy
import json
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).parent
RUNNER = 'plugin:langbot-team/LocalAgent/default'


def expanded_profile(groups=()):
    profile = json.loads((ROOT / 'regression_profiles/smoke.json').read_text())
    profile['coverage_suite'] = 'scenarios'
    profile['smoke']['group_turns'] = 3
    resources = {r['id']: r for r in profile['resources']}
    cases = {c['name']: c for c in profile['cases']}

    for rejection in (
        'expired_signature',
        'future_signature',
        'bad_timestamp',
        'tampered_body',
        'invalid_json',
        'invalid_object',
        'missing_session',
        'invalid_message',
    ):
        case = copy.deepcopy(cases['missing_signature'])
        case.update(name=rejection, reject_group=rejection)
        if rejection in ('invalid_json', 'invalid_object', 'missing_session', 'invalid_message'):
            case.update(expect='40001', fields={'http_status': 400, 'code': 40001})
        profile['cases'].append(case)

    for auth in ('missing', 'invalid'):
        profile['cases'].append(
            {
                'name': f'api_auth_{auth}',
                'stage': 'auth',
                'http_probe': {'url': '${core_base_url}/api/v1/pipelines', 'auth': auth},
                'expect': 'http_status',
                'fields': {'http_status': 401},
            }
        )

    def group_case(name, pipeline, message=None):
        bot = copy.deepcopy(resources['chat_bot'])
        bot['id'] = name + '_bot'
        bot['body']['name'] = 'daily ' + name
        bot['body']['event_bindings'][0]['target_uuid'] = '${' + pipeline + '}'
        profile['resources'].append(bot)
        case = copy.deepcopy(cases['group_chat_history'])
        case.update(name=name)
        case['http_group']['url'] = '${core_base_url}/bots/${' + bot['id'] + '}/sync'
        if message:
            case['http_group']['message'] = message
        return case

    for source, message in [
        ('unicode', 'ai 请原样处理：你好，世界 🌍'),
        ('fallback429', None),
        ('exec_error', None),
        ('parallel', None),
    ]:
        case = group_case('group_' + source, source + '_pipeline', message)
        for key in ('expect', 'box_exec', 'mock_requests'):
            if key in cases[source]:
                case[key] = copy.deepcopy(cases[source][key])
        profile['cases'].append(case)

    reset = copy.deepcopy(cases['group_chat_history'])
    reset.update(name='group_reset_isolation', reset_group=True)
    profile['cases'].append(reset)

    for name in ('tool_recovery', 'tool_timeout_recovery', 'empty_rag_chat'):
        model = copy.deepcopy(resources['chat_model'])
        model['id'] = name + '_model'
        model['body']['name'] = 'mock-daily-' + name.replace('_', '-')
        pipeline = copy.deepcopy(resources['box_pipeline' if name.startswith('tool_') else 'rag_pipeline'])
        pipeline['id'] = name + '_pipeline'
        pipeline['body']['name'] = 'daily ' + name
        config = pipeline['body']['config']['ai']['runner_config'][RUNNER]
        config['model'] = {'primary': '${' + model['id'] + '}', 'fallbacks': []}
        if name == 'empty_rag_chat':
            config['knowledge-bases'] = ['${empty_knowledge_base}']
        profile['resources'].extend([model, pipeline])
        case = copy.deepcopy(cases['chat'])
        case.update(
            name=name,
            stage='tools' if name.startswith('tool_') else 'retrieval',
            args=[
                'pipeline',
                'run',
                '${' + pipeline['id'] + '}',
                '--message',
                'Run the daily scenario',
                '--timeout',
                '90s',
            ],
            expect='LANGBOT_' + name.upper() + '_OK',
        )
        profile['cases'].append(case)
    if groups:
        from regression_local_cases import add_cases

        add_cases(profile, groups)
    return profile


class ExecutionWindow:
    """One shared scenario/cleanup deadline, with the existing resource sampler format."""

    def __init__(self, suite):
        self.suite = suite
        self.settings = suite.profile['execution']
        self.started = time.monotonic()
        self.deadline = self.started + self.settings['total_seconds']
        self.cleanup_deadline = self.deadline - self.settings['cooldown_seconds']
        self.admission_deadline = self.cleanup_deadline - self.settings['drain_seconds']
        self.stage = 'prepare'
        self.phases = []
        self.errors = []
        self.stop = threading.Event()
        self.thread = threading.Thread(target=self.sample, daemon=True)

    def start(self):
        self.mark('prepare')
        self.thread.start()

    def mark(self, stage):
        self.stage = stage
        self.phases.append({'stage': stage, 'time': time.time(), 'elapsed': time.monotonic() - self.started})
        self.suite.write('execution.json', {'settings': self.settings, 'phases': self.phases})

    def timeout(self, maximum, *, sampling=False):
        remaining = (self.deadline if sampling else self.cleanup_deadline) - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Shared execution deadline reached; no operation started')
        return min(maximum, remaining)

    def admitting(self):
        return time.monotonic() < self.admission_deadline

    def sample(self):
        from regression_suite import resolve
        from regression_traffic import (
            owned_box_containers,
            read_endpoint_snapshot,
            read_process_snapshot,
            sample_containers,
        )

        def run(command, **kwargs):
            kwargs['timeout'] = self.timeout(kwargs.get('timeout', 10), sampling=True)
            return subprocess.run(command, **kwargs)

        def discover(root):
            def checked(command):
                result = run(command, capture_output=True, text=True, check=True)
                return result.stdout

            return owned_box_containers(root, checked=checked)

        try:
            observed = resolve(self.suite.profile['observe'], self.suite.variables)
            pids = dict(observed.get('pids', {}))
            for name, path in observed.get('pid_files', {}).items():
                pids[name] = int(Path(self.suite.path(path)).read_text().strip())
            with (self.suite.output / 'resources.jsonl').open('w') as stream:
                while not self.stop.is_set() and time.monotonic() < self.deadline:
                    stage = self.stage
                    row = {
                        'time': time.time(),
                        'elapsed': time.monotonic() - self.started,
                        'phase': 'cooldown' if stage == 'cooldown' else 'load',
                        'stage': stage,
                        'targets': {},
                        'health': {},
                    }
                    for name, pid in pids.items():
                        try:
                            row['targets'][name] = read_process_snapshot(pid)
                        except (OSError, RuntimeError) as exc:
                            row['targets'][name] = {'error': str(exc)}
                            self.errors.append(f'{name}: process sample failed: {exc}')
                    for name, url in observed['health'].items():
                        try:
                            row['health'][name] = read_endpoint_snapshot(
                                url, timeout_seconds=self.timeout(3, sampling=True)
                            )
                        except (OSError, RuntimeError, ValueError) as exc:
                            row['health'][name] = {'error': str(exc)}
                            self.errors.append(f'{name}: health sample failed: {exc}')
                    if observed.get('containers') or observed.get('box_data_root'):
                        row.update(
                            sample_containers(
                                observed.get('containers', []),
                                observed.get('box_data_root'),
                                run=run,
                                discover=discover,
                            )
                        )
                        if row.get('container_error'):
                            self.errors.append('Container resource sample failed')
                    stream.write(json.dumps(row) + '\n')
                    stream.flush()
                    self.stop.wait(3)
        except (OSError, RuntimeError, ValueError, KeyError, subprocess.SubprocessError) as exc:
            self.errors.append(f'Resource sampler stopped: {exc}')

    def finish(self, result):
        if time.monotonic() > self.cleanup_deadline:
            result['errors'].append('Execution/drain/cleanup exceeded the shared deadline')
        self.mark('cooldown')
        remaining = max(0, self.deadline - time.monotonic() - min(1, self.settings['cooldown_seconds'] / 10))
        self.stop.wait(min(self.settings['cooldown_seconds'], remaining))
        self.stop.set()
        self.thread.join(timeout=max(0, self.deadline - time.monotonic()))
        if self.thread.is_alive():
            result['errors'].append('Resource sampler did not stop before its drain deadline')
        result['errors'].extend(dict.fromkeys(self.errors))
        if limits := self.suite.profile.get('resource_limits'):
            from regression_analysis import resource_verdict

            try:
                verdict = resource_verdict(self.suite.output, limits)
                result['resources'] = verdict
                result['errors'].extend(verdict['errors'])
                result.setdefault('incomplete', []).extend(verdict['incomplete'])
            except (OSError, ValueError, KeyError) as exc:
                error = f'Resource recovery evidence unavailable: {exc}'
                result['errors'].append(error)
                result.setdefault('incomplete', []).append(error)
        from regression_smoke import reconcile_scenario_runs

        reconcile_scenario_runs(self.suite, result, key='ledger_closeout')
        self.mark('finished')
        result['execution'] = {
            'settings': self.settings,
            'phases': self.phases,
            'elapsed_seconds': time.monotonic() - self.started,
        }
