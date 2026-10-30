"""Optional lifecycle checks using real asynchronous HTTP Bot callbacks."""

from contextlib import closing
import copy
import hashlib
import hmac
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
from pathlib import Path
import secrets
import sqlite3
import threading
import time

from regression_coverage import checked
from regression_local_cases import ScenarioUnavailable, api, record_run, require

GROUP = 'lifecycle'
CASE_NAMES = {'callback_retry_identity'}


def add_cases(profile):
    profile['cases'].append(
        {
            'name': 'callback_retry_identity',
            'scenario': 'callback_retry_identity',
            'stage': 'delivery',
            'expect': 'LANGBOT_CALLBACK_RETRY_OK',
        }
    )


def signature(secret, body, timestamp):
    return 'sha256=' + hmac.new(secret.encode(), timestamp.encode() + b'.' + body, hashlib.sha256).hexdigest()


def ledger(suite):
    path = Path(suite.path(suite.profile['smoke']['ledger_db'])).resolve()
    connection = sqlite3.connect(path.as_uri() + '?mode=ro', uri=True, timeout=min(5, suite.timeout(5)))
    connection.row_factory = sqlite3.Row
    return connection


def after_id(suite):
    with closing(ledger(suite)) as connection:
        return connection.execute('SELECT COALESCE(MAX(id),0) FROM agent_run').fetchone()[0]


def completed(suite, row, session_id, after, expected='completed'):
    from regression_smoke import completed_run

    with closing(ledger(suite)) as connection:
        run = completed_run(
            connection, suite.variables['workspace_uuid'], 'group_' + session_id, after, suite.timeout(20)
        )
    record_run(suite, row, run['run_id'], expected)
    return run


class CallbackReceiver:
    """Reject the first callback once, then retain receipts for independent checks."""

    def __init__(self, secret):
        self.records = []
        self.condition = threading.Condition()
        receiver = self

        class Handler(BaseHTTPRequestHandler):
            def setup(self):
                super().setup()
                self.connection.settimeout(5)

            def do_POST(self):
                try:
                    size = int(self.headers.get('Content-Length', '0'))
                    require(0 < size <= 1024 * 1024, 'Invalid callback body size')
                    body = self.rfile.read(size)
                    payload = json.loads(body)
                    timestamp = self.headers.get('X-LB-Timestamp', '')
                    require(abs(time.time() - int(timestamp)) <= 300, 'Invalid callback timestamp')
                    require(
                        hmac.compare_digest(self.headers.get('X-LB-Signature', ''), signature(secret, body, timestamp)),
                        'Invalid callback signature',
                    )
                    require(isinstance(payload, dict), 'Callback must be an object')
                    record = {'body': body, 'payload': payload}
                    with receiver.condition:
                        status = 503 if not receiver.records else 200
                except (ValueError, OSError) as exc:
                    record, status = {'error': str(exc)}, 400
                self.send_response(status)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{}')
                self.wfile.flush()
                with receiver.condition:
                    receiver.records.append({**record, 'status': status})
                    receiver.condition.notify_all()

            def log_message(self, *args):
                pass

        self.server = ThreadingHTTPServer(('127.0.0.1', 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, kwargs={'poll_interval': 0.05})

    def __enter__(self):
        self.thread.start()
        return self

    def __exit__(self, *args):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=5)
        require(not self.thread.is_alive(), 'Callback receiver did not stop')

    @property
    def url(self):
        return f'http://127.0.0.1:{self.server.server_port}/callback'

    def wait_final(self, reply_to, timeout):
        deadline = time.monotonic() + timeout
        with self.condition:
            while True:
                errors = [item['error'] for item in self.records if 'error' in item]
                require(not errors, f'Callback receiver rejected delivery: {errors}')
                records = [item for item in self.records if item['payload'].get('reply_to') == reply_to]
                if any(item['status'] == 200 and item['payload'].get('is_final') is True for item in records):
                    return list(records)
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError('No successful final callback before the observation deadline')
                self.condition.wait(remaining)


def verify_delivery(records, session_id, *, retried):
    require(bool(records), 'No callback receipts')
    statuses = [item['status'] for item in records]
    if retried:
        require(len(records) >= 2 and [item['status'] for item in records[:2]] == [503, 200], '5xx was not retried')
        require(records[0]['body'] == records[1]['body'], 'Retry changed callback body or identity')
        records = records[1:]
    require(all(item['status'] == 200 for item in records), 'Unexpected callback failure')
    payloads = [item['payload'] for item in records]
    require(all(item.get('session_id') == session_id for item in payloads), 'Callback changed session identity')
    require([item.get('sequence') for item in payloads] == list(range(1, len(payloads) + 1)), 'Callback order changed')
    require(
        [item.get('is_final') for item in payloads] == [False] * (len(payloads) - 1) + [True],
        'Callback final marker is missing or duplicated',
    )
    parts = [part for item in payloads for part in item.get('message', [])]
    require(all(isinstance(part, dict) for part in parts), 'Callback message has invalid components')
    text = ''.join(str(part.get('text', '')) for part in parts if part.get('type') == 'Plain')
    require('LANGBOT_CHAT_OK' in text, 'Callback did not deliver the expected business reply')
    return {
        'parts': len(payloads),
        'finals': 1,
        'response_statuses': statuses,
        'body_sha256': [hashlib.sha256(item['body']).hexdigest() for item in records],
    }


def run_case(suite, case, row):
    require(case['scenario'] in CASE_NAMES, 'Unknown lifecycle scenario')
    secret = secrets.token_urlsafe(32)
    suite.secrets.append(secret)
    bot_uuid, primary_error = None, None
    with CallbackReceiver(secret) as receiver:
        try:
            status, response = api(
                suite,
                'POST',
                '/api/v1/platform/bots',
                {
                    'name': 'QA callback retry ' + secrets.token_hex(4),
                    'adapter': 'http_bot',
                    'enable': True,
                    'adapter_config': {
                        'signature_required': True,
                        'inbound_secret': secret,
                        'outbound_secret': secret,
                        'callback_url': receiver.url,
                        'callback_timeout': 2,
                        'callback_max_retries': 1,
                        'default_session_type': 'group',
                    },
                    'event_bindings': [
                        {
                            'event_pattern': 'message.received',
                            'target_type': 'pipeline',
                            'target_uuid': suite.variables['chat_pipeline'],
                            'enabled': True,
                            'filters': [],
                        }
                    ],
                    'plugin_processors': [],
                },
            )
            require(status == 200 and response.get('code') == 0, 'Callback Bot creation failed')
            bot_uuid = response['data']['uuid']
            messages = []
            for index in range(2):
                session_id = 'qa-callback-' + secrets.token_hex(8)
                body = {
                    'session_id': session_id,
                    'session_type': 'group',
                    'sender': {'id': 'qa-callback-sender'},
                    'message': [{'type': 'Plain', 'text': 'ai Run the normal QA scenario'}],
                }
                stamp = str(int(time.time()))
                status, accepted = api(
                    suite,
                    'POST',
                    f'/bots/{bot_uuid}',
                    body,
                    headers={
                        'X-LB-Timestamp': stamp,
                        'X-LB-Signature': signature(secret, json.dumps(body).encode(), stamp),
                        'X-LB-Idempotency-Key': secrets.token_hex(16),
                    },
                )
                require(status == 202 and accepted.get('code') == 0, 'Asynchronous ingress was not accepted')
                message_id = accepted['data']['accepted_message_id']
                name = 'callback_retry' if index == 0 else 'callback_followup'
                checked(
                    row,
                    name,
                    lambda: verify_delivery(
                        receiver.wait_final(message_id, suite.timeout(30)), session_id, retried=index == 0
                    ),
                )
                messages.append((message_id, session_id, name))
            with receiver.condition:
                receipts = list(receiver.records)
            deliveries = []
            for index, (message_id, session_id, name) in enumerate(messages):
                records = [item for item in receipts if item.get('payload', {}).get('reply_to') == message_id]
                deliveries.append(checked(row, name, lambda: verify_delivery(records, session_id, retried=index == 0)))
                completed(suite, row, session_id, row['after_id'])
            return {'result': 'LANGBOT_CALLBACK_RETRY_OK', 'deliveries': deliveries}
        except BaseException as exc:
            primary_error = exc
            raise
        finally:
            if bot_uuid is not None:

                def cleanup():
                    status, response = api(suite, 'DELETE', f'/api/v1/platform/bots/{bot_uuid}')
                    require(status == 200 and response.get('code') == 0, 'Callback Bot deletion failed')
                    status, _ = api(suite, 'GET', f'/api/v1/platform/bots/{bot_uuid}')
                    require(status == 404, 'Deleted callback Bot remains visible')

                try:
                    checked(row, 'callback_cleanup', cleanup)
                except Exception as exc:
                    row.setdefault('cleanup_errors', []).append(f'{type(exc).__name__}: {exc}')
                    if primary_error is None:
                        raise


def restart_profile(profile):
    """Build the exact one-time restart fixture profile for execution and catalog checks."""
    current = copy.deepcopy(profile)
    for key in ('execution', 'resource_limits', 'scenario_groups'):
        current.pop(key, None)
    wanted = {'mock_provider', 'chat_model', 'chat_pipeline', 'chat_bot', 'slow_model', 'slow_pipeline'}
    current['resources'] = [item for item in current['resources'] if item['id'] in wanted]
    require(
        {item['id'] for item in current['resources']} == wanted,
        'Restart checks require the standard chat/slow fixtures',
    )
    slow_bot = copy.deepcopy(next(item for item in current['resources'] if item['id'] == 'chat_bot'))
    slow_bot['id'] = 'restart_slow_bot'
    slow_bot['body']['name'] = 'QA runtime restart slow'
    slow_bot['body']['event_bindings'][0]['target_uuid'] = '${slow_pipeline}'
    current['resources'].append(slow_bot)
    current.update(coverage_suite='scenarios', cleanup='always', plugins=[], cases=[])
    for name, bot, expected in (
        ('core_restart_history', 'chat_bot', 'LANGBOT_CHAT_OK'),
        ('runtime_restart_recovery', 'restart_slow_bot', 'LANGBOT_SLOW_STREAM_OK'),
    ):
        current['cases'].append(
            {
                'name': name,
                'stage': 'restart',
                'expect': expected,
                'http_group': {
                    'url': '${core_base_url}/bots/${' + bot + '}/sync',
                    'secret_env': 'LANGBOT_QA_GROUP_SECRET',
                    'message': 'ai Run the restart QA scenario',
                },
            }
        )
    return current


def run_restart_checks(profile, profile_path, output, env, restart_owned):
    """Run owned-service restart checks once, before fixed-PID resource sampling starts."""
    from regression_smoke import UnresolvedRun, reconcile_scenario_runs
    from regression_suite import Suite, resolve
    from regression_traffic import group_request

    started = time.monotonic()
    deadline = started + 120

    def timeout(maximum):
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise TimeoutError('Restart preflight exceeded its 120-second deadline')
        return min(maximum, remaining)

    current = restart_profile(profile)
    output = Path(output)
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    suite = Suite(current, Path(profile_path), output, env)
    suite.timeout = timeout
    user_token = suite.env.get('LANGBOT_QA_USER_TOKEN')
    if user_token:
        suite.secrets.append(user_token)
    suite.write('profile.json', current)
    result = {'mode': 'restart_preflight', 'errors': [], 'incomplete': [], 'cases': [], 'phases': []}

    def restart(row, name):
        receipt = restart_owned(name, timeout=timeout(60))
        require(
            isinstance(receipt, dict)
            and receipt.get('old_pid')
            and receipt.get('new_pid')
            and receipt['old_pid'] != receipt['new_pid'],
            'Owned restart did not replace the service process',
        )
        row['restart'] = receipt
        timeout(1)

    try:
        if not user_token:
            raise ScenarioUnavailable('Restart terminal readback requires LANGBOT_QA_USER_TOKEN')
        suite.prepare()
        for original in current['cases']:
            row = {'case': original['name'], 'stage': 'restart', 'status': 'failed', 'after_id': after_id(suite)}
            result['cases'].append(row)
            case = resolve(original, suite.variables)
            session_id = 'qa-restart-' + secrets.token_hex(8)
            token = secrets.token_hex(16)
            worker = None
            before = time.monotonic()
            try:
                if row['case'] == 'core_restart_history':
                    checked(
                        row,
                        'before_restart',
                        lambda: group_request(
                            case, session_id, 'qa-member', 1, token, 'none', suite.env, timeout=timeout(20)
                        ),
                    )
                    completed(suite, row, session_id, row['after_id'])
                    checked(row, 'process_replaced', lambda: restart(row, 'core'))
                    after = after_id(suite)
                    checked(
                        row,
                        'history_after_restart',
                        lambda: group_request(
                            case,
                            session_id,
                            'qa-member',
                            2,
                            secrets.token_hex(16),
                            token,
                            suite.env,
                            timeout=timeout(20),
                        ),
                    )
                    completed(suite, row, session_id, after)
                else:
                    outcome = {}

                    def request():
                        try:
                            outcome['response'] = group_request(
                                case, session_id, 'qa-member', 1, token, 'none', suite.env, timeout=timeout(25)
                            )
                        except Exception as exc:
                            outcome['error'] = type(exc).__name__ + ': ' + str(exc)

                    worker = threading.Thread(target=request, daemon=True)
                    worker.start()
                    running_deadline = time.monotonic() + timeout(10)
                    while True:
                        with closing(ledger(suite)) as connection:
                            runs = connection.execute(
                                'SELECT run_id, status, finished_at FROM agent_run '
                                'WHERE workspace_id=? AND conversation_id=? AND id>?',
                                (suite.variables['workspace_uuid'], 'group_' + session_id, row['after_id']),
                            ).fetchall()
                        if len(runs) == 1 and runs[0]['status'] == 'running' and not runs[0]['finished_at']:
                            break
                        if outcome or time.monotonic() >= running_deadline:
                            raise TimeoutError('No unique in-flight run was observed before Runtime restart')
                        time.sleep(0.05)
                    row['interrupted_run_id'] = runs[0]['run_id']
                    checked(row, 'process_replaced', lambda: restart(row, 'runtime'))
                    worker.join(timeout=timeout(25))
                    if worker.is_alive():
                        raise TimeoutError('Interrupted request did not finish after Runtime restart')
                    row['interrupted_response'] = outcome
                    checked(
                        row,
                        'no_false_success',
                        lambda: require(
                            'response' not in outcome, 'Interrupted request returned a successful business response'
                        ),
                    )
                    from regression_smoke import completed_run

                    with closing(ledger(suite)) as connection:
                        terminal = completed_run(
                            connection,
                            suite.variables['workspace_uuid'],
                            'group_' + session_id,
                            row['after_id'],
                            timeout(20),
                        )

                    def public_terminal():
                        status, payload = api(
                            suite,
                            'GET',
                            f'/api/v1/monitoring/executions/agent/{row["interrupted_run_id"]}?section=overview',
                            headers={'Authorization': 'Bearer ' + user_token},
                        )
                        run = payload.get('data', {}).get('run', {})
                        require(
                            status == 200
                            and payload.get('code') == 0
                            and run.get('run_id') == row['interrupted_run_id'] == terminal['run_id']
                            and run.get('status') == terminal['status']
                            and run['status'] in ('failed', 'cancelled', 'timeout'),
                            'Interrupted run did not expose the expected failure terminal state',
                        )
                        return run

                    row['public_terminal'] = checked(row, 'interrupted_terminal', public_terminal)
                    record_run(suite, row, terminal['run_id'], terminal['status'])
                    recovery = resolve(current['cases'][0], suite.variables)
                    recovery_session = 'qa-runtime-recovered-' + secrets.token_hex(8)
                    after = after_id(suite)
                    checked(
                        row,
                        'response_after_restart',
                        lambda: group_request(
                            recovery,
                            recovery_session,
                            'qa-member',
                            1,
                            secrets.token_hex(16),
                            'none',
                            suite.env,
                            timeout=timeout(20),
                        ),
                    )
                    completed(suite, row, recovery_session, after)
                row['status'] = 'passed'
            except Exception as exc:
                row.update(
                    status='unknown'
                    if isinstance(exc, (TimeoutError, UnresolvedRun, ScenarioUnavailable))
                    else 'failed',
                    error=str(exc),
                )
                result['errors'].append(f'{row["case"]}: {row["error"]}')
                if row['status'] == 'unknown':
                    result['incomplete'].append(result['errors'][-1])
            finally:
                if worker is not None and worker.is_alive():
                    worker.join(timeout=max(0, min(5, deadline - time.monotonic())))
                    if worker.is_alive():
                        error = 'Restart request worker did not stop before cleanup deadline'
                        row.setdefault('cleanup_errors', []).append(error)
                        result['errors'].append(f'{row["case"]}: cleanup failed: {error}')
                row['seconds'] = time.monotonic() - before
                suite.write('cases.json', result['cases'])
            if row['status'] != 'passed':
                break
        reconcile_scenario_runs(suite, result, key='ledger_closeout')
    except Exception as exc:
        result['errors'].append('restart preparation: ' + str(exc))
        if isinstance(exc, (TimeoutError, ScenarioUnavailable)):
            result['incomplete'].append(result['errors'][-1])
    finally:
        suite.write('cases.json', result['cases'])
        try:
            suite.finish(result)
        except Exception as exc:
            result['errors'].append('restart finalization: ' + str(exc))
            result.update(passed=False, outcome='FAIL')
        result.update(elapsed_seconds=time.monotonic() - started, coverage_dir=str(output))
        suite.write('summary.json', result)
    return result
