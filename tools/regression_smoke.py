"""Run finite CLI/group smoke cases with an independent read-only AgentRun oracle."""

from collections import Counter
from contextlib import closing
import base64
import json
import hashlib
import hmac
import os
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.request
from uuid import uuid4

from regression_traffic import group_request, percentile, read_endpoint_snapshot, reconcile_runs
from regression_coverage import checked, check_response
from regression_local_cases import ScenarioUnavailable


class UnresolvedRun(RuntimeError):
    """The request cannot yet be matched to one authoritative terminal run."""


def completed_run(connection, workspace, conversation, after_id, timeout):
    deadline = time.monotonic() + timeout
    while True:
        rows = connection.execute(
            'SELECT run_id, status, status_reason, finished_at FROM agent_run '
            'WHERE workspace_id=? AND conversation_id=? AND id>? ORDER BY id',
            (workspace, conversation, after_id),
        ).fetchall()
        if len(rows) > 1:
            raise UnresolvedRun('More than one AgentRun matches this request')
        if rows and (rows[0]['finished_at'] or rows[0]['status'] in {'completed', 'failed', 'timeout', 'cancelled'}):
            return dict(rows[0])
        if time.monotonic() >= deadline:
            raise UnresolvedRun('No unique terminal AgentRun before the observation deadline; not retried')
        time.sleep(0.1)


def check_run(connection, run, case):
    if run['status'] != 'completed':
        raise ValueError(f'AgentRun {run["run_id"]} ended as {run["status"]}: {run["status_reason"]}')
    events = [
        (kind, json.loads(data or '{}'))
        for kind, data in connection.execute(
            'SELECT type, data_json FROM agent_run_event WHERE run_id=? ORDER BY sequence', (run['run_id'],)
        )
    ]
    if any(not isinstance(data, dict) for _kind, data in events):
        raise ValueError('AgentRun event payload must be an object')
    if not any(kind == 'run.completed' for kind, _data in events):
        raise ValueError('Completed AgentRun is missing its persisted run.completed event')
    checks = {'terminal_event': True}
    if expected := case.get('box_exec'):
        calls = [
            data.get('result', {})
            for kind, data in events
            if kind == 'tool.call.completed' and data.get('tool_name') == 'exec'
        ]
        if len(calls) != expected['count'] or any(
            not isinstance(item, dict)
            or item.get('backend') != expected['backend']
            or item.get('exit_code') != expected.get('exit_code', 0)
            or not isinstance(item.get('stdout'), str)
            or expected['stdout'] not in item['stdout']
            or ('stderr' in expected and expected['stderr'] not in str(item.get('stderr', '')))
            for item in calls
        ):
            raise ValueError('Box execution count/backend/exit code/output did not match the oracle')
        checks['box_exec'] = {'calls': len(calls), 'backend': expected['backend'], 'output_matched': True}
    return checks


def check_attachment(data, expected):
    replies = data.get('replies')
    if not isinstance(replies, list) or any(
        not isinstance(reply, dict)
        or not isinstance(reply.get('message_chain'), list)
        or any(not isinstance(part, dict) for part in reply['message_chain'])
        for reply in replies
    ):
        raise ValueError('Malformed file delivery response')
    attachments = [part for reply in replies for part in reply.get('message_chain', []) if part.get('type') == 'File']
    if len(attachments) != 1 or attachments[0].get('name') != expected['name']:
        raise ValueError('Expected exactly one file attachment with the configured name')
    encoded = attachments[0].get('base64')
    if not isinstance(encoded, str):
        raise ValueError('Attachment must contain base64 bytes')
    content = base64.b64decode(encoded, validate=True)
    if content != expected['text'].encode('utf-8'):
        raise ValueError('Exported attachment bytes differ from the expected fixture')
    return {'name': expected['name'], 'bytes': len(content), 'content_matched': True}


def check_fields(data, expected):
    for path, value in expected.items():
        actual = data
        try:
            for key in path.split('.'):
                actual = actual[int(key)] if isinstance(actual, list) else actual[key]
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            raise ValueError(f'Response field {path} is missing or malformed') from exc
        if actual != value:
            raise ValueError(f'Response field {path} differs from the expected value')
    return expected


def check_mock_requests(path, offset, expected, *, timeout=3):
    deadline = time.monotonic() + timeout
    while True:
        with path.open('rb') as stream:
            stream.seek(offset)
            lines = stream.read().splitlines()
        records = [json.loads(line) for line in lines]
        actual = [
            {'model': row['request']['model'], 'status': row['status'], 'stream': row['request'].get('stream', False)}
            for row in records
            if row['path'] == '/v1/chat/completions'
        ]
        if len(actual) >= len(expected) or time.monotonic() >= deadline:
            if actual != expected:
                raise ValueError(f'Model request sequence differs: expected {expected}, got {actual}')
            return actual
        time.sleep(0.05)


def signed_headers(body, secret, timestamp=None):
    timestamp = str(int(time.time()) if timestamp is None else timestamp)
    signature = hmac.new(secret.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    return {'Content-Type': 'application/json', 'X-LB-Timestamp': timestamp, 'X-LB-Signature': 'sha256=' + signature}


def rejected_group(case, group, env=None, *, timeout=10):
    settings = case['http_group']
    env = os.environ if env is None else env
    kind = case['reject_group']
    payload = {
        'session_id': group,
        'session_type': 'group',
        'sender': {'id': 'qa-rejected'},
        'message': [{'type': 'Plain', 'text': settings['message']}],
    }
    if kind == 'missing_session':
        payload.pop('session_id')
    if kind == 'invalid_message':
        payload['message'] = 'not a message chain'
    body = json.dumps(payload).encode()
    if kind == 'invalid_json':
        body = b'{'
    if kind == 'invalid_object':
        body = b'[]'
    timestamp = {
        'expired_signature': int(time.time()) - 600,
        'future_signature': int(time.time()) + 600,
        'bad_timestamp': 'invalid',
    }.get(kind)
    headers = {'Content-Type': 'application/json'}
    if kind == 'bad_signature':
        headers.update({'X-LB-Timestamp': str(int(time.time())), 'X-LB-Signature': 'sha256=' + '0' * 64})
    elif kind != 'missing_signature':
        headers = signed_headers(body, env[settings['secret_env']], timestamp)
    if kind == 'tampered_body':
        body += b' '
    request = urllib.request.Request(settings['url'], headers=headers, data=body)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout):
            raise ValueError('Invalid bot ingress was accepted')
    except urllib.error.HTTPError as exc:
        payload = json.load(exc)
        return {'http_status': exc.code, 'code': payload.get('code')}


def api_probe(case, *, timeout=10):
    probe = case['http_probe']
    headers = {} if probe['auth'] == 'missing' else {'X-API-Key': 'qa-intentionally-invalid'}
    request = urllib.request.Request(probe['url'], headers=headers)
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        response = opener.open(request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        response = exc
    with response:
        return {'http_status': response.status, 'body': json.load(response)}


def reset_group(case, group, env, *, timeout=10):
    body = json.dumps({'session_id': group, 'session_type': 'group'}).encode()
    settings = case['http_group']
    request = urllib.request.Request(
        settings['url'].removesuffix('/sync') + '/reset',
        data=body,
        headers=signed_headers(body, env[settings['secret_env']]),
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    try:
        with opener.open(request, timeout=timeout) as response:
            result = json.load(response)
    except urllib.error.HTTPError as exc:
        # A received error response violates reset's success contract; do not retry it.
        raise ValueError(f'Reset returned HTTP {exc.code}; expected 200') from exc
    check_fields(result, {'code': 0, 'data.session_id': group, 'data.removed': True})
    return result


def verify_cleanup(suite, deleted):
    checks = []
    for kind, model_type in dict.fromkeys((item['kind'], item.get('type')) for item in deleted):
        args = [kind, 'list'] + (['--type', model_type] if model_type else [])
        data = suite.call(args)
        key = {
            'provider': 'providers',
            'model': 'models',
            'pipeline': 'pipelines',
            'bot': 'bots',
            'knowledge-base': 'bases',
        }[kind]
        items = data.get(key) if isinstance(data, dict) else None
        if not isinstance(items, list) or any(
            not isinstance(item, dict) or not isinstance(item.get('uuid'), str) for item in items
        ):
            raise ValueError(f'Malformed {kind} list response during cleanup verification')
        visible = {item['uuid'] for item in items}
        expected_absent = {item['uuid'] for item in deleted if item['kind'] == kind and item.get('type') == model_type}
        remaining = sorted(expected_absent & visible)
        checks.append({'kind': kind, 'type': model_type, 'deleted_count': len(expected_absent), 'remaining': remaining})
    suite.write('cleanup-checks.json', checks)
    if any(row['remaining'] for row in checks):
        raise ValueError('Deleted resources remain visible in CLI list readback')


def run_cycle(suite, rows, health, cycle):
    # Imported here because Suite dispatches to this module after profile validation.
    from regression_suite import resolve

    settings = suite.profile['smoke']
    path = Path(suite.path(settings['ledger_db'])).resolve()
    if not path.is_file():
        raise ValueError('smoke.ledger_db must be an existing target Core SQLite database')
    mock_path = Path(suite.path(settings['mock_records'])) if settings.get('mock_records') else None
    errors = []
    initial_count = len(rows)
    complete = True
    execution = getattr(suite, 'execution', None)
    started = time.monotonic()

    def redact(value):
        for secret in suite.secrets:
            value = value.replace(secret, '[REDACTED]')
        return value

    def sample_health(phase):
        for name, url in resolve(suite.profile['observe']['health'], suite.variables).items():
            row = {'phase': phase, 'cycle': cycle, 'endpoint': name}
            try:
                row['result'] = read_endpoint_snapshot(url, timeout_seconds=suite.timeout(3))
            except (RuntimeError, OSError, ValueError) as exc:
                row['error'] = redact(str(exc))
                errors.append(f'{phase}/{name}: health check failed')
            health.append(row)
        suite.write('health.json', health)

    sample_health('before')
    # shortcut: local SQLite only; use a terminal-run API when lbctl exposes one.
    with closing(sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=5)) as connection:
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        for original in suite.profile['cases']:
            if execution and not execution.admitting():
                complete = False
                break
            case = resolve(original, suite.variables)
            is_group = 'http_group' in case
            rejected = 'reject_group' in case
            runner = not rejected and (is_group or case.get('args', [])[:2] == ['pipeline', 'run'])
            groups = (
                [f'qa-smoke-{uuid4().hex}' for _ in range(settings.get('groups_per_case', 2))]
                if is_group and not rejected
                else [f'qa-smoke-{uuid4().hex}' if rejected else None]
            )
            previous = {group: 'none' for group in groups}
            retired = set()
            reset_done = False
            history_turns = {group: 0 for group in groups}
            for turn in range(1, (settings.get('group_turns', 2) if is_group and not rejected else 1) + 1):
                for group_index, group in enumerate(groups):
                    if execution and not execution.admitting():
                        complete = False
                        break
                    row = {
                        'case': case['name'],
                        'cycle': cycle,
                        'stage': case.get('stage', 'execution'),
                        'status': 'failed',
                        'requires_runner': runner,
                    }
                    if is_group:
                        row.update(
                            group_id=group, turn=turn, group_index=group_index, member_id=f'qa-member-{turn % 2:03d}'
                        )
                    if case.get('reset_group') and group_index == 1 and turn >= 2 and not reset_done:
                        row.update(status='skipped', error='Peer reset did not complete; isolation cannot be checked')
                        rows.append(row)
                        continue
                    if group in retired:
                        row.update(status='skipped', error='Earlier turn failed or is unknown; group not retried')
                        rows.append(row)
                        continue
                    before = time.monotonic()
                    after_id = connection.execute('SELECT COALESCE(MAX(id),0) FROM agent_run').fetchone()[0]
                    row['after_id'] = after_id
                    if runner and is_group:
                        row['conversation_id'] = 'group_' + group
                    token = uuid4().hex
                    offset = mock_path.stat().st_size if case.get('mock_requests') and mock_path.exists() else 0
                    try:
                        if 'scenario' in case:
                            from regression_local_cases import run_case

                            data = run_case(suite, case, row)
                        elif rejected:
                            data = checked(
                                row,
                                'response',
                                lambda: rejected_group(case, group, suite.env, timeout=suite.timeout(10)),
                            )
                            count = connection.execute(
                                'SELECT COUNT(*) FROM agent_run WHERE workspace_id=? AND id>?',
                                (suite.variables['workspace_uuid'], after_id),
                            ).fetchone()[0]
                            checked(row, 'no_run', lambda: check_fields({'runs': count}, {'runs': 0}))
                        elif is_group:
                            if case.get('reset_group') and turn == 2 and group_index == 0:
                                checked(
                                    row, 'reset', lambda: reset_group(case, group, suite.env, timeout=suite.timeout(10))
                                )
                                reset_done = True
                                history_turns[group] = 0
                                previous[group] = 'none'
                            data = checked(
                                row,
                                'response',
                                lambda: group_request(
                                    case,
                                    group,
                                    row['member_id'],
                                    history_turns[group] + 1,
                                    token,
                                    previous[group],
                                    suite.env,
                                    timeout=suite.timeout(90),
                                ),
                            )['data']
                        elif 'http_probe' in case:
                            data = api_probe(case, timeout=suite.timeout(10))
                            checked(row, 'response', lambda: check_response(data, case['expect']))
                        else:
                            data = suite.call(case['args'], case.get('body'))
                            checked(row, 'response', lambda: check_response(data, case['expect']))
                        row['output'] = data
                        if case.get('forbid'):
                            checked(row, 'isolation', lambda: check_response(data, case['expect'], case['forbid']))
                        row.setdefault('checks', {})
                        if case.get('fields'):
                            row['checks']['fields'] = checked(row, 'fields', lambda: check_fields(data, case['fields']))
                        if case.get('attachment'):
                            row['checks']['attachment'] = checked(
                                row, 'attachment', lambda: check_attachment(data, case['attachment'])
                            )
                        if case.get('mock_requests'):
                            row['checks']['mock_requests'] = checked(
                                row,
                                'model_sequence',
                                lambda: check_mock_requests(
                                    mock_path, offset, case['mock_requests'], timeout=suite.timeout(3)
                                ),
                            )
                        if runner:
                            if not isinstance(data, dict):
                                raise ValueError('Runner response must be an object')
                            session = data.get('session_id')
                            if not isinstance(session, str) or not session:
                                raise UnresolvedRun('Reply has no session ID for AgentRun reconciliation')
                            row['conversation_id'] = 'group_' + session if is_group else session
                            run = completed_run(
                                connection,
                                suite.variables['workspace_uuid'],
                                'group_' + session if is_group else session,
                                after_id,
                                suite.timeout(settings.get('timeout_seconds', 30)),
                            )
                            row['run'] = run
                            row['checks'].update(checked(row, 'ledger', lambda: check_run(connection, run, case)))
                        row['status'] = 'passed'
                        previous[group] = token
                        history_turns[group] += 1
                    except ScenarioUnavailable as exc:
                        row.update(status='skipped', error=redact(str(exc)))
                    except urllib.error.HTTPError as exc:
                        row.update(
                            status='unknown' if exc.code >= 500 else 'failed', error=f'HTTP {exc.code}; not retried'
                        )
                    except TimeoutError as exc:
                        row.update(status='unknown', timed_out=True, error=redact(str(exc)))
                    except (UnresolvedRun, urllib.error.URLError, ConnectionError) as exc:
                        row.update(status='unknown', error=redact(str(exc)))
                        if isinstance(getattr(exc, 'reason', None), TimeoutError):
                            row['timed_out'] = True
                    except (RuntimeError, ValueError, OSError, KeyError, IndexError, sqlite3.Error) as exc:
                        message = redact(str(exc))
                        row.update(
                            status='unknown'
                            if 'outcome unknown' in message or 'result_unknown' in message
                            else 'failed',
                            error=message,
                        )
                        if 'timed out' in message:
                            row['timed_out'] = True
                    row['seconds'] = time.monotonic() - before
                    for error in row.get('cleanup_errors', []):
                        errors.append(f'{case["name"]}: cleanup failed: {redact(str(error))}')
                    if row['status'] != 'passed':
                        errors.append(f'{case["name"]}: {row["status"]}: {row["error"]}')
                        if is_group:
                            retired.add(group)
                    rows.append(row)
                    suite.write('cases.json', rows)
                    suite.write(
                        'progress.json',
                        {'completed_requests': len(rows), 'status': dict(Counter(x['status'] for x in rows))},
                    )
        suite.write('cases.json', rows)
    sample_health('after')
    return {
        'mode': 'smoke',
        'cycle_complete': complete,
        'cycle_requests': len(rows) - initial_count,
        'phases': [],
        'cases': rows,
        'errors': errors,
        'elapsed_seconds': time.monotonic() - started,
        'status': dict(Counter(row['status'] for row in rows)),
        'stages': {
            stage: dict(Counter(row['status'] for row in rows if row['stage'] == stage))
            for stage in dict.fromkeys(row['stage'] for row in rows)
        },
        'case_count': len(suite.profile['cases']),
        'requests': len(rows),
    }


def run_smoke(suite):
    rows, health, errors, cycles = [], [], [], []
    execution = getattr(suite, 'execution', None)
    while True:
        cycle = len(cycles) + 1
        if execution:
            execution.mark(f'cycle-{cycle}')
        result = run_cycle(suite, rows, health, cycle)
        errors.extend(result['errors'])
        cycles.append(
            {
                'cycle': cycle,
                'requests': result['cycle_requests'],
                'complete': result['cycle_complete'],
                'elapsed_seconds': result['elapsed_seconds'],
                'status': dict(Counter(row['status'] for row in rows if row['cycle'] == cycle)),
            }
        )
        suite.write('cycles.json', cycles)
        if not execution or not execution.admitting() or any(row['status'] in ('unknown', 'skipped') for row in rows):
            break
    result['errors'] = errors
    result['cycles'] = cycles
    result['first_pass_complete'] = cycles[0]['complete']
    result['incomplete'] = [
        f'{row["case"]}: {row["status"]}: {row["error"]}'
        for row in rows
        if row['status'] in ('unknown', 'skipped') and not row.get('timed_out')
    ]
    if not result['first_pass_complete']:
        error = 'Required first pass did not finish before the admission deadline'
        result['errors'].append(error)
        result['incomplete'].append(error)
    result['elapsed_seconds'] = sum(cycle['elapsed_seconds'] for cycle in cycles)
    result['performance_mode'] = 'observe'
    result['observations'] = {
        'successful_requests_per_second': sum(row['status'] == 'passed' for row in rows)
        / max(result['elapsed_seconds'], 0.000001),
        'step_p95_seconds': {
            name: percentile([row['seconds'] for row in rows if row['case'] == name and 'seconds' in row], 0.95)
            for name in dict.fromkeys(row['case'] for row in rows)
        },
    }
    executed = scenario_run_rows(rows)
    result['test_data'] = {
        'observed_conversations': len({row['conversation_id'] for row in executed if 'conversation_id' in row}),
        'observed_agent_runs': len({row['run']['run_id'] for row in executed if 'run' in row}),
        'group_sessions': len({row['group_id'] for row in executed if 'group_id' in row}),
        'owned_api_resources': len(suite.owned),
    }
    reconcile_scenario_runs(suite, result)
    return result


def scenario_run_rows(rows):
    executed = [row for row in rows if row.get('requires_runner') and 'after_id' in row]
    for row in rows:
        for run in row.get('scenario_runs', []):
            executed.append(
                {
                    'after_id': row['after_id'],
                    'conversation_id': run['conversation_id'],
                    'run': {'run_id': run['run_id']},
                    'expected_status': run['expected_status'],
                }
            )
    return executed


def reconcile_scenario_runs(suite, result, *, key='ledger'):
    """Recheck the originally observed conversations without expanding run ownership."""
    executed = scenario_run_rows(result.get('cases', []))
    if not executed:
        return
    try:
        result[key] = reconcile_runs(
            suite.path(suite.profile['smoke']['ledger_db']),
            suite.variables['workspace_uuid'],
            min(row['after_id'] for row in executed),
            {row['conversation_id'] for row in executed if 'conversation_id' in row},
            {row['run']['run_id'] for row in executed if 'run' in row},
            expected_statuses={
                row['run']['run_id']: row.get('expected_status', 'completed') for row in executed if 'run' in row
            },
        )
    except (OSError, sqlite3.Error) as exc:
        error = f'Scenario {key} evidence unavailable: {exc}'
        result['errors'].append(error)
        result.setdefault('incomplete', []).append(error)
        return
    if not result[key]['matched']:
        error = f'Scenario {key} found extra, missing or unexpected AgentRun states'
        result['errors'].append(error)
