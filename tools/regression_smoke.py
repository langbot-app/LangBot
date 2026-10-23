"""Run finite CLI/group smoke cases with an independent read-only AgentRun oracle."""

from collections import Counter
from contextlib import closing
import base64
import json
from pathlib import Path
import sqlite3
import time
import urllib.error
from uuid import uuid4

from regression_traffic import group_request, read_endpoint_snapshot


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
            or item.get('exit_code') != 0
            or not isinstance(item.get('stdout'), str)
            or expected['stdout'] not in item['stdout']
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


def run_smoke(suite):
    # Imported here because Suite dispatches to this module after profile validation.
    from regression_suite import resolve

    settings = suite.profile['smoke']
    path = Path(suite.path(settings['ledger_db'])).resolve()
    if not path.is_file():
        raise ValueError('smoke.ledger_db must be an existing target Core SQLite database')
    rows, errors, health = [], [], []
    started = time.monotonic()

    def redact(value):
        for secret in suite.secrets:
            value = value.replace(secret, '[REDACTED]')
        return value

    def sample_health(phase):
        for name, url in resolve(suite.profile['observe']['health'], suite.variables).items():
            row = {'phase': phase, 'endpoint': name}
            try:
                row['result'] = read_endpoint_snapshot(url, timeout_seconds=3)
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
            case = resolve(original, suite.variables)
            is_group = 'http_group' in case
            runner = is_group or case.get('args', [])[:2] == ['pipeline', 'run']
            groups = (
                [f'qa-smoke-{uuid4().hex}' for _ in range(settings.get('groups_per_case', 2))] if is_group else [None]
            )
            previous = {group: 'none' for group in groups}
            retired = set()
            for turn in range(1, (settings.get('group_turns', 2) if is_group else 1) + 1):
                for group in groups:
                    row = {'case': case['name'], 'status': 'failed', 'requires_runner': runner}
                    if is_group:
                        row.update(group_id=group, turn=turn, member_id=f'qa-member-{turn % 2:03d}')
                    if group in retired:
                        row.update(status='skipped', error='Earlier turn failed or is unknown; group not retried')
                        rows.append(row)
                        continue
                    before = time.monotonic()
                    after_id = connection.execute('SELECT COALESCE(MAX(id),0) FROM agent_run').fetchone()[0]
                    token = uuid4().hex
                    try:
                        if is_group:
                            data = group_request(
                                case, group, row['member_id'], turn, token, previous[group], suite.env
                            )['data']
                        else:
                            data = suite.call(case['args'], case.get('body'))
                            if case['expect'] not in json.dumps(data, ensure_ascii=False):
                                raise ValueError('Expected business response was not returned')
                        row['output'] = data
                        if runner:
                            if not isinstance(data, dict):
                                raise ValueError('Runner response must be an object')
                            session = data.get('session_id')
                            if not isinstance(session, str) or not session:
                                raise UnresolvedRun('Reply has no session ID for AgentRun reconciliation')
                            run = completed_run(
                                connection,
                                suite.variables['workspace_uuid'],
                                'group_' + session if is_group else session,
                                after_id,
                                settings.get('timeout_seconds', 30),
                            )
                            row['run'] = run
                            row['checks'] = check_run(connection, run, case)
                            if case.get('attachment'):
                                row['checks']['attachment'] = check_attachment(data, case['attachment'])
                        row['status'] = 'passed'
                        previous[group] = token
                    except urllib.error.HTTPError as exc:
                        row.update(
                            status='unknown' if exc.code >= 500 else 'failed', error=f'HTTP {exc.code}; not retried'
                        )
                    except (UnresolvedRun, urllib.error.URLError, TimeoutError) as exc:
                        row.update(status='unknown', error=redact(str(exc)))
                    except (RuntimeError, ValueError, OSError, KeyError, sqlite3.Error) as exc:
                        message = redact(str(exc))
                        row.update(
                            status='unknown'
                            if 'outcome unknown' in message or 'result_unknown' in message
                            else 'failed',
                            error=message,
                        )
                    row['seconds'] = time.monotonic() - before
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
        'phases': [],
        'cases': rows,
        'errors': errors,
        'elapsed_seconds': time.monotonic() - started,
        'status': dict(Counter(row['status'] for row in rows)),
        'case_count': len(suite.profile['cases']),
        'requests': len(rows),
    }
