"""Run finite CLI/group smoke cases with an independent read-only AgentRun oracle."""

from collections import Counter
from contextlib import closing
import json
import os
from pathlib import Path
import sqlite3
import time
import urllib.error
import urllib.request
from uuid import uuid4

from tools.entrypoints.regression_traffic import percentile
from tools.regression.observations import read_endpoint_snapshot
from tools.regression.evidence import check_attachment, check_fields, check_response, checked
from tools.regression.http_bot import group_request, signed_headers
from tools.regression.regression_local_cases import ScenarioUnavailable
from tools.regression.run_ledger import (
    UnresolvedRun,
    check_run,
    completed_run,
    connect_readonly,
    high_water_mark,
    reconcile_scenario_runs,
    scenario_run_rows,
)


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


def run_cycle(suite, rows, health, cycle):
    # Imported here because Suite dispatches to this module after profile validation.
    from tools.entrypoints.regression_suite import resolve

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
    with closing(connect_readonly(path)) as connection:
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
                    after_id = high_water_mark(connection)
                    row['after_id'] = after_id
                    if runner and is_group:
                        row['conversation_id'] = 'group_' + group
                    token = uuid4().hex
                    offset = mock_path.stat().st_size if case.get('mock_requests') and mock_path.exists() else 0
                    try:
                        if 'scenario' in case:
                            from tools.regression.regression_local_cases import run_case

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
