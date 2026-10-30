"""Bounded concurrent conversations and cancellation isolation in one Workspace."""

from concurrent.futures import ThreadPoolExecutor
from contextlib import ExitStack, closing
import copy
import json
from pathlib import Path
import threading
import secrets
from uuid import uuid4

import regression_execution_cases as execution
from regression_api_checks import owned_resource
from regression_coverage import checked
from regression_lifecycle_cases import after_id, ledger
from regression_local_cases import record_run, require
from regression_smoke import check_run, completed_run
from regression_traffic import group_request

CASE_NAMES = ('isolation.same_pipeline', 'isolation.cross_pipeline', 'isolation.cancel_neighbor')


def add_cases(profile):
    require(profile.get('coverage_suite') == 'isolation', 'Isolation requires its dedicated suite')
    profile['cases'] = [
        {'name': name, 'scenario': name, 'stage': 'isolation', 'expect': 'ISOLATION_OK'} for name in CASE_NAMES
    ]
    profile['scenario_groups'] = ['isolation']


def isolation_profile(base):
    profile = copy.deepcopy(base)
    execution.add_cases(profile)
    wanted = {
        'mock_provider',
        'chat_model',
        'slow_model',
        'chat_pipeline',
        'fault_interrupt_model',
        'fault_interrupt_check_model',
    }
    profile['resources'] = [item for item in profile['resources'] if item['id'] in wanted]
    resources = {item['id']: item for item in profile['resources']}
    resources['slow_model']['body']['name'] = 'mock-slow'
    resources['chat_model']['body']['name'] = 'mock-slow-stream'
    resources['chat_pipeline']['body']['config']['ai']['runner_config'][execution.RUNNER]['model']['primary'] = (
        '${slow_model}'
    )
    other = copy.deepcopy(resources['chat_pipeline'])
    other['id'], other['body']['name'] = 'isolation_pipeline', 'regression isolation peer'
    other['body']['config']['ai']['runner_config'][execution.RUNNER]['model']['primary'] = '${chat_model}'
    profile['resources'].append(other)
    profile['coverage_suite'] = 'isolation'
    add_cases(profile)
    return profile


def lane(suite, bot, expected, model):
    return {
        'group': 'qa-isolation-' + uuid4().hex,
        'previous': 'none',
        'model': model,
        'bot': bot,
        'case': {
            'expect': expected,
            'http_group': {
                'url': suite.variables['core_base_url'] + '/bots/' + bot + '/sync',
                'secret_env': 'LANGBOT_QA_GROUP_SECRET',
                'message': 'ai Run the isolation QA scenario',
            },
        },
    }


def check_reply(parts, expected):
    # /sync retains cumulative stream snapshots and drops their final/sequence metadata.
    texts = [part.get('text') for part in parts if part.get('type') == 'Plain']
    require(len(texts) == len(parts) and bool(texts), 'Reply must contain only text snapshots')
    require(all(isinstance(text, str) and expected.startswith(text) for text in texts), 'Reply contains foreign output')
    require(
        texts[-1] == expected and all(b.startswith(a) for a, b in zip(texts, texts[1:])),
        'Reply lost its final output or reversed its stream',
    )


def turn(suite, item, number, barrier, receipt):
    receipt.update(
        group=item['group'],
        turn=number,
        token=uuid4().hex,
        after_id=after_id(suite),
        model=item['model'],
        expected=item['case']['expect'],
    )
    barrier.wait(timeout=suite.timeout(10))
    response_error = None
    try:
        receipt['response'] = checked(
            receipt,
            'response_identity',
            lambda: group_request(
                item['case'],
                item['group'],
                'qa-isolation-member',
                number,
                receipt['token'],
                item['previous'],
                suite.env,
                timeout=suite.timeout(45),
            ),
        )
        checked(
            receipt,
            'exact_reply',
            lambda: check_reply(
                receipt['response']['data']['message'], item['case']['expect'] + ' GROUP_ACK=' + receipt['token']
            ),
        )
    except Exception as exc:
        response_error = exc
    try:
        with closing(ledger(suite)) as db:
            run = completed_run(
                db, suite.variables['workspace_uuid'], 'group_' + item['group'], receipt['after_id'], suite.timeout(20)
            )
            checked(receipt, 'run_events', lambda: check_run(db, run, item['case']))
            receipt['interval'] = dict(
                db.execute(
                    'SELECT run_id, started_at, finished_at, bot_id FROM agent_run WHERE run_id=?', (run['run_id'],)
                ).fetchone()
            )
        checked(
            receipt,
            'bot_identity',
            lambda: require(receipt['interval']['bot_id'] == item['bot'], 'Run belongs to a different Bot'),
        )
        record_run(suite, receipt, run['run_id'], 'completed')
    except Exception as exc:
        if response_error is not None:
            receipt['ledger_error'] = str(exc)
            raise response_error from exc
        raise
    if response_error is not None:
        raise response_error
    item['previous'] = receipt['token']
    return receipt


def overlapping(intervals):
    require(
        len(intervals) == 2 and all(x.get('started_at') and x.get('finished_at') for x in intervals),
        'Two persisted execution intervals are required',
    )
    require(
        max(x['started_at'] for x in intervals) < min(x['finished_at'] for x in intervals),
        'The requests did not execute concurrently',
    )
    return intervals


def merge_receipts(row, receipts):
    row.setdefault('requests', []).extend(receipts)
    for receipt in receipts:
        row.setdefault('scenario_runs', []).extend(receipt.get('scenario_runs', []))


def verify_wire(suite, row, receipts):
    path = Path(suite.path(suite.profile['smoke']['mock_records']))
    records = [json.loads(line) for line in path.read_text().splitlines()]
    owned = {receipt['group'] for receipt in receipts}
    from mock_llm import GROUP_TURN, group_ack

    matched = []
    for record in records:
        messages = record.get('request', {}).get('messages', [])
        starts = [i for i, message in enumerate(messages) if message.get('role') == 'user']
        if not starts:
            continue
        markers = list(GROUP_TURN.finditer(str(messages[starts[-1]].get('content', ''))))
        if not markers or markers[-1][1] not in owned:
            continue
        require(
            record['status'] == 200 and record.get('response_complete'), 'Owned model request failed or did not finish'
        )
        expected = next((receipt for receipt in receipts if receipt['token'] == markers[-1][3]), None)
        require(expected is not None, 'Model request has an unowned token')
        require(record['request']['model'] == expected['model'], 'Conversation used an unexpected model')
        acknowledgement = group_ack(messages, starts[-1])
        require(
            record.get('response', {}).get('content') == expected['expected'] + acknowledgement,
            'Mock response does not identify the current request',
        )
        matched.append(markers[-1][3])
    require(
        sorted(matched) == sorted(receipt['token'] for receipt in receipts),
        'Model requests were duplicated, lost, or assigned to a different conversation',
    )
    return {'requests': len(matched), 'history_isolated': True}


def parallel_history(suite, row, bots):
    lanes = [lane(suite, *bot) for bot in bots]
    with ThreadPoolExecutor(max_workers=2) as pool:
        for number in (1, 2):
            barrier, receipts = threading.Barrier(2), [{}, {}]
            futures = [
                pool.submit(turn, suite, item, number, barrier, receipt) for item, receipt in zip(lanes, receipts)
            ]
            errors = []
            try:
                for future in futures:
                    try:
                        future.result(timeout=suite.timeout(70))
                    except Exception as exc:
                        errors.append(exc)
            finally:
                merge_receipts(row, receipts)
            if errors:
                row['request_errors'] = [str(error) for error in errors]
                raise errors[0]
            checked(row, f'overlap_turn_{number}', lambda: overlapping([receipt['interval'] for receipt in receipts]))
    row['wire'] = checked(row, 'wire_identity_history_once', lambda: verify_wire(suite, row, row['requests']))


def cancel_neighbor(suite, row, bot):
    peer, receipt, future = lane(suite, *bot), {}, None
    with ThreadPoolExecutor(max_workers=1) as pool:

        def before_cancel():
            nonlocal future
            future = pool.submit(turn, suite, peer, 1, threading.Barrier(1), receipt)

            def active():
                with closing(ledger(suite)) as db:
                    matches = db.execute(
                        'SELECT run_id, started_at FROM agent_run WHERE workspace_id=? AND conversation_id=? AND id>? '
                        'AND started_at IS NOT NULL AND finished_at IS NULL',
                        (suite.variables['workspace_uuid'], 'group_' + peer['group'], row['after_id']),
                    ).fetchall()
                require(len(matches) <= 1, 'Neighbor submission created multiple active runs')
                return dict(matches[0]) if matches else None

            row['neighbor_at_cancel'] = checked(
                row,
                'neighbor_active_at_cancel',
                lambda: execution._poll(
                    suite,
                    active,
                    'Neighbor never became active before cancellation',
                    seconds=10,
                ),
            )
            require(
                execution._sessions(suite).get(row['box_session_id'], {}).get('status') == 'running',
                'Target tool stopped before the neighbor became active',
            )

        try:
            execution.run_case(suite, {'scenario': 'execution.cancel_cleanup'}, row, before_cancel=before_cancel)
        finally:
            if future is not None:
                try:
                    future.result(timeout=suite.timeout(70))
                finally:
                    merge_receipts(row, [receipt])
        require(future is not None, 'Cancellation never reached its active execution checkpoint')
    cancelled = next(run for run in row['scenario_runs'] if run['expected_status'] == 'cancelled')
    with closing(ledger(suite)) as db:
        interval = dict(
            db.execute(
                'SELECT run_id, started_at, finished_at FROM agent_run WHERE run_id=?', (cancelled['run_id'],)
            ).fetchone()
        )
    checked(row, 'cancellation_overlapped_neighbor', lambda: overlapping([interval, receipt['interval']]))
    row['wire'] = checked(row, 'neighbor_identity_once', lambda: verify_wire(suite, row, [receipt]))


def run_case(suite, case, row):
    require(case['scenario'] in CASE_NAMES, 'Unknown isolation scenario')
    secret = secrets.token_urlsafe(32)
    suite.secrets.append(secret)
    suite.env['LANGBOT_QA_GROUP_SECRET'] = secret
    with ExitStack() as stack:
        bots = []
        pipelines = [('chat_pipeline', 'LANGBOT_SLOW_OK', 'mock-slow')]
        if case['scenario'] == 'isolation.cross_pipeline':
            pipelines.append(('isolation_pipeline', 'LANGBOT_SLOW_STREAM_OK', 'mock-slow-stream'))
        for pipeline, expected, model in pipelines:
            body = {
                'name': 'qa-isolation-' + uuid4().hex,
                'adapter': 'http_bot',
                'enable': True,
                'adapter_config': {
                    'inbound_secret': secret,
                    'signature_required': True,
                    'default_session_type': 'group',
                    'callback_url': 'http://127.0.0.1:9/unused-sync-only',
                    'callback_max_retries': 0,
                },
                'event_bindings': [
                    {
                        'event_pattern': 'message.received',
                        'target_type': 'pipeline',
                        'target_uuid': suite.variables[pipeline],
                        'enabled': True,
                        'filters': [],
                    }
                ],
                'plugin_processors': [],
            }
            _, bot = stack.enter_context(
                owned_resource(
                    suite,
                    row,
                    '/api/v1/platform/bots',
                    body,
                    item_key='bot',
                    list_key='bots',
                )
            )
            bots.append((bot, expected, model))
        if case['scenario'] == 'isolation.cancel_neighbor':
            checked(row, 'cancel_isolation', lambda: cancel_neighbor(suite, row, bots[0]))
        else:
            if case['scenario'] == 'isolation.same_pipeline':
                bots = [bots[0], bots[0]]
            checked(row, 'conversation_isolation', lambda: parallel_history(suite, row, bots))
    return {'result': 'ISOLATION_OK', 'owned_runs': len(row.get('scenario_runs', []))}
