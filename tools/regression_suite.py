#!/usr/bin/env python3
"""Prepare an lbctl regression from JSON, run load phases, and clean owned resources."""

import argparse
import copy
import json
import math
import os
from pathlib import Path
import re
import secrets
import subprocess
import sys
import urllib.error
import urllib.request
from uuid import uuid4

from regression_traffic import group_request


KINDS = {'provider', 'model', 'pipeline', 'knowledge-base', 'bot'}
REFERENCE = re.compile(r'\$\{([a-zA-Z][a-zA-Z0-9_-]*)\}')


def resolve(value, variables):
    if isinstance(value, dict):
        return {key: resolve(item, variables) for key, item in value.items()}
    if isinstance(value, list):
        return [resolve(item, variables) for item in value]
    if isinstance(value, str):
        return REFERENCE.sub(lambda match: str(variables[match[1]]), value)
    return value


def merge(base, patch):
    result = copy.deepcopy(base)
    for key, value in patch.items():
        result[key] = (
            merge(result[key], value) if isinstance(value, dict) and isinstance(result.get(key), dict) else value
        )
    return result


def contains_fields(actual, expected):
    """Check submitted fields while allowing server-generated defaults."""
    if isinstance(expected, dict):
        return isinstance(actual, dict) and all(
            key in actual and contains_fields(actual[key], value) for key, value in expected.items()
        )
    if isinstance(expected, list):
        return (
            isinstance(actual, list)
            and len(actual) == len(expected)
            and all(contains_fields(left, right) for left, right in zip(actual, expected))
        )
    return actual == expected


def number(value, label, *, minimum=0, integer=False):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f'{label} must be a finite number')
    if value < minimum or (integer and not isinstance(value, int)):
        raise ValueError(f'{label} must be {"an integer " if integer else ""}>= {minimum}')


def validate(profile):
    if not isinstance(profile, dict) or profile.get('version') != 1:
        raise ValueError('profile version must be 1')
    allowed = {
        'version',
        'cli',
        'vars',
        'plugins',
        'resources',
        'cases',
        'phases',
        'observe',
        'cleanup',
        'thresholds',
        'smoke',
        'verification',
        'resource_limits',
    }
    if extra := profile.keys() - allowed:
        raise ValueError(f'unknown profile fields: {sorted(extra)}')
    for field in ('cli', 'vars', 'observe', 'thresholds'):
        if field in profile and not isinstance(profile[field], dict):
            raise ValueError(f'{field} must be an object')
    for field in ('plugins', 'resources', 'cases', 'phases'):
        if field in profile and (
            not isinstance(profile[field], list) or any(not isinstance(item, dict) for item in profile[field])
        ):
            raise ValueError(f'{field} must be an array of objects')
    cli = profile.get('cli', {})
    if not isinstance(cli, dict) or cli.keys() - {'config', 'executable'}:
        raise ValueError('cli accepts config and executable')
    if not isinstance(cli.get('config'), str) or not cli['config']:
        raise ValueError('cli.config must name a Workspace-bound lbctl config')
    variables = {'profile_dir': '.', 'run_dir': '.', 'workspace_uuid': 'workspace', 'group_secret': 'private'}
    supplied = profile.get('vars', {})
    if not isinstance(supplied, dict) or variables.keys() & supplied.keys():
        raise ValueError('vars must be an object without reserved names')
    if any(not isinstance(value, (str, int, float)) or '${' in str(value) for value in supplied.values()):
        raise ValueError('vars values must be scalar literals, without nested references')
    variables.update(supplied)
    for plugin in profile.get('plugins', []):
        if plugin.keys() - {'source', 'file'}:
            raise ValueError('plugins accept source and file')
        if plugin.get('source') not in {'local', 'github', 'marketplace'} or not plugin.get('file'):
            raise ValueError('plugins need source local/github/marketplace and file')
        resolve(plugin, variables)
    for item in profile.get('resources', []):
        if item.keys() - {'id', 'kind', 'type', 'body', 'documents'}:
            raise ValueError('unknown resource field')
        name = item.get('id', '')
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]*', name) or name in variables:
            raise ValueError(f'invalid or duplicate resource id: {name}')
        if item.get('kind') not in KINDS or not isinstance(item.get('body'), dict):
            raise ValueError(f'{name}: resource needs kind and body')
        if 'uuid' in item['body']:
            raise ValueError(f'{name}: resources must create new objects; body.uuid is forbidden')
        if item['kind'] == 'bot' and (
            item['body'].get('adapter') != 'http_bot'
            or not isinstance(item['body'].get('adapter_config'), dict)
            or item['body'].get('adapter_config', {}).get('inbound_secret') != '${group_secret}'
            or not any(
                isinstance(case.get('http_group'), dict) and '${' + name + '}' in case['http_group'].get('url', '')
                for case in profile.get('cases', [])
            )
        ):
            raise ValueError('Bot resources require http_bot, ${group_secret}, and a matching http_group case')
        if item['kind'] == 'model' and item.get('type') not in {'llm', 'embedding', 'rerank'}:
            raise ValueError(f'{name}: model type must be llm/embedding/rerank')
        resolve(item['body'], variables)  # References must point backwards; never guess missing UUIDs.
        variables[name] = name
        documents = item.get('documents', [])
        if not isinstance(documents, list) or any(not isinstance(doc, dict) for doc in documents):
            raise ValueError(f'{name}: documents must be an array of objects')
        for document in documents:
            if item['kind'] != 'knowledge-base' or not document.get('file') or not document.get('parser_plugin_id'):
                raise ValueError(f'{name}: documents need file and parser_plugin_id on a knowledge-base')
            resolve(document, variables)
    verification = profile.get('verification')
    if verification is not None:
        if (
            'smoke' in profile
            or not isinstance(verification, dict)
            or verification.keys() - {'ledger_db', 'timeout_seconds'}
        ):
            raise ValueError('verification is a load-only ledger configuration')
        if not isinstance(verification.get('ledger_db'), str) or not verification['ledger_db']:
            raise ValueError('verification.ledger_db is required')
        resolve(verification, variables)
        number(verification.get('timeout_seconds', 5), 'verification timeout', minimum=0.001)
    cases = profile.get('cases')
    if not isinstance(cases, list) or not cases:
        raise ValueError('cases must be a non-empty array')
    names = set()
    for case in cases:
        if case.keys() - {
            'name',
            'weight',
            'args',
            'expect',
            'body',
            'http_group',
            'box_exec',
            'attachment',
            'stage',
            'mock_requests',
            'fields',
            'forbid',
            'reject_group',
        }:
            raise ValueError('unknown case field')
        if not isinstance(case.get('name'), str) or not case['name'] or case['name'] in names:
            raise ValueError('case names must be non-empty and unique')
        names.add(case['name'])
        if 'stage' in case and (not isinstance(case['stage'], str) or not case['stage']):
            raise ValueError('case stage must be a non-empty string')
        if any(key in case for key in ('mock_requests', 'reject_group')) and 'smoke' not in profile:
            raise ValueError('extended case checks require smoke mode')
        if 'fields' in case and (not isinstance(case['fields'], dict) or not case['fields']):
            raise ValueError('fields must be a non-empty mapping of dotted paths to exact values')
        if 'fields' in case and any(not isinstance(key, str) or not key for key in case['fields']):
            raise ValueError('field paths must be non-empty strings')
        if 'forbid' in case and (
            not isinstance(case['forbid'], list)
            or not case['forbid']
            or any(not isinstance(item, str) or not item for item in case['forbid'])
        ):
            raise ValueError('forbid must contain non-empty response substrings')
        if 'mock_requests' in case:
            requests = case['mock_requests']
            if not isinstance(requests, list) or not requests or not profile.get('smoke', {}).get('mock_records'):
                raise ValueError('mock_requests requires expected requests and smoke.mock_records')
            for request in requests:
                if not isinstance(request, dict) or set(request) != {'model', 'status', 'stream'}:
                    raise ValueError('mock_requests entries require model, status and stream')
                if (
                    not isinstance(request['model'], str)
                    or not request['model']
                    or not isinstance(request['stream'], bool)
                ):
                    raise ValueError('invalid mock request model/stream')
                number(request['status'], 'mock request status', minimum=100, integer=True)
        if 'reject_group' in case and (
            'http_group' not in case
            or case['reject_group'] not in ('missing_signature', 'bad_signature')
            or any(key in case for key in ('box_exec', 'attachment', 'mock_requests'))
        ):
            raise ValueError('reject_group must name a signature rejection on an HTTP group case')
        if 'http_group' in case:
            settings = case['http_group']
            if (
                'args' in case
                or 'body' in case
                or not isinstance(settings, dict)
                or set(settings) != {'url', 'secret_env', 'message'}
                or any(not isinstance(value, str) or not value for value in settings.values())
                or not resolve(settings['url'], variables).startswith(('http://', 'https://'))
                or settings['secret_env'] != 'LANGBOT_QA_GROUP_SECRET'
            ):
                raise ValueError(
                    'http_group needs url, message and secret_env=LANGBOT_QA_GROUP_SECRET; no CLI args/body'
                )
        elif (
            not isinstance(case.get('args'), list)
            or not case['args']
            or not all(isinstance(x, str) for x in case['args'])
        ):
            raise ValueError('case args must be a non-empty string array')
        if not isinstance(case.get('expect'), str) or not case['expect']:
            raise ValueError('case expect must be a non-empty string')
        number(case.get('weight', 1), 'case weight', minimum=1, integer=True)
        resolve(case, variables)
        if 'body' in case and (not isinstance(case['body'], dict) or '--file' in case['args']):
            raise ValueError('case body must be an object and cannot coexist with --file')
        if 'box_exec' in case:
            check = case['box_exec']
            if (
                not isinstance(check, dict)
                or not {'count', 'backend', 'stdout'} <= set(check)
                or check.keys() - {'count', 'backend', 'stdout', 'exit_code', 'stderr'}
            ):
                raise ValueError('box_exec requires count, backend and stdout')
            if 'exit_code' in check:
                number(check['exit_code'], 'box_exec.exit_code', minimum=0, integer=True)
            if 'stderr' in check and not isinstance(check['stderr'], str):
                raise ValueError('box_exec.stderr must be a string')
            number(check['count'], 'box_exec.count', minimum=1, integer=True)
            if any(not isinstance(check[k], str) or not check[k] for k in ('backend', 'stdout')):
                raise ValueError('box_exec backend/stdout must be non-empty strings')
            if 'smoke' not in profile and verification is None:
                raise ValueError('box_exec requires smoke or load verification')
            if 'http_group' not in case and case.get('args', [])[:2] != ['pipeline', 'run']:
                raise ValueError('box_exec requires a Pipeline or group case')
        if 'attachment' in case:
            check = case['attachment']
            if (
                ('smoke' not in profile and verification is None)
                or case.get('args', [])[:2] != ['pipeline', 'run']
                or not isinstance(check, dict)
                or set(check) != {'name', 'text'}
                or any(not isinstance(value, str) or not value for value in check.values())
            ):
                raise ValueError('attachment requires name/text on a smoke Pipeline case')
    if sum(case.get('weight', 1) for case in cases) > 1000:
        raise ValueError('total case weight must be <= 1000')
    smoke = profile.get('smoke')
    if 'smoke' in profile:
        if not isinstance(smoke, dict) or smoke.keys() - {
            'ledger_db',
            'mock_records',
            'timeout_seconds',
            'group_turns',
            'groups_per_case',
            'required_plugins',
        }:
            raise ValueError('invalid smoke settings')
        if not isinstance(smoke.get('ledger_db'), str) or not smoke['ledger_db']:
            raise ValueError('smoke.ledger_db must name the target Core SQLite database')
        if 'mock_records' in smoke and (not isinstance(smoke['mock_records'], str) or not smoke['mock_records']):
            raise ValueError('smoke.mock_records must name the dedicated mock recording file')
        resolve(smoke, variables)
        number(smoke.get('timeout_seconds', 30), 'smoke timeout_seconds', minimum=0.001)
        number(smoke.get('group_turns', 2), 'smoke group_turns', minimum=2, integer=True)
        number(smoke.get('groups_per_case', 2), 'smoke groups_per_case', minimum=2, integer=True)
        if smoke.get('group_turns', 2) > 10 or smoke.get('groups_per_case', 2) > 10:
            raise ValueError('smoke group_turns/groups_per_case must be <= 10')
        required = smoke.get('required_plugins', [])
        if not isinstance(required, list) or any(not isinstance(p, str) or not p for p in required):
            raise ValueError('smoke.required_plugins must be an array of plugin IDs')
        if profile.get('phases') or profile.get('thresholds'):
            raise ValueError('smoke uses fixed case counts; load phases/thresholds are not applicable')
    phases = profile.get('phases', [])
    if not isinstance(phases, list) or (smoke is None and not phases):
        raise ValueError('phases must be a non-empty array')
    names = set()
    for phase in phases:
        name = phase.get('name', '')
        if not re.fullmatch(r'[a-zA-Z][a-zA-Z0-9_-]*', name) or name in names:
            raise ValueError('phase names must be unique simple names')
        names.add(name)
        if phase.keys() - {
            'name',
            'duration_seconds',
            'rps',
            'workers',
            'cooldown_seconds',
            'groups',
            'members_per_group',
        }:
            raise ValueError(f'{name}: unknown phase field')
        number(phase.get('duration_seconds'), 'duration_seconds', minimum=0.001)
        number(phase.get('rps'), 'rps', minimum=0.001)
        number(phase.get('workers'), 'workers', minimum=1, integer=True)
        number(phase.get('cooldown_seconds', 0), 'cooldown_seconds')
        if phase['workers'] > 32:
            raise ValueError('workers must be <= 32')
        number(phase.get('groups', 0), 'groups', integer=True)
        number(phase.get('members_per_group', 3), 'members_per_group', minimum=1, integer=True)
        if phase.get('groups', 0) > 4096 or phase.get('members_per_group', 3) > 1000:
            raise ValueError('groups must be <= 4096 and members_per_group <= 1000')
        group_cases = ['http_group' in case for case in cases]
        if any(group_cases) and (
            not all(group_cases) or phase.get('groups', 0) < sum(case.get('weight', 1) for case in cases)
        ):
            raise ValueError('group phases need only http_group cases and enough groups for all weighted cases')
        if not any(group_cases) and phase.get('groups', 0):
            raise ValueError('groups require http_group cases')
    if profile.get('cleanup', 'on-success') not in {'always', 'on-success', 'never'}:
        raise ValueError('cleanup must be always/on-success/never')
    thresholds = profile.get('thresholds', {})
    if extra := thresholds.keys() - {'min_rps_ratio', 'max_p95_seconds'}:
        raise ValueError(f'unknown thresholds: {sorted(extra)}')
    number(thresholds.get('min_rps_ratio', 0), 'min_rps_ratio')
    if thresholds.get('min_rps_ratio', 0) > 1:
        raise ValueError('min_rps_ratio must be <= 1')
    if not isinstance(thresholds.get('max_p95_seconds', {}), dict):
        raise ValueError('max_p95_seconds must map case names to seconds')
    for name, value in thresholds.get('max_p95_seconds', {}).items():
        if name not in {case['name'] for case in cases}:
            raise ValueError(f'unknown case in max_p95_seconds: {name}')
        number(value, 'max_p95_seconds', minimum=0.001)
    if 'resource_limits' in profile:
        if 'smoke' in profile:
            raise ValueError('resource_limits requires measured load and cooldown phases')
        from regression_analysis import validate_resource_limits

        validate_resource_limits(profile['resource_limits'])
    observed = resolve(profile.get('observe', {}), variables)
    if not isinstance(observed, dict) or observed.keys() - {
        'health',
        'pids',
        'pid_files',
        'containers',
        'box_data_root',
    }:
        raise ValueError('observe accepts health, pids, pid_files, containers, box_data_root')
    if 'box_data_root' in observed and (
        not isinstance(observed['box_data_root'], str) or not observed['box_data_root']
    ):
        raise ValueError('observe.box_data_root must name the deployment Box data directory')
    if not isinstance(observed.get('health'), dict) or not observed['health']:
        raise ValueError('observe.health must contain at least one health endpoint')
    for name, url in observed['health'].items():
        if not isinstance(name, str) or not isinstance(url, str) or not url.startswith(('http://', 'https://')):
            raise ValueError('health endpoints must map names to HTTP(S) URLs')
    for field in ('pids', 'pid_files'):
        if not isinstance(observed.get(field, {}), dict):
            raise ValueError(f'observe.{field} must be an object')
    for pid in observed.get('pids', {}).values():
        number(pid, 'PID', minimum=1, integer=True)
    if profile.get('resource_limits'):
        if profile['resource_limits'].get('containers') and not (
            observed.get('containers') or observed.get('box_data_root')
        ):
            raise ValueError('Container budgets require container names or a Box data root')
        configured = set(observed.get('pids', {})) | set(observed.get('pid_files', {}))
        if set(profile['resource_limits']['targets']) - configured:
            raise ValueError('Resource limit targets must have configured PIDs or PID files')
        for phase in phases:
            limits = profile['resource_limits']
            if (
                phase['duration_seconds'] < limits['warmup_seconds'] + limits['window_seconds']
                or phase.get('cooldown_seconds', 0) < limits['window_seconds']
            ):
                raise ValueError('Phase must cover the configured warmup, resource window and cooldown')
    if not isinstance(observed.get('containers', []), list) or any(
        not isinstance(item, str) or not item for item in observed.get('containers', [])
    ):
        raise ValueError('observe.containers must be an array of container names/IDs')


class Suite:
    def __init__(self, profile, profile_path, output, env=None):
        self.profile = profile
        self.output = output.resolve()
        self.variables = {
            **profile.get('vars', {}),
            'profile_dir': str(profile_path.parent.resolve()),
            'run_dir': str(self.output),
        }
        self.cli = [
            profile.get('cli', {}).get('executable', 'lbctl'),
            '--config',
            self.path(profile['cli']['config']),
            '-o',
            'json',
        ]
        self.owned = []
        self.connection = {}
        self.env = dict(os.environ if env is None else env)
        if any('http_group' in case for case in profile['cases']):
            self.variables['group_secret'] = secrets.token_urlsafe(32)
            self.env['LANGBOT_QA_GROUP_SECRET'] = self.variables['group_secret']
        self.secrets = [
            value for key, value in self.env.items() if ('API_KEY' in key or key == 'LANGBOT_QA_GROUP_SECRET') and value
        ]

    def path(self, value):
        path = Path(resolve(value, self.variables)).expanduser()
        return str(path if path.is_absolute() else Path(self.variables['profile_dir']) / path)

    def write(self, name, value):
        path = self.output / name
        if name == 'request.json':
            private = self.output / '.private'
            private.mkdir(exist_ok=True, mode=0o700)
            path = private / name
        path.write_text(json.dumps(value, ensure_ascii=False, indent=2))
        path.chmod(0o600)
        return str(path)

    def call(self, args, body=None, *, defer_bot_readback=False):
        command = [*self.cli, *args]
        if body is not None:
            command += ['--file', self.write('request.json', body)]
        try:
            result = subprocess.run(command, capture_output=True, text=True, timeout=360, env=self.env)
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError('lbctl timed out; outcome unknown, no automatic retry') from exc
        if result.returncode:
            if defer_bot_readback and args == ['bot', 'create']:
                response = json.loads(result.stdout)
                data = response.get('data', {})
                if (
                    response.get('error', {}).get('type') == 'verification_failed'
                    and data.get('operation') == 'bot.create'
                    and data.get('uuid')
                    and data.get('bot', {}).get('uuid') == data['uuid']
                ):
                    return data
            error = result.stdout + result.stderr
            for secret in self.secrets:
                error = error.replace(secret, '[REDACTED]')
            raise RuntimeError(error[:3000])
        response = json.loads(result.stdout)
        if args == ['whoami']:
            self.connection = response.get('meta') or {}
        return response['data']

    def read_bot(self, bot_uuid):
        """Read full Bot fields using the endpoint and environment credential confirmed by lbctl."""
        source = self.connection.get('credential_source', '')
        key = self.env.get(source.removeprefix('env:')) if source.startswith('env:') else None
        if not key or not self.connection.get('endpoint'):
            raise RuntimeError('Group Bot readback requires environment-backed lbctl credentials')
        self.secrets.append(key)
        request = urllib.request.Request(
            self.connection['endpoint'].rstrip('/') + '/api/v1/platform/bots/' + bot_uuid,
            headers={'Authorization': 'Bearer ' + key, 'X-Workspace-Id': self.variables['workspace_uuid']},
        )
        opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
        try:
            with opener.open(request, timeout=30) as response:
                payload = json.load(response)
        except (urllib.error.URLError, OSError) as exc:
            raise RuntimeError('Bot readback request failed; the creation was not retried') from exc
        if (
            not isinstance(payload, dict)
            or payload.get('code') != 0
            or not isinstance(payload.get('data'), dict)
            or not isinstance(payload['data'].get('bot'), dict)
        ):
            raise RuntimeError('Bot readback did not return a successful Bot resource')
        return payload['data']['bot']

    def journal(self):
        self.write('owned.json', {'workspace_uuid': self.variables['workspace_uuid'], 'resources': self.owned})

    def prepare(self):
        verification = self.profile.get('smoke') or self.profile.get('verification')
        if verification and not Path(self.path(verification['ledger_db'])).is_file():
            raise ValueError('ledger_db must be an existing target Core SQLite database')
        identity = self.call(['whoami'])
        self.variables['workspace_uuid'] = identity['workspace_uuid']
        self.journal()
        for plugin in self.profile.get('plugins', []):
            self.call(['plugin', 'install', plugin['source'], '--file', self.path(plugin['file']), '--wait'])
        if 'smoke' in self.profile or 'verification' in self.profile:
            capabilities = self.call(['capabilities'])
            plugins = self.call(['plugin', 'list'])
            ready = {
                f'{item["author"]}/{item["name"]}'
                for item in plugins['plugins']
                if item.get('enabled') and item.get('status') == 'initialized'
            }
            missing = set(self.profile.get('smoke', {}).get('required_plugins', [])) - ready
            self.write('environment.json', {'identity': identity, 'capabilities': capabilities, 'plugins': plugins})
            if missing:
                raise RuntimeError(f'Required plugins are not initialized: {sorted(missing)}')
        for item in self.profile.get('resources', []):
            kind = item['kind']
            body = resolve(item['body'], self.variables)
            config = body.pop('config', None) if kind == 'pipeline' else None
            args = [kind, 'apply' if kind == 'pipeline' else 'create']
            if kind == 'model':
                args += ['--type', item['type']]
            created = self.call(args, body, defer_bot_readback=True) if kind == 'bot' else self.call(args, body)
            created = created.get('pipeline', created) if kind == 'pipeline' else created
            uuid = created['uuid']
            self.variables[item['id']] = uuid
            self.owned.append({'kind': kind, 'uuid': uuid, **({'type': item['type']} if kind == 'model' else {})})
            self.journal()  # Record ownership before any later configuration or ingestion can fail.
            if kind == 'bot':
                # lbctl 0.3's Bot projection omits event bindings; verify the existing Core API instead.
                actual = self.read_bot(uuid)
                expected = copy.deepcopy(body)
                expected['adapter_config'].pop('inbound_secret')
                if not contains_fields(actual, expected):
                    raise RuntimeError(f'Bot readback differs from submitted non-secret fields: {uuid}')
            if config is not None:
                current = self.call(['pipeline', 'get', uuid])
                current = current.get('pipeline', current)
                self.call(
                    ['pipeline', 'apply'],
                    {
                        'uuid': uuid,
                        'name': current['name'],
                        'description': current['description'],
                        'config': merge(current['config'], config),
                    },
                )
            for document in item.get('documents', []):
                self.call(
                    [
                        'knowledge-base',
                        'ingest',
                        uuid,
                        '--file',
                        self.path(document['file']),
                        '--parser-plugin-id',
                        document['parser_plugin_id'],
                        '--wait',
                    ]
                )
        self.write(
            'resources.json',
            {
                key: value
                for key, value in self.variables.items()
                if key not in self.profile.get('vars', {}) and key != 'group_secret'
            },
        )
        if 'smoke' in self.profile:
            return
        warmups = []
        for case in self.profile['cases']:
            if 'http_group' in case:
                case = resolve(case, self.variables)
                group = f'qa-warmup-{uuid4().hex[:12]}'
                response = group_request(case, group, 'qa-member-000', 1, uuid4().hex, 'none', self.env)
                warmups.append({'case': case['name'], 'output': response})
                self.write('warmup.json', warmups)

    def cleanup(self):
        saved = json.loads((self.output / 'owned.json').read_text())
        identity = self.call(['whoami'])
        if saved['workspace_uuid'] != identity['workspace_uuid']:
            raise RuntimeError('cleanup refused: Workspace differs from owned.json')
        failures = []
        original = saved['resources'].copy()
        for resource in reversed(original):
            args = [resource['kind'], 'delete', resource['uuid'], '--yes']
            if resource['kind'] == 'model':
                args += ['--type', resource['type']]
            try:
                self.call(args)
            except (RuntimeError, ValueError, OSError) as exc:
                failures.append(str(exc))
            else:
                saved['resources'].remove(resource)
                self.write('owned.json', saved)
        if 'smoke' in self.profile or 'verification' in self.profile:
            from regression_smoke import verify_cleanup

            try:
                verify_cleanup(self, [item for item in original if item not in saved['resources']])
            except (RuntimeError, ValueError, OSError, KeyError) as exc:
                failures.append(f'cleanup readback failed: {exc}')
        return failures

    def run(self):
        if 'smoke' in self.profile:
            from regression_smoke import run_smoke

            return run_smoke(self)
        cases = []
        for original in self.profile['cases']:
            case = resolve(original, self.variables)
            if 'body' in case:
                case['args'] += ['--file', self.write(f'case-{len(cases)}.json', case.pop('body'))]
            cases.extend(
                [
                    {
                        key: case[key]
                        for key in (
                            'name',
                            'args',
                            'expect',
                            'http_group',
                            'box_exec',
                            'attachment',
                            'fields',
                            'forbid',
                        )
                        if key in case
                    }
                ]
                * case.get('weight', 1)
            )
        cases_path = self.write('cases.json', cases)
        observed = resolve(self.profile.get('observe', {}), self.variables)
        observe_args = []
        for name, pid in observed.get('pids', {}).items():
            observe_args += ['--pid', f'{name}={int(pid)}']
        for name, path in observed.get('pid_files', {}).items():
            observe_args += ['--pid', f'{name}={int(Path(self.path(path)).read_text().strip())}']
        for name, url in observed.get('health', {}).items():
            observe_args += ['--health', f'{name}={url}']
        for container in observed.get('containers', []):
            observe_args += ['--container', container]
        if observed.get('box_data_root'):
            observe_args += ['--box-data-root', self.path(observed['box_data_root'])]
        if verification := self.profile.get('verification'):
            observe_args += [
                '--ledger-db',
                self.path(verification['ledger_db']),
                '--workspace',
                self.variables['workspace_uuid'],
                '--verification-timeout',
                str(verification.get('timeout_seconds', 5)),
            ]
        results = []
        errors = []
        for phase in self.profile['phases']:
            destination = self.output / phase['name']
            command = [
                sys.executable,
                str(Path(__file__).with_name('regression_traffic.py')),
                '--lbctl',
                self.cli[0],
                '--config',
                self.cli[2],
                '--cases',
                cases_path,
                '--output',
                str(destination),
                '--duration',
                str(phase['duration_seconds']),
                '--rps',
                str(phase['rps']),
                '--workers',
                str(phase['workers']),
                '--cooldown',
                str(phase.get('cooldown_seconds', 0)),
                '--shared-case-sequence',
                '--groups',
                str(phase.get('groups', 0)),
                '--members-per-group',
                str(phase.get('members_per_group', 3)),
                '--group-state',
                str(self.output / 'group-state.json'),
                *observe_args,
            ]
            with (self.output / f'{phase["name"]}.log').open('w') as log:
                result = subprocess.run(command, stdout=log, stderr=subprocess.STDOUT, env=self.env)
            summary = json.loads((destination / 'summary.json').read_text())
            summary['name'] = phase['name']
            summary['achieved_rps'] = (
                summary.get(
                    'successful_requests', sum(row.get('status', {}).get('ok', 0) for row in summary['cases'].values())
                )
                / summary['load_elapsed_seconds']
            )
            results.append(summary)
            if self.profile.get('resource_limits'):
                from regression_analysis import resource_verdict

                summary['resources'] = resource_verdict(destination, self.profile['resource_limits'])
                errors.extend(f'{phase["name"]}: {error}' for error in summary['resources']['errors'])
            if result.returncode:
                errors.append(f'{phase["name"]}: business or health/resource checks failed')
            thresholds = self.profile.get('thresholds', {})
            if summary['achieved_rps'] < phase['rps'] * thresholds.get('min_rps_ratio', 0):
                errors.append(f'{phase["name"]}: achieved RPS below configured threshold')
            for name, maximum in thresholds.get('max_p95_seconds', {}).items():
                p95 = summary['cases'][name]['p95_seconds']
                if p95 is None or p95 > maximum:
                    errors.append(f'{phase["name"]}/{name}: P95 missing or above configured threshold')
        return {'phases': results, 'errors': errors}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('action', choices=('validate', 'run', 'cleanup'))
    parser.add_argument('--profile', required=True, type=Path)
    parser.add_argument('--output', type=Path, help='New run directory; existing run directory for cleanup')
    parser.add_argument('--duration', type=float, help='Override duration_seconds in every phase')
    parser.add_argument('--rps', type=float, help='Override RPS in every phase')
    parser.add_argument('--workers', type=int, help='Override workers in every phase')
    parser.add_argument('--groups', type=int, help='Override group count in every group phase')
    parser.add_argument('--members-per-group', type=int)
    args = parser.parse_args()
    try:
        profile = json.loads(args.profile.read_text())
        if 'smoke' in profile and any(
            getattr(args, flag) is not None for flag in ('duration', 'rps', 'workers', 'groups', 'members_per_group')
        ):
            raise ValueError('Load overrides are not applicable to smoke mode')
        for phase in profile.get('phases', []):
            for flag, field in [
                ('duration', 'duration_seconds'),
                ('rps', 'rps'),
                ('workers', 'workers'),
                ('groups', 'groups'),
                ('members_per_group', 'members_per_group'),
            ]:
                if getattr(args, flag) is not None:
                    phase[field] = getattr(args, flag)
        validate(profile)
        if args.action == 'validate':
            print('Profile valid (no services or resources changed).')
            return
        if args.output is None:
            raise ValueError('--output is required for run/cleanup')
        suite = Suite(profile, args.profile.resolve(), args.output)
        if args.action == 'cleanup':
            errors = suite.cleanup()
            if errors:
                raise RuntimeError('\n'.join(errors))
            return
        args.output.mkdir(parents=True, exist_ok=False, mode=0o700)
        suite.write('profile.json', profile)
        if 'smoke' not in profile:
            from regression_analysis import workload_contract

            suite.write('workload.json', workload_contract(profile, args.profile))
        result = {'phases': [], 'errors': []}
        completed = False
        try:
            suite.prepare()
            result = suite.run()
            completed = True
        except KeyboardInterrupt:
            result['errors'].append('Interrupted; in-flight outcomes may be unknown. Inspect retained resources.')
        except (RuntimeError, ValueError, OSError, KeyError) as exc:
            result['errors'].append(str(exc))
        finally:
            if not completed and not result['errors']:
                result['errors'].append('Run aborted before completion; inspect logs and retained resources.')
            policy = profile.get('cleanup', 'on-success')
            if policy == 'always' or (policy == 'on-success' and not result['errors']):
                if (args.output / 'owned.json').exists():
                    try:
                        result['errors'].extend(suite.cleanup())
                    except (RuntimeError, ValueError, OSError, KeyError) as exc:
                        result['errors'].append(f'cleanup failed: {exc}')
            result['passed'] = not result['errors']
            suite.write('summary.json', result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        if not result['passed']:
            raise SystemExit(1)
    except (RuntimeError, ValueError, OSError, KeyError) as exc:
        parser.exit(1, f'{type(exc).__name__}: {exc}\n')


if __name__ == '__main__':
    main()
