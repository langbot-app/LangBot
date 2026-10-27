#!/usr/bin/env python3
"""Own one complete lbctl deployment, mock backend, regression, and teardown."""

import argparse
import copy
import json
import os
from pathlib import Path
import re
import secrets
import shutil
import subprocess
import time
import urllib.error
import urllib.request

import yaml

from regression_suite import Suite, number, resolve, validate
from regression_traffic import owned_box_containers


KEY_ENV = 'LANGBOT_QA_API_KEY'


def write_json(path, data):
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2))
    temporary.chmod(0o600)
    temporary.replace(path)


def load_profile(path):
    profile = json.loads(path.read_text())
    if not isinstance(profile, dict) or profile.get('version') != 1:
        raise ValueError('job profile version must be 1')
    if profile.keys() - {'version', 'lbctl', 'suite', 'deployment', 'vars', 'cleanup', 'purge_data', 'mock_image'}:
        raise ValueError('unknown job profile field')
    deployment = profile.get('deployment', {})
    if not isinstance(deployment, dict) or deployment.keys() - {'version', 'port'}:
        raise ValueError('deployment accepts version and port')
    version = deployment.get('version', '')
    if not isinstance(version, str) or not re.fullmatch(r'v[0-9]+\.[0-9]+\.[0-9]+', version):
        raise ValueError('deployment.version must pin a stable vX.Y.Z Release')
    number(deployment.get('port', 5300), 'deployment port', minimum=1, integer=True)
    if deployment.get('port', 5300) > 65535:
        raise ValueError('deployment port must be <= 65535')
    if profile.get('cleanup', 'on-success') not in ('always', 'on-success', 'never'):
        raise ValueError('cleanup must be always/on-success/never')
    if not isinstance(profile.get('purge_data', True), bool):
        raise ValueError('purge_data must be boolean')
    suite_path = Path(profile['suite']).expanduser()
    suite_path = suite_path if suite_path.is_absolute() else path.parent / suite_path
    suite = json.loads(suite_path.read_text())
    suite.setdefault('vars', {}).update(profile.get('vars', {}))
    suite['vars'].update(
        mock_base_url='http://regression_mock:18080/v1', embedding_base_url='http://regression_mock:18080/v1'
    )
    suite['cli'] = {'config': 'job-generated.yaml'}
    for item in suite.get('resources', []):
        if item['kind'] == 'model' and item.get('type') == 'embedding':
            item['body']['name'] = 'mock-embedding'
    validate(suite)
    return profile, suite, suite_path.resolve()


class Job:
    def __init__(self, profile, suite_profile, suite_path, output):
        self.profile = profile
        self.suite_profile = copy.deepcopy(suite_profile)
        self.suite_path = suite_path
        self.output = output.resolve()
        self.private = self.output / '.private'
        self.deploy = self.private / 'deployment'
        self.state_path = self.output / 'state.json'
        self.cli_config = self.private / 'lbctl.yaml'
        self.env = {**os.environ, 'XDG_CONFIG_HOME': str(self.private / 'config')}
        self.cli = [profile.get('lbctl', 'lbctl'), '--config', str(self.cli_config), '-o', 'json']
        self.redactions = []
        self.state = {'job_id': secrets.token_hex(8), 'record': None, 'bound': False, 'phase': 'created'}

    def redact(self, value):
        for secret in self.redactions:
            value = value.replace(secret, '[REDACTED]')
        return value

    def save(self):
        write_json(self.state_path, self.state)

    def recover_record(self):
        if (self.private / 'job-id').read_text().strip() != self.state['job_id']:
            raise RuntimeError('Job ownership marker differs from state.json')
        path = self.deploy / 'deployment.yaml'
        if not path.exists():
            if self.state.get('record'):
                raise RuntimeError('deployment record disappeared; refusing cleanup')
            return
        if path.is_symlink():
            raise RuntimeError('deployment record must not be a symlink')
        try:
            record = yaml.safe_load(path.read_text())
        except yaml.YAMLError as exc:
            raise ValueError('invalid deployment YAML') from exc
        if not isinstance(record, dict) or not record.get('deployment_id'):
            raise RuntimeError('invalid deployment record')
        if (
            Path(record['compose_file']).resolve().parent != self.deploy
            or Path(record['data_dir']).resolve() != self.deploy / 'data'
            or Path(record['env_file']).resolve().parent != self.deploy
        ):
            raise RuntimeError('deployment record is outside this Job')
        if self.state.get('record') and record['deployment_id'] != self.state['record']['deployment_id']:
            raise RuntimeError('deployment identity changed; refusing cleanup')
        self.state['record'] = record
        self.save()

    def load_redactions(self):
        if self.state.get('record'):
            path = Path(self.state['record']['env_file'])
            if path.exists():
                for line in path.read_text().splitlines():
                    name, separator, value = line.partition('=')
                    if separator and any(word in name for word in ('TOKEN', 'KEY')) and len(value) >= 16:
                        self.redactions.append(value)

    def command(self, args, timeout=900):
        result = subprocess.run(args, capture_output=True, text=True, env=self.env, timeout=timeout)
        return result.returncode, self.redact(result.stdout), self.redact(result.stderr)

    def checked(self, args, timeout=900):
        code, stdout, stderr = self.command(args, timeout)
        if code:
            raise RuntimeError((stderr + stdout)[-4000:])
        return stdout

    def cli_call(self, args):
        code, stdout, stderr = self.command([*self.cli, *args])
        result = json.loads(stdout) if stdout.strip() else {}
        data = result.get('data', {})
        if args[0] == 'install' and isinstance(data, dict) and data.get('record'):
            record = data['record']
            if (
                Path(record['compose_file']).resolve().parent != self.deploy
                or Path(record['data_dir']).resolve() != self.deploy / 'data'
            ):
                raise RuntimeError('install returned a deployment outside this Job')
            self.state['record'] = record
            self.save()  # Installation may have changed state even when its final health check failed.
        if code:
            raise RuntimeError((stderr + stdout)[-4000:])
        return data

    def compose(self, *args, override=False):
        record = self.state['record']
        command = ['docker', 'compose', '--project-name', record['compose_project'], '--file', record['compose_file']]
        if override:
            command += ['--file', str(self.private / 'compose.override.json')]
        command += ['--env-file', record['env_file'], '--profile', 'all', *args]
        return self.checked(command)

    def project_containers(self):
        project = self.state['record']['compose_project']
        output = self.checked(
            [
                'docker',
                'ps',
                '-a',
                '--filter',
                f'label=com.docker.compose.project={project}',
                '--format',
                '{{.ID}} {{.Label "com.docker.compose.service"}}',
            ]
        )
        return {service: container for container, service in (line.split() for line in output.splitlines() if line)}

    def address(self, container):
        networks = json.loads(
            self.checked(['docker', 'inspect', '--format', '{{json .NetworkSettings.Networks}}', container])
        )
        addresses = [network['IPAddress'] for network in networks.values() if network.get('IPAddress')]
        if len(addresses) != 1:
            raise RuntimeError('expected one private container network')
        return addresses[0]

    @staticmethod
    def ready(url):
        deadline = time.monotonic() + 120
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        while time.monotonic() < deadline:
            try:
                with opener.open(url, timeout=2) as response:
                    payload = json.load(response)
                    if response.status == 200 and payload.get('ready') is not False and payload.get('code', 0) == 0:
                        return
            except (urllib.error.URLError, TimeoutError, OSError, ValueError):
                pass
            time.sleep(0.5)
        raise RuntimeError(f'readiness deadline exceeded: {url}')

    def prepare(self):
        variables = {
            **self.suite_profile.get('vars', {}),
            'profile_dir': str(self.suite_path.parent),
            'run_dir': str(self.output),
        }
        inputs = [plugin['file'] for plugin in self.suite_profile.get('plugins', [])]
        inputs += [
            document['file']
            for item in self.suite_profile.get('resources', [])
            for document in item.get('documents', [])
        ]
        for name in inputs:
            path = Path(resolve(name, variables)).expanduser()
            path = path if path.is_absolute() else self.suite_path.parent / path
            if not path.is_file():
                raise ValueError(f'Job input file is missing: {path}')
        self.state['phase'] = 'install'
        self.save()
        # Current Box runtimes reap sandboxes from previous runtime IDs on startup.
        # Do not start one alongside another user's live sandbox on this daemon.
        boxes = self.checked(['docker', 'ps', '-a', '--filter', 'label=langbot.box=true', '--format', '{{.ID}}'])
        if boxes.strip():
            raise RuntimeError('Docker daemon has existing Box sandboxes; use an idle dedicated test daemon')
        key = secrets.token_urlsafe(32)
        self.env[KEY_ENV] = key
        self.env['LANGBOT_API_KEY'] = key
        self.redactions.append(key)
        (self.private / 'api-key').write_text(key)
        (self.private / 'api-key').chmod(0o600)
        deployment = self.profile['deployment']
        self.cli_call(
            [
                'install',
                '--dir',
                str(self.deploy),
                '--version',
                deployment['version'],
                '--profile',
                'all',
                '--port',
                str(deployment.get('port', 5300)),
            ]
        )
        self.recover_record()
        self.load_redactions()
        mock_results = self.output / 'mock'
        mock_results.mkdir(mode=0o700)
        override = {
            'services': {
                'langbot': {
                    'environment': {'API__GLOBAL_API_KEY': key},
                    'volumes': [f'{self.deploy / "data/box"}:{self.deploy / "data/box"}'],
                },
                'regression_mock': {
                    'image': self.profile.get('mock_image', 'python:3.12-alpine'),
                    'volumes': [f'{Path(__file__).parent.resolve()}:/regression:ro', f'{mock_results}:/results'],
                    'command': [
                        'python',
                        '/regression/mock_llm.py',
                        '--host',
                        '0.0.0.0',
                        '--port',
                        '18080',
                        '--record',
                        '/results/requests.jsonl',
                    ],
                    'networks': ['langbot_network'],
                    'labels': {'langbot.regression_job': self.state['job_id']},
                },
            },
        }
        write_json(self.private / 'compose.override.json', override)
        self.compose('up', '-d', override=True)
        containers = self.project_containers()
        for service in ('langbot', 'langbot_plugin_runtime', 'langbot_box', 'regression_mock'):
            if service not in containers:
                raise RuntimeError(f'missing deployment service: {service}')
        endpoint = self.state['record']['endpoint']
        health = {
            'core': endpoint + '/healthz',
            'mock': f'http://{self.address(containers["regression_mock"])}:18080/healthz',
            'box': f'http://{self.address(containers["langbot_box"])}:5410/readyz',
        }
        for url in health.values():
            self.ready(url)
        identity = self.cli_call(['--endpoint', endpoint, 'whoami'])
        self.cli_call(
            [
                'context',
                'add',
                'regression',
                '--endpoint',
                endpoint,
                '--api-key-env',
                KEY_ENV,
                '--expect-workspace',
                identity['workspace_uuid'],
            ]
        )
        self.cli_call(['context', 'use', 'regression'])
        self.state.update(
            bound=True, workspace_uuid=identity['workspace_uuid'], containers=containers, phase='resources'
        )
        self.save()
        profile = self.suite_profile
        profile.setdefault('vars', {})['core_base_url'] = endpoint
        if 'smoke' in profile:
            if 'mock_records' in profile['smoke']:
                profile['smoke']['mock_records'] = str(self.output / 'mock' / 'requests.jsonl')
            profile['smoke']['ledger_db'] = str(Path(self.state['record']['data_dir']) / 'langbot.db')
        if 'verification' in profile:
            profile['verification']['ledger_db'] = str(Path(self.state['record']['data_dir']) / 'langbot.db')
        profile['cli'] = {'executable': self.cli[0], 'config': str(self.cli_config)}
        profile['observe'] = {'health': health, 'pids': {}, 'containers': list(containers.values())}
        for service, container in containers.items():
            pid = int(self.checked(['docker', 'inspect', '--format', '{{.State.Pid}}', container]).strip())
            name = (
                {'langbot': 'core', 'langbot_plugin_runtime': 'runtime', 'langbot_box': 'box'}.get(service, service)
                if profile.get('verification')
                else service
            )
            profile['observe']['pids'][name] = pid
        destination = self.output / 'suite'
        destination.mkdir(mode=0o700)
        suite = Suite(profile, self.suite_path, destination, env=self.env)
        self.redactions.extend(suite.secrets)
        suite.write('profile.json', profile)
        if 'smoke' not in profile:
            from regression_analysis import workload_contract

            suite.write('workload.json', workload_contract(profile, self.suite_path))
        suite.prepare()
        if 'smoke' in profile:
            return suite
        # Prime every configured business case before measuring steady load.
        for case in profile['cases']:
            case = resolve(case, suite.variables)
            if 'http_group' in case:
                continue  # Suite preparation already verifies signed group ingress and the masked secret.
            data = suite.call(case['args'], case.get('body'))
            if case['expect'] not in json.dumps(data, ensure_ascii=False):
                raise RuntimeError(f'warmup oracle failed: {case["name"]}')
        profile['observe']['box_data_root'] = str(Path(self.state['record']['data_dir']) / 'box')
        suite.write('profile.json', profile)
        return suite

    def owned_sandboxes(self):
        record = self.state.get('record')
        if not record:
            return []
        return owned_box_containers(Path(record['data_dir']) / 'box', self.checked)

    def collect(self):
        self.recover_record()
        self.load_redactions()
        if self.state.get('record'):
            logs = self.compose('logs', '--no-color', '--tail', '10000')
            (self.output / 'services.log').write_text(logs)

    def cleanup(self):
        self.recover_record()
        self.load_redactions()
        record = self.state.get('record')
        if self.state['phase'] == 'cleaned':
            if record and self.project_containers():
                raise RuntimeError('containers appeared after Job cleanup; inspect deployment before acting')
            return
        if record:
            if (
                Path(record['compose_file']).resolve().parent != self.deploy
                or Path(record['data_dir']).resolve() != self.deploy / 'data'
            ):
                raise RuntimeError('cleanup refused: deployment is outside this Job')
            if self.state['bound']:
                self.cli_call(['stop'])
            else:
                self.compose('stop', override=(self.private / 'compose.override.json').exists())
            sandboxes = self.owned_sandboxes()
            if sandboxes:
                self.checked(['docker', 'rm', '-f', *sandboxes])
            if self.state['bound']:
                self.cli_call(
                    ['uninstall', '--yes', *(['--purge-data'] if self.profile.get('purge_data', True) else [])]
                )
            else:
                self.compose('down', '--remove-orphans', override=(self.private / 'compose.override.json').exists())
                if self.profile.get('purge_data', True) and (self.deploy / 'data').exists():
                    shutil.rmtree(self.deploy / 'data')
        for path in (self.private / 'api-key', self.private / 'compose.override.json'):
            path.unlink(missing_ok=True)
        self.state['phase'] = 'cleaned'
        self.save()

    def run(self):
        self.output.mkdir(parents=True, exist_ok=False, mode=0o700)
        self.private.mkdir(mode=0o700)
        (self.private / 'job-id').write_text(self.state['job_id'])
        write_json(self.output / 'job-profile.json', self.profile)
        self.save()
        result = {'errors': [], 'completed': False}
        try:
            suite = self.prepare()
            self.state['phase'] = 'traffic'
            self.save()
            summary = suite.run()
            summary['passed'] = not summary['errors']
            suite.write('summary.json', summary)
            result.update(completed=True, suite=summary, errors=list(summary['errors']))
            self.state['phase'] = 'finished'
            self.save()
        except KeyboardInterrupt:
            result['errors'].append('Job interrupted; in-flight outcomes may be unknown')
        except (RuntimeError, ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
            result['errors'].append(self.redact(str(exc)))
        finally:
            if not result['completed'] and not result['errors']:
                result['errors'].append('Job aborted before completion')
            try:
                self.collect()
            except (RuntimeError, ValueError, OSError, subprocess.TimeoutExpired) as exc:
                result['errors'].append('artifact collection: ' + self.redact(str(exc)))
            policy = self.profile.get('cleanup', 'on-success')
            if policy == 'always' or (policy == 'on-success' and not result['errors']):
                try:
                    self.cleanup()
                except (RuntimeError, ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
                    result['errors'].append('cleanup: ' + self.redact(str(exc)))
            result.update(passed=not result['errors'], phase=self.state['phase'])
            write_json(self.output / 'summary.json', result)
        return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('validate', 'run', 'cleanup'))
    parser.add_argument('--profile', type=Path)
    parser.add_argument('--output', type=Path)
    parser.add_argument('--duration', type=float)
    parser.add_argument('--rps', type=float)
    parser.add_argument('--workers', type=int)
    parser.add_argument('--groups', type=int)
    parser.add_argument('--members-per-group', type=int)
    args = parser.parse_args()
    try:
        if args.action == 'cleanup':
            if args.output is None:
                raise ValueError('--output is required for cleanup')
            profile = json.loads((args.output / 'job-profile.json').read_text())
            job = Job(profile, {}, args.output / 'unused-profile.json', args.output)
            job.state = json.loads(job.state_path.read_text())
            if (job.private / 'api-key').exists():
                key = (job.private / 'api-key').read_text()
                job.env[KEY_ENV] = key
                job.env['LANGBOT_API_KEY'] = key
                job.redactions.append(key)
            job.cleanup()
            return
        if args.profile is None:
            raise ValueError('--profile is required for run/validate')
        profile, suite, path = load_profile(args.profile.resolve())
        if 'smoke' in suite and any(
            getattr(args, flag) is not None for flag in ('duration', 'rps', 'workers', 'groups', 'members_per_group')
        ):
            raise ValueError('Load overrides are not applicable to smoke mode')
        for phase in suite.get('phases', []):
            for flag, field in [
                ('duration', 'duration_seconds'),
                ('rps', 'rps'),
                ('workers', 'workers'),
                ('groups', 'groups'),
                ('members_per_group', 'members_per_group'),
            ]:
                if getattr(args, flag) is not None:
                    phase[field] = getattr(args, flag)
        validate(suite)
        if args.action == 'validate':
            print('Job profile valid; no deployment or backend changed.')
            return
        if args.output is None:
            raise ValueError('--output is required for run')
        job = Job(profile, suite, path, args.output)
        result = job.run()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result['passed']:
            raise SystemExit(1)
    except (RuntimeError, ValueError, OSError, KeyError, subprocess.TimeoutExpired) as exc:
        parser.exit(1, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()
