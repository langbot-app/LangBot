"""Read-only AgentRun evidence, shared by finite and repeating workloads."""

from contextlib import closing
import json
from pathlib import Path
import sqlite3
import time


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


def connect_readonly(path, *, timeout=5):
    """Open the SQLite ledger without creating a missing file or allowing writes."""
    return sqlite3.connect(Path(path).resolve().as_uri() + '?mode=ro', uri=True, timeout=timeout)


def high_water_mark(connection):
    return connection.execute('SELECT COALESCE(MAX(id),0) FROM agent_run').fetchone()[0]


def run_event_rows(connection, run_id, event_type=None):
    query = 'SELECT type, data_json FROM agent_run_event WHERE run_id=?'
    params = (run_id,)
    if event_type is not None:
        query += ' AND type=?'
        params += (event_type,)
    return connection.execute(query + ' ORDER BY sequence', params)


def ledger(suite):
    path = Path(suite.path(suite.profile['smoke']['ledger_db'])).resolve()
    connection = connect_readonly(path, timeout=min(5, suite.timeout(5)))
    connection.row_factory = sqlite3.Row
    return connection


def after_id(suite):
    with closing(ledger(suite)) as connection:
        return high_water_mark(connection)


def completed(suite, row, session_id, after, expected='completed'):
    with closing(ledger(suite)) as connection:
        run = completed_run(
            connection, suite.variables['workspace_uuid'], 'group_' + session_id, after, suite.timeout(20)
        )
    record_run(suite, row, run['run_id'], expected)
    return run


def record_run(suite, row, run_id, expected_status):
    """Register exact run ownership for the independent final ledger check."""
    if expected_status not in {'completed', 'failed', 'cancelled', 'timeout'}:
        raise ValueError('Expected Run status must be terminal')
    path = Path(suite.path(suite.profile['smoke']['ledger_db'])).resolve()
    deadline = time.monotonic() + suite.timeout(30)
    with closing(connect_readonly(path)) as connection:
        connection.row_factory = sqlite3.Row
        while True:
            run = connection.execute(
                'SELECT run_id, conversation_id, status, finished_at FROM agent_run '
                'WHERE workspace_id=? AND run_id=? AND id>?',
                (suite.variables['workspace_uuid'], run_id, row['after_id']),
            ).fetchone()
            if run and run['finished_at']:
                observed = dict(run)
                observed.update(expected_status=expected_status, after_id=row['after_id'])
                row.setdefault('scenario_runs', []).append(observed)
                if run['status'] != expected_status:
                    raise ValueError(f'Run ended as {run["status"]}; expected {expected_status}')
                return observed
            if time.monotonic() >= deadline:
                raise TimeoutError('Scenario Run did not reach a persisted terminal state')
            time.sleep(0.1)


def check_run(connection, run, case):
    if run['status'] != 'completed':
        raise ValueError(f'AgentRun {run["run_id"]} ended as {run["status"]}: {run["status_reason"]}')
    events = [(kind, json.loads(data or '{}')) for kind, data in run_event_rows(connection, run['run_id'])]
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


def reconcile_runs(path, workspace, after_id, conversations, expected_ids, *, expected_statuses=None):
    """Catch delayed extra or nonterminal runs after request-level verification."""
    actual, unfinished = set(), []
    expected_statuses = expected_statuses or {}
    if set(expected_statuses) - set(expected_ids) or any(
        status not in {'completed', 'failed', 'cancelled', 'timeout'} for status in expected_statuses.values()
    ):
        raise ValueError('Expected statuses must name owned runs and terminal states')
    connection = connect_readonly(path)
    try:
        values = sorted(conversations)
        for start in range(0, len(values), 500):
            part = values[start : start + 500]
            query = (
                'SELECT run_id, status FROM agent_run WHERE workspace_id=? AND id>? '
                'AND conversation_id IN (' + ','.join('?' for _ in part) + ')'
            )
            for run_id, status in connection.execute(query, [workspace, after_id, *part]):
                actual.add(run_id)
                if status != expected_statuses.get(run_id, 'completed'):
                    unfinished.append(run_id)
    finally:
        connection.close()
    return {
        'matched': actual == set(expected_ids) and not unfinished,
        'expected_count': len(expected_ids),
        'actual_count': len(actual),
        'extra': sorted(actual - set(expected_ids)),
        'missing': sorted(set(expected_ids) - actual),
        'not_completed': unfinished,
    }


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
