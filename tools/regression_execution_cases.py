"""Local Agent faults with public API, mock-wire, and independent Run evidence."""

import copy
import hashlib
import json
from pathlib import Path
import time
import sys
import urllib.request
from uuid import uuid4

from regression_coverage import checked
from regression_local_cases import api, endpoint, headers, record_run, require

GROUP = 'faults'
RUNNER = 'plugin:langbot-team/LocalAgent/default'
CASE_NAMES = {
    'execution.cancel_cleanup',
    'execution.timeout_cleanup',
    'execution.retry_side_effects',
    'model.stream_disconnect',
    'model.exhausted_fallback',
    'tools.path_escape',
}
MODELS = {
    'interrupt': 'mock-local-interrupt',
    'interrupt_check': 'mock-local-interrupt-check',
    'retry': 'mock-local-retry-side-effect',
    'disconnect': 'mock-stream-disconnect',
    'escape': 'mock-local-path-escape',
}


def add_cases(profile):
    template = next(item for item in profile['resources'] if item['id'] == 'chat_model')
    for name, model in MODELS.items():
        item = copy.deepcopy(template)
        item['id'] = 'fault_' + name + '_model'
        item['body']['name'] = model
        item['body']['extra_args'] = {'request_policy': {'retries': 1 if name == 'retry' else 0}}
        profile['resources'].append(item)
    for name in sorted(CASE_NAMES):
        profile['cases'].append(
            {'name': name, 'scenario': name, 'stage': name.split('.')[0], 'expect': 'FAULT_CASE_OK'}
        )


def _data(suite, method, path, body=None):
    status, payload = api(suite, method, path, body)
    require(
        status == 200 and isinstance(payload, dict) and payload.get('code') == 0,
        f'{method} {path} returned HTTP {status}: {payload}',
    )
    return payload.get('data')


def _poll(suite, read, message, seconds=20):
    deadline = time.monotonic() + suite.timeout(seconds)
    while True:
        value = read()
        if value:
            return value
        if time.monotonic() >= deadline:
            raise TimeoutError(message)
        time.sleep(0.1)


def _agent_config(suite, scope, model, *, box=False, timeout=30, fallbacks=()):
    return {
        'runner': {'id': RUNNER},
        'allowed_tools': ['exec', 'read'] if box else [],
        'runner_config': {
            RUNNER: {
                'model': {'primary': suite.variables[model], 'fallbacks': [suite.variables[key] for key in fallbacks]},
                'prompt': [{'role': 'system', 'content': 'Execute the deterministic QA scenario.'}],
                'knowledge-bases': [],
                'box-enabled': box,
                'box-session-id-template': scope,
                'timeout': timeout,
                'max-tool-iterations': 5,
                'tool-execution-mode': 'serial',
            }
        },
    }


def _sessions(suite):
    result = _data(suite, 'GET', '/api/v1/box/sessions')
    require(isinstance(result, list), 'Box sessions must be an array')
    return {item['session_id']: item for item in result}


def _running_box(suite, session_id):
    def read():
        return session_id if _sessions(suite).get(session_id, {}).get('status') == 'running' else None

    return _poll(suite, read, 'The long exec never became active in its Box')


def _stream(suite, agent, scope, row, *, interrupt=None, box_session_id=None, frame_key='frames'):
    request = urllib.request.Request(
        endpoint(suite, f'/api/v1/agents/{agent}/debug/stream'),
        data=json.dumps({'text': f'Run the QA scenario LB_MOCK_SCOPE={scope}', 'conversation_id': scope}).encode(),
        headers={**headers(suite), 'Content-Type': 'application/json'},
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    frames = []
    row[frame_key] = frames
    deadline = time.monotonic() + suite.timeout(45)
    with opener.open(request, timeout=suite.timeout(45)) as response:
        require(response.status == 200, 'Agent debug stream was not accepted')
        while time.monotonic() < deadline:
            line = response.readline(256 * 1024 + 1)
            require(len(line) <= 256 * 1024, 'Agent debug frame exceeded its limit')
            if not line:
                break
            if not line.strip():
                continue
            text = line.decode('utf-8')
            for secret in suite.secrets:
                text = text.replace(secret, '[REDACTED]')
            frame = json.loads(text)
            require(isinstance(frame, dict), 'Agent debug frame must be an object')
            frames.append(frame)
            if interrupt and frame.get('kind') == 'result':
                event = frame.get('data', {})
                if event.get('type') == 'tool.call.started' and event.get('data', {}).get('parameters', {}).get(
                    'command', ''
                ).startswith('sleep 8;'):
                    row['box_session_id'] = checked(row, 'exec_active', lambda: _running_box(suite, box_session_id))
                    if interrupt == 'cancel':
                        break  # Closing this public debug stream cancels its run.
            if frame.get('kind') in {'completed', 'error'}:
                return frames
        else:
            raise TimeoutError('Agent debug stream exceeded the observation deadline; not retried')
    if interrupt == 'cancel':
        require('box_session_id' in row, 'Cancellation did not reach the active long exec')
    else:
        raise RuntimeError('Agent debug stream ended without a terminal frame; outcome unknown')
    return frames


def _terminal(suite, agent, conversation, row, expected, excluded=()):
    def read():
        runs = _data(suite, 'GET', f'/api/v1/agents/{agent}/runs')['items']
        matches = [run for run in runs if run['conversation_id'] == conversation and run['run_id'] not in excluded]
        require(len(matches) <= 1, 'One scenario submission created multiple AgentRuns')
        return matches[0] if matches and matches[0].get('finished_at') else None

    run = _poll(suite, read, 'AgentRun did not terminate after the scenario')
    try:
        checked(
            row,
            'run_status',
            lambda: require(run['status'] == expected, f'Public Run status is {run["status"]}; expected {expected}'),
        )
    finally:
        checked(row, 'ledger_status', lambda: record_run(suite, row, run['run_id'], expected))
    detail = _data(suite, 'GET', f'/api/v1/agents/{agent}/runs/{run["run_id"]}/events')
    require(not detail.get('has_more'), 'Scenario trace exceeds the bounded event page')
    return run, detail['items']


def _mock_rows(suite, scope, count):
    path = Path(suite.path(suite.profile['smoke']['mock_records']))

    def read():
        rows = []
        for line in path.read_text().splitlines():
            try:
                item = json.loads(line)
            except ValueError:
                continue  # A concurrent handler may still be appending its last line.
            if item.get('scope') == scope:
                rows.append(item)
        return rows if len(rows) >= count else None

    return _poll(suite, read, 'The expected model request was not recorded', seconds=5)


def _tool_events(events, name):
    return [
        item['data']
        for item in events
        if item['type'] == 'tool.call.completed' and item['data'].get('tool_name') == name
    ]


def _cleanup(suite, agent, scope, row, expected):
    original = sys.exception()
    errors = []
    try:
        runs = _data(suite, 'GET', f'/api/v1/agents/{agent}/runs')['items']
        registered = {item['run_id'] for item in row.get('scenario_runs', [])}
        pending = [run for run in runs if run['run_id'] not in registered]
        if not registered and len(pending) == 1:
            record_run(suite, row, pending[0]['run_id'], expected)
        elif pending:
            raise ValueError('Scenario has unexpected or unregistered AgentRuns at cleanup')
    except (ValueError, OSError, RuntimeError) as exc:
        errors.append(f'Run closeout: {exc}')
    try:
        _data(suite, 'DELETE', f'/api/v1/agents/{agent}')
        status, _ = api(suite, 'GET', f'/api/v1/agents/{agent}')
        require(status == 404, 'Deleted scenario Agent remains visible')
    except (ValueError, OSError, RuntimeError) as exc:
        errors.append(f'Agent cleanup: {exc}')
    if row['case'] == 'execution.retry_side_effects':
        try:
            url = suite.variables['mock_base_url'].removesuffix('/v1').rstrip('/') + '/_mock/scopes/' + scope
            request = urllib.request.Request(url, method='DELETE')
            opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
            with opener.open(request, timeout=suite.timeout(10)) as response:
                payload = json.load(response)
                require(
                    response.status == 200 and payload.get('scope') == scope and payload.get('released') in (0, 1),
                    'Mock recovery scope cleanup failed',
                )
        except (ValueError, OSError, RuntimeError) as exc:
            errors.append(f'Mock scope cleanup: {exc}')
    row['cleanup_errors'] = errors
    if errors:
        raise RuntimeError('; '.join(([str(original)] if original else []) + errors))


def run_case(suite, case, row):
    scenario = case['scenario']
    require(scenario in CASE_NAMES, 'Unknown local execution scenario')
    scope = 'qa-fault-' + uuid4().hex
    box_key = 'qa-fault-' + hashlib.sha256((str(suite.output.resolve()) + scenario).encode()).hexdigest()[:24]
    # Core's RunnerBoxService maps the requested reuse key to this logical ID.
    box_session_id = 'runner-' + hashlib.sha256(box_key.encode()).hexdigest()
    interrupt = scenario in {'execution.cancel_cleanup', 'execution.timeout_cleanup'}
    model = {
        'execution.cancel_cleanup': 'fault_interrupt_model',
        'execution.timeout_cleanup': 'fault_interrupt_model',
        'execution.retry_side_effects': 'fault_retry_model',
        'model.stream_disconnect': 'fault_disconnect_model',
        'model.exhausted_fallback': 'error503_model',
        'tools.path_escape': 'fault_escape_model',
    }[scenario]
    fallbacks = (
        ('error429_model',)
        if scenario == 'model.exhausted_fallback'
        else ('chat_model',)
        if scenario == 'model.stream_disconnect'
        else ()
    )
    config = _agent_config(
        suite,
        box_key,
        model,
        box=interrupt or scenario in {'execution.retry_side_effects', 'tools.path_escape'},
        timeout=5 if scenario == 'execution.timeout_cleanup' else 30,
        fallbacks=fallbacks,
    )
    expected = (
        'cancelled'
        if scenario == 'execution.cancel_cleanup'
        else 'timeout'
        if interrupt
        else 'failed'
        if scenario.startswith('model.')
        else 'completed'
    )
    created = _data(suite, 'POST', '/api/v1/agents', {'name': scope, 'config': config})
    agent = created['uuid']
    try:
        row['agent_uuid'], row['conversation_id'] = agent, scope
        row['box_reuse_key'] = box_key
        frames = _stream(
            suite,
            agent,
            scope,
            row,
            interrupt='cancel' if scenario == 'execution.cancel_cleanup' else 'timeout' if interrupt else None,
            box_session_id=box_session_id,
        )
        row['frames'] = frames
        run, events = _terminal(suite, agent, scope, row, expected)
        row['run_events'] = events
        request_count = (
            4 if scenario == 'execution.retry_side_effects' else 1 if scenario == 'model.stream_disconnect' else 2
        )
        requests = _mock_rows(suite, scope, request_count)
        row['model_requests'] = [
            {'model': item['request']['model'], 'status': item['status'], 'faults': item.get('faults', [])}
            for item in requests
        ]
        if interrupt:
            checked(
                row,
                'exec_active',
                lambda: require('box_session_id' in row, 'No active exec was observed before interruption'),
            )
            checked(
                row,
                'exec_stopped',
                lambda: _poll(
                    suite,
                    lambda: _sessions(suite).get(row['box_session_id'], {}).get('status') == 'idle',
                    'Interrupted Box exec remains active',
                ),
            )
            config = _agent_config(suite, box_key, 'fault_interrupt_check_model', box=True)
            _data(suite, 'PUT', f'/api/v1/agents/{agent}', {'config': config})
            recovery = _stream(suite, agent, scope, row, frame_key='recovery_frames')
            calls = _tool_events([frame['data'] for frame in recovery if frame.get('kind') == 'result'], 'exec')
            row['recovery_exec_results'] = calls
            try:
                recovery_run, recovery_events = _terminal(
                    suite, agent, scope, row, 'completed', excluded={run['run_id']}
                )
                row['recovery_run_id'], row['recovery_events'] = recovery_run['run_id'], recovery_events
            finally:
                # The tool's evidence remains authoritative if its failed check also makes the model fail.
                checked(
                    row,
                    'no_late_side_effect',
                    lambda: require(
                        len(calls) == 1
                        and (calls[0].get('result') or {}).get('exit_code') == 0
                        and calls[0]['result'].get('stdout') == 'INTERRUPT_CLEANUP_OK',
                        'Interrupted shell cleanup failed: ' + json.dumps(calls, ensure_ascii=False),
                    ),
                )
        elif scenario == 'execution.retry_side_effects':
            checked(
                row,
                'fault_injected',
                lambda: require(
                    [item['status'] for item in requests] == [503, 200, 200, 200]
                    and all(item['request']['model'] == 'mock-local-retry-side-effect' for item in requests),
                    'Expected one 503 retry followed by tool execution and completion',
                ),
            )
            calls = _tool_events(events, 'exec')
            checked(
                row,
                'side_effect_once',
                lambda: require(
                    len(calls) == 2
                    and all(call.get('result', {}).get('exit_code') == 0 for call in calls)
                    and [call['result'].get('stdout') for call in calls] == ['SIDE_EFFECT_WRITTEN', 'SIDE_EFFECT_ONCE'],
                    'Model retry duplicated or lost the tool side effect',
                ),
            )
        elif scenario == 'tools.path_escape':
            calls = _tool_events(events, 'read')
            checked(
                row,
                'path_rejected',
                lambda: require(
                    len(calls) == 1 and 'Path escapes the workspace boundary' in str(calls[0].get('error')),
                    'The real Host tool did not reject the path escape',
                ),
            )
            checked(
                row,
                'no_file_content',
                lambda: require('root:' not in json.dumps(frames), 'Rejected file content appeared in Agent output'),
            )
        else:
            if scenario == 'model.stream_disconnect':
                checked(
                    row,
                    'fault_injected',
                    lambda: require(
                        len(requests) == 1
                        and requests[0].get('injected_disconnect') is True
                        and not requests[0]['response_complete'],
                        'The stream disconnect was not observed',
                    ),
                )
                checked(
                    row,
                    'no_fallback_after_partial',
                    lambda: require(
                        requests[0]['request']['model'] == 'mock-stream-disconnect'
                        and any(
                            item.get('data', {}).get('type') == 'message.delta'
                            and item['data'].get('data', {}).get('chunk', {}).get('content')
                            for item in frames
                        ),
                        'The model did not commit partial output before failing',
                    ),
                )
            else:
                checked(
                    row,
                    'fallback_exhausted',
                    lambda: require(
                        [(item['request']['model'], item['status']) for item in requests]
                        == [('mock-503', 503), ('mock-429', 429)],
                        'The configured fallback sequence was not exhausted',
                    ),
                )
            config = _agent_config(suite, scope, 'chat_model')
            _data(suite, 'PUT', f'/api/v1/agents/{agent}', {'config': config})
            recovery = _stream(suite, agent, scope, row, frame_key='recovery_frames')
            _terminal(suite, agent, scope, row, 'completed', excluded={run['run_id']})
            checked(
                row,
                'recovered',
                lambda: require(
                    any(
                        item.get('kind') == 'completed' and item.get('data', {}).get('final_text') == 'LANGBOT_CHAT_OK'
                        for item in recovery
                    ),
                    'A healthy model did not recover after the failed run',
                ),
            )
        if config['runner_config'][RUNNER]['box-enabled']:
            checked(
                row,
                'box_idle',
                lambda: _poll(
                    suite,
                    lambda: _sessions(suite).get(box_session_id, {}).get('status') == 'idle',
                    'The scenario Box did not return to idle',
                ),
            )
            row['box_session_id'] = box_session_id
        return {'result': 'FAULT_CASE_OK', 'scenario': scenario, 'run_id': run['run_id']}
    finally:
        _cleanup(suite, agent, scope, row, expected)
