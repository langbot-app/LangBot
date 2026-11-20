#!/usr/bin/env python3
"""Drive independent CLI requests or persistent group conversations with Linux resource sampling."""

import argparse

from tools.regression.mixload_pacing import allocate_group_slot, planned_group_slots
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import subprocess
import sqlite3
import threading
import time
import urllib.error
import uuid

from tools.regression.evidence import check_attachment, check_fields, check_response, checked
from tools.regression.http_bot import group_request, valid_group_settings
from tools.regression.observations import read_endpoint_snapshot, read_process_snapshot
from tools.regression.run_ledger import (
    UnresolvedRun,
    check_run,
    completed_run,
    connect_readonly,
    high_water_mark,
    reconcile_runs,
)


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def http_concurrency(rows):
    """Measure successful group HTTP intervals, excluding subsequent ledger verification."""
    group_rows = [row for row in rows if row.get('group_id')]
    selected = [row for row in group_rows if row.get('status') == 'ok']

    def intervals(items):
        if not items:
            return {'status': 'unknown', 'requests': 0, 'peak_in_flight': None, 'overlap_seconds': None}
        events = []
        for row in items:
            begin, seconds = row.get('elapsed'), row.get('seconds')
            if (
                any(
                    isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not math.isfinite(value)
                    or value < 0
                    for value in (begin, seconds)
                )
                or seconds == 0
            ):
                return {'status': 'unknown', 'requests': len(items), 'peak_in_flight': None, 'overlap_seconds': None}
            events.extend(((begin, 1), (begin + seconds, -1)))
        active = peak = 0
        overlap = 0.0
        previous = min(event[0] for event in events)
        for stamp, change in sorted(events):
            if active >= 2:
                overlap += stamp - previous
            active += change
            peak = max(peak, active)
            previous = stamp
        return {'status': 'observed', 'requests': len(items), 'peak_in_flight': peak, 'overlap_seconds': overlap}

    return {
        **intervals(selected),
        'basis': 'successful_group_http_intervals_excluding_ledger_verification',
        'cases': {
            name: intervals([row for row in selected if row['case'] == name])
            for name in dict.fromkeys(row['case'] for row in group_rows)
        },
    }


def resource_observations(samples):
    """Summarize sampled container/session scale and queue recovery; absence is unknown."""

    def peak(values):
        valid = [
            value
            for value in values
            if not isinstance(value, bool) and isinstance(value, (int, float)) and math.isfinite(value) and value >= 0
        ]
        return {
            'status': 'observed' if values and len(valid) == len(values) else 'unknown',
            'peak': max(valid) if valid else None,
            'samples': len(valid),
            'missing_samples': len(values) - len(valid),
        }

    containers = []
    for row in samples:
        entries = row.get('containers')
        try:
            counts = [int(item['PIDs']) for item in entries] if isinstance(entries, list) else None
            containers.append(
                sum(value > 0 for value in counts)
                if counts is not None and all(value >= 0 for value in counts) and not row.get('container_error')
                else None
            )
        except (ValueError, KeyError, TypeError):
            containers.append(None)
    running = peak(containers)
    running['basis'] = 'docker_stats_rows_with_positive_pids'
    sessions = peak([row.get('health', {}).get('box', {}).get('body.resources.sessions') for row in samples])
    load = [row for row in samples if row.get('phase') == 'load']
    cooldown = [row for row in samples if row.get('phase') == 'cooldown']
    tail = []
    if cooldown:
        end = max(row['elapsed'] for row in cooldown)
        tail = [row for row in cooldown if row['elapsed'] >= end - 30]
    queues = {}
    for target, metrics in {
        'core': ('body.resources.query_pool.queued',),
        'box': (
            'body.resources.blocking_executor.pending',
            'body.resources.creating_session_tasks',
            'body.resources.closing_session_tasks',
        ),
    }.items():
        for metric in metrics:
            before, after = [
                peak([row.get('health', {}).get(target, {}).get(metric) for row in rows]) for rows in (load, tail)
            ]
            queues[target + '.' + metric] = {
                'status': 'observed' if before['status'] == after['status'] == 'observed' else 'unknown',
                'load_peak': before['peak'],
                'cooldown_tail_max': after['peak'],
                'load_samples': before['samples'],
                'cooldown_tail_samples': after['samples'],
                'missing_samples': before['missing_samples'] + after['missing_samples'],
            }
    return {
        'running_containers': running,
        'box_sessions': sessions,
        'queues': queues,
        'cooldown_tail_window_seconds': 30,
    }


def missing_containers(error, candidates):
    messages = {
        prefix + container: container
        for container in candidates
        for prefix in ('Error: No such object: ', 'Error response from daemon: No such container: ')
    }
    lines = [line.strip() for line in error.splitlines() if line.strip()]
    return {messages[line] for line in lines} if lines and all(line in messages for line in lines) else set()


def container_is_absent(container, checked):
    try:
        return not checked(['docker', 'ps', '-a', '--filter', f'id={container}', '--format', '{{.ID}}']).strip()
    except Exception:
        return False


def owned_box_containers(data_root, checked=None):
    """Discover sandboxes mounted below one run's data root, including newly created groups."""
    if checked is None:

        def checked(command):
            return subprocess.check_output(command, text=True, stderr=subprocess.PIPE, timeout=10)

    candidates = checked(['docker', 'ps', '-a', '--filter', 'label=langbot.box=true', '--format', '{{.ID}}']).split()
    if not candidates:
        return []
    root = Path(data_root).resolve()
    owned = []
    for container in candidates:
        try:
            description = checked(['docker', 'inspect', '--format', '{{json .}}', container])
        except subprocess.CalledProcessError as exc:
            if exc.returncode != 1 or (exc.output or '').strip() or not container_is_absent(container, checked):
                raise
            continue  # A sandbox may expire between discovery and inspection.
        except RuntimeError:
            if not container_is_absent(container, checked):
                raise
            continue
        entry = json.loads(description)
        if (
            not isinstance(entry, dict)
            or not isinstance(entry.get('Id'), str)
            or not entry['Id'].startswith(container)
            or not isinstance(entry.get('Mounts'), list)
            or any(
                not isinstance(mount, dict) or not isinstance(mount.get('Source', ''), str) for mount in entry['Mounts']
            )
        ):
            raise ValueError(f'Malformed container inspection: {container}')
        if any(
            Path(mount['Source']).resolve().is_relative_to(root) for mount in entry['Mounts'] if mount.get('Source')
        ):
            owned.append(entry['Id'])
    return owned


def sample_containers(configured, data_root, run=subprocess.run, discover=owned_box_containers):
    def selected():
        return set(configured) | (set(discover(data_root)) if data_root else set())

    containers = selected()
    if not containers:
        return {'containers': []}

    def stats(names):
        return run(
            ['docker', 'stats', '--no-stream', '--format', '{{json .}}', *sorted(names)],
            capture_output=True,
            text=True,
            timeout=10,
        )

    result = stats(containers)
    observation = {}
    missing = missing_containers(result.stderr, containers) if result.returncode == 1 else set()
    # Docker 26 can close the stats stream with EOF when a sampled sandbox is deleted.
    eof = result.returncode == 1 and result.stderr.strip() == 'EOF' and not result.stdout.strip()
    if (missing or eof) and data_root:
        current = selected()
        removed = containers - current
        if removed and (eof or missing <= removed):
            observation['container_churn'] = {
                'removed': sorted(removed),
                'added': sorted(current - containers),
                'first_error': result.stderr.strip(),
            }
            if not current:
                return {**observation, 'containers': []}
            result = stats(current)
    observation['containers'] = [json.loads(line) for line in result.stdout.splitlines() if line]
    if result.returncode:
        observation['container_error'] = result.stderr.strip()
    return observation


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lbctl', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument(
        '--cases', type=Path, required=True, help='JSON cases with name, expect, and args or http_group'
    )
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=600)
    parser.add_argument('--rps', type=float, default=2)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--arrival-mode', choices=('paced', 'open-loop'), default='paced')
    parser.add_argument('--queue-capacity', type=int, default=128, help='Maximum waiting arrivals in open-loop mode')
    parser.add_argument(
        '--max-requests',
        type=int,
        help='Require this many requests, including enabled per-request ledger checks, to finish within --duration',
    )
    parser.add_argument(
        '--groups', type=int, default=0, help='Stable group sessions; zero uses independent CLI requests'
    )
    parser.add_argument('--members-per-group', type=int, default=3)
    parser.add_argument(
        '--group-state', type=Path, help='Carry group histories across load phases; refuses interrupted runs'
    )
    parser.add_argument(
        '--open-loop-groups', action='store_true', help='Use absolute offered slots; report missed admissions'
    )
    parser.add_argument('--ledger-db', type=Path)
    parser.add_argument('--workspace')
    parser.add_argument('--verification-timeout', type=float, default=5)
    parser.add_argument('--cooldown', type=float, default=30)
    parser.add_argument('--pid', action='append', default=[], metavar='NAME=PID')
    parser.add_argument('--health', action='append', default=[], metavar='NAME=URL')
    parser.add_argument('--container', action='append', default=[])
    parser.add_argument('--box-data-root', type=Path, help='Dynamically sample Box containers mounted under this root')
    parser.add_argument(
        '--shared-case-sequence', action='store_true', help='Share the weighted case sequence across workers'
    )
    args = parser.parse_args()
    if (
        not all(math.isfinite(value) for value in (args.duration, args.rps, args.cooldown))
        or args.duration <= 0
        or args.rps <= 0
        or not 1 <= args.workers <= 32
        or args.cooldown < 0
    ):
        parser.error('duration/rps must be positive, workers 1..32, cooldown nonnegative')
    if not 0 <= args.groups <= 4096 or not 1 <= args.members_per_group <= 1000:
        parser.error('groups must be 0..4096 (0 selects CLI mode), members-per-group 1..1000')
    if args.open_loop_groups and args.arrival_mode == 'open-loop':
        parser.error('--open-loop-groups and --arrival-mode open-loop select different schedulers')
    if args.open_loop_groups and not args.groups:
        parser.error('open-loop groups require group mode')
    if args.max_requests is not None and args.max_requests < 1:
        parser.error('max-requests must be positive')
    if args.queue_capacity < 1:
        parser.error('queue-capacity must be positive')
    if args.arrival_mode == 'open-loop' and args.max_requests is not None:
        parser.error('open-loop uses duration and rps to fix arrival count; max-requests is not supported')
    cases = json.loads(args.cases.read_text())
    if (
        not isinstance(cases, list)
        or not cases
        or any(
            not isinstance(case, dict)
            or not isinstance(case.get('name'), str)
            or (
                not args.groups
                and (not isinstance(case.get('args'), list) or not all(isinstance(item, str) for item in case['args']))
            )
            or not isinstance(case.get('expect'), str)
            or not case['expect']
            for case in cases
        )
    ):
        parser.error('cases must contain name, string args, and expected response text')
    if args.groups:
        if args.groups < len(cases):
            parser.error('groups must cover the complete weighted case sequence')
        for case in cases:
            settings = case.get('http_group', {})
            if (
                not valid_group_settings(settings)
                or not settings['url'].startswith(('http://', 'https://'))
                or not os.environ.get(settings['secret_env'])
            ):
                parser.error('group cases need HTTP(S) url, message and a populated secret_env')
    if args.ledger_db and (not args.ledger_db.is_file() or not args.workspace):
        parser.error('ledger verification requires an existing SQLite file and workspace')
    if not math.isfinite(args.verification_timeout) or args.verification_timeout <= 0:
        parser.error('verification timeout must be positive')
    args.output.mkdir(parents=True, exist_ok=False)
    pids = {name: int(pid) for name, pid in (value.split('=', 1) for value in args.pid)}
    endpoints = dict(value.split('=', 1) for value in args.health)
    rows = []
    verified_ids = set()
    conversations = set()
    sampling_errors = []
    lock = threading.Lock()
    group_condition = threading.Condition(lock)
    stop = threading.Event()
    admission_closed = threading.Event()
    phase = ['load']
    next_case = 0
    admitted_requests = 0
    next_slot = 0
    offered_slots = planned_group_slots(args.duration, args.rps, args.max_requests) if args.open_loop_groups else None
    missed_by_case = Counter()
    phase_start_id = 0
    if args.ledger_db:
        with connect_readonly(args.ledger_db) as db:
            phase_start_id = high_water_mark(db)
    started = time.monotonic()
    deadline = started + args.duration
    redactions = [value for name, value in os.environ.items() if 'API_KEY' in name and value]
    group_state = None
    groups = []
    if args.groups:
        redactions += [os.environ[case['http_group']['secret_env']] for case in cases]
        state_path = args.group_state or args.output / 'group-state.json'
        fingerprint = [(case['name'], case['http_group']) for case in cases]
        group_state = (
            json.loads(state_path.read_text())
            if state_path.exists()
            else {
                'run_id': uuid.uuid4().hex[:12],
                'cases': fingerprint,
                'groups': [],
                'in_progress': False,
            }
        )
        if group_state.get('in_progress') or json.dumps(group_state['cases']) != json.dumps(fingerprint):
            parser.error('group state is interrupted or belongs to different cases; inspect it before reuse')
        for index in range(len(group_state['groups']), args.groups):
            group_state['groups'].append(
                {
                    'id': f'qa-{group_state["run_id"]}-g{index:04d}',
                    'case': index % len(cases),
                    'turn': 1,
                    'previous': 'none',
                    'failed': False,
                }
            )
        groups = [
            dict(item, due=started + index / args.rps, busy=False)
            for index, item in enumerate(group_state['groups'][: args.groups])
        ]
        group_state['in_progress'] = True
        state_path.write_text(json.dumps(group_state, indent=2))
        state_path.chmod(0o600)

    def redact(text):
        for secret in redactions:
            text = text.replace(secret, '[REDACTED]')
        return text

    def open_ledger():
        if not args.ledger_db:
            return None, None
        connection = connect_readonly(args.ledger_db)
        connection.row_factory = sqlite3.Row
        connection.execute('PRAGMA query_only=ON')
        after_id = high_water_mark(connection)
        return connection, after_id

    def verify(row, case, connection, after_id, is_group=False):
        began = time.monotonic()
        data = row['output']['data']
        checks = {}
        if case.get('fields'):
            checks['fields'] = checked(row, 'fields', lambda: check_fields(data, case['fields']))
        if case.get('forbid'):
            checked(row, 'isolation', lambda: check_response(data, case['expect'], case['forbid']))
        if case.get('attachment'):
            checks['attachment'] = checked(row, 'attachment', lambda: check_attachment(data, case['attachment']))
        runner = is_group or case.get('args', [])[:2] == ['pipeline', 'run']
        row['requires_runner'] = runner
        if connection and runner:
            if not isinstance(data, dict):
                raise ValueError('Runner response data must be an object')
            session = data.get('session_id')
            if not isinstance(session, str) or not session:
                raise UnresolvedRun('Response has no conversation identity')
            conversation = 'group_' + session if is_group else session
            with lock:
                conversations.add(conversation)
            run = completed_run(
                connection,
                args.workspace,
                conversation,
                after_id,
                args.verification_timeout,
            )
            row['run'] = run

            def verify_ledger():
                result = check_run(connection, run, case)
                with lock:
                    if run['run_id'] in verified_ids:
                        raise ValueError('Two requests matched the same AgentRun')
                    verified_ids.add(run['run_id'])
                return result

            checks.update(checked(row, 'ledger', verify_ledger))
        row['checks'] = checks
        row['verification_seconds'] = time.monotonic() - began

    def sample():
        with (args.output / 'resources.jsonl').open('w') as stream:
            while not stop.is_set():
                sample_started = time.monotonic()
                row = {
                    'time': time.time(),
                    'elapsed': time.monotonic() - started,
                    'phase': phase[0],
                    'targets': {},
                    'health': {},
                }
                for name, pid in pids.items():
                    try:
                        row['targets'][name] = read_process_snapshot(pid)
                    except (OSError, RuntimeError) as exc:
                        row['targets'][name] = {'error': str(exc)}
                for name, url in endpoints.items():
                    try:
                        row['health'][name] = read_endpoint_snapshot(url, timeout_seconds=3)
                    except RuntimeError as exc:
                        row['health'][name] = {'error': str(exc)}
                if args.container or args.box_data_root:
                    row.update(sample_containers(args.container, args.box_data_root))
                stream.write(json.dumps(row) + '\n')
                stream.flush()
                with lock:
                    progress = {
                        'elapsed': row['elapsed'],
                        'phase': phase[0],
                        'requests': len(rows),
                        'status': dict(Counter(item['status'] for item in rows)),
                    }
                (args.output / 'progress.json').write_text(json.dumps(progress))
                # Collection time counts toward the three-second sampling cadence.
                stop.wait(max(0, sample_started + 3 - time.monotonic()))

    def execute_request(case, due, *, group=None, arrival=None, offered_slot=None):
        before = time.monotonic()
        row = {
            'case': case['name'],
            'time': time.time(),
            'elapsed': before - started,
            'status': 'failed',
            'schedule_lag_seconds': max(0, before - due),
        }
        if offered_slot is not None:
            row.update(offered_slot=offered_slot, planned_elapsed_seconds=offered_slot / args.rps)
        if group is not None:
            token = uuid.uuid4().hex
            member = f'qa-member-{(group["turn"] - 1) % args.members_per_group:03d}'
            row.update(group_id=group['id'], token=token, member_id=member, turn=group['turn'])
        connection = None
        try:
            connection, after_id = open_ledger()
            dispatch = time.monotonic()
            row.update(
                ledger_setup_seconds=dispatch - before,
                elapsed=dispatch - started,
                schedule_lag_seconds=max(0, dispatch - due),
            )
            if arrival is not None and (dispatch >= deadline or stop.is_set()):
                return None
            if group is not None:
                row['output'] = checked(
                    row,
                    'response',
                    lambda: group_request(case, group['id'], member, group['turn'], token, group['previous']),
                )
                row['seconds'] = time.monotonic() - dispatch
                verify(row, case, connection, after_id, is_group=True)
                row['status'] = 'ok'
            else:
                result = subprocess.run(
                    [args.lbctl, '--config', args.config, '-o', 'json', *case['args']],
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                row['seconds'] = time.monotonic() - dispatch
                row['exit_code'] = result.returncode
                row['output'] = json.loads(redact(result.stdout))
                if not isinstance(row['output'], dict):
                    raise ValueError('CLI response must be an object')
                if result.returncode == 0:
                    checked(row, 'response', lambda: check_response(row['output'].get('data'), case['expect']))
                    verify(row, case, connection, after_id)
                    row['status'] = 'ok'
                elif 'result_unknown' in result.stdout:
                    row['status'] = 'unknown'
                else:
                    row['error'] = redact(result.stderr)[:2000] or 'exit code or response oracle failed'
        except subprocess.TimeoutExpired:
            row.update(status='unknown', error='CLI timed out; server outcome unknown; request was not retried')
        except urllib.error.HTTPError as exc:
            row['error'] = redact(str(exc))
            if group is not None:
                row.update(http_status=exc.code, error=redact(exc.read(2000).decode(errors='replace')))
                if exc.code >= 500:
                    row['status'] = 'unknown'
        except (urllib.error.URLError, TimeoutError) as exc:
            row['error'] = redact(str(exc))
            if group is not None:
                row.update(status='unknown', error=row['error'] + '; not retried')
        except UnresolvedRun as exc:
            row.update(status='unknown', error=str(exc))
        except (OSError, ValueError, KeyError, sqlite3.Error) as exc:
            row['error'] = redact(str(exc))
            if group is not None and isinstance(exc, OSError):
                row['status'] = 'unknown'
        finally:
            if connection:
                connection.close()
        row.setdefault('seconds', time.monotonic() - before)
        if arrival is not None:
            completed = time.monotonic() - started
            row.update(
                arrival_id=arrival['arrival_id'],
                scheduled_elapsed=arrival['scheduled_elapsed'],
                dispatch_elapsed=row['elapsed'],
                completed_elapsed=completed,
                queue_seconds=max(0, row['elapsed'] - arrival['scheduled_elapsed']),
                arrival_seconds=max(0, completed - arrival['scheduled_elapsed']),
            )
        with group_condition:
            rows.append(row)
            with (args.output / 'requests.jsonl').open('a') as stream:
                stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            if group is not None:
                group.update(busy=False, failed=row['status'] != 'ok')
                if row['status'] == 'ok':
                    group.update(turn=group['turn'] + 1, previous=token)
                group['due'] = max(group['due'] + args.groups / args.rps, time.monotonic())
                group_condition.notify_all()
        return row

    def worker(index):
        nonlocal next_case, admitted_requests
        iteration = 0
        due = started + index / args.rps
        while due < deadline:
            pacing_stop = stop if args.max_requests is None else admission_closed
            if pacing_stop.wait(max(0, due - time.monotonic())) or stop.is_set() or time.monotonic() >= deadline:
                break
            with lock:
                if (
                    stop.is_set()
                    or time.monotonic() >= deadline
                    or (args.max_requests is not None and admitted_requests >= args.max_requests)
                ):
                    break
                admitted_requests += 1
                if admitted_requests == args.max_requests:
                    admission_closed.set()
                if args.shared_case_sequence:
                    case = cases[next_case % len(cases)]
                    next_case += 1
                else:
                    case = cases[(iteration * args.workers + index) % len(cases)]
            execute_request(case, due)
            iteration += 1
            due = max(due + args.workers / args.rps, time.monotonic())

    def miss_slots(start, end):
        if start >= end:
            return
        cycle = len(groups)
        loops, rem = divmod(end - start, cycle)
        if loops:
            for group in groups:
                missed_by_case[cases[group['case']]['name']] += loops
        for slot in range(start, start + rem):
            group = groups[slot % cycle]
            missed_by_case[cases[group['case']]['name']] += 1

    def group_worker(_index):
        nonlocal admitted_requests, next_slot
        while not stop.is_set():
            offered_slot = None
            with group_condition:
                while True:
                    now = time.monotonic()
                    if (
                        stop.is_set()
                        or now >= deadline
                        or (args.max_requests is not None and admitted_requests >= args.max_requests)
                    ):
                        return
                    if args.open_loop_groups:
                        if next_slot >= offered_slots:
                            return
                        next_slot, index, missed_start, missed_end, wait = allocate_group_slot(
                            next_slot,
                            now - started,
                            args.rps,
                            offered_slots,
                            [not item['busy'] and not item['failed'] for item in groups],
                        )
                        miss_slots(missed_start, missed_end)
                        if index is None:
                            if next_slot < offered_slots:
                                group_condition.wait(min(wait, max(0, deadline - now)))
                            continue
                        group = groups[index]
                        offered_slot = next_slot - 1
                        group['due'] = started + offered_slot / args.rps
                        group['busy'] = True
                        admitted_requests += 1
                        break
                    available = [group for group in groups if not group['busy'] and not group['failed']]
                    if not available:
                        if not any(group['busy'] for group in groups):
                            return
                        group_condition.wait(0.1)
                        continue
                    group = min(available, key=lambda item: item['due'])
                    if group['due'] > now:
                        group_condition.wait(min(1, group['due'] - now))
                        continue
                    group['busy'] = True
                    admitted_requests += 1
                    if admitted_requests == args.max_requests:
                        group_condition.notify_all()
                    break
            execute_request(cases[group['case']], group['due'], group=group, offered_slot=offered_slot)

    def sampling_guard():
        try:
            sample()
        except Exception as exc:
            sampling_errors.append(f'{type(exc).__name__}: {exc}')
            stop.set()
            admission_closed.set()

    def execute_arrival(item):
        group = groups[item['serialization_key']] if groups else None
        case = cases[group['case']] if group is not None else cases[item['arrival_id'] % len(cases)]
        return execute_request(case, started + item['scheduled_elapsed'], group=group, arrival=item)

    def settle_arrival(item, outcome, row):
        group = groups[item['serialization_key']] if groups else None
        case = cases[group['case']] if group is not None else cases[item['arrival_id'] % len(cases)]
        record = {**item, 'case': case['name'], 'outcome': outcome}
        if group is not None:
            record['group_id'] = group['id']
        if row is not None:
            record.update(
                status=row['status'],
                dispatch_elapsed=row['dispatch_elapsed'],
                completed_elapsed=row['completed_elapsed'],
                queue_seconds=row['queue_seconds'],
                arrival_seconds=row['arrival_seconds'],
            )
        else:
            record['settled_elapsed'] = time.monotonic() - started
            record['reason'] = {
                'dropped': 'client waiting queue full',
                'blocked': 'group has a failed or unknown previous request',
                'expired': 'observation aborted' if stop.is_set() else 'load deadline reached before dispatch',
            }[outcome]
        with (args.output / 'arrivals.jsonl').open('a') as stream:
            stream.write(json.dumps(record, ensure_ascii=False) + '\n')

    arrivals = None
    if args.open_loop_groups or args.arrival_mode == 'open-loop':
        # Schedules start after state/ledger setup, not while files are initialized.
        started = time.monotonic()
        deadline = started + args.duration
    sampler = threading.Thread(target=sampling_guard)
    sampler.start()
    try:
        if args.arrival_mode == 'open-loop':
            from tools.regression.arrival_schedule import run_open_loop

            (args.output / 'requests.jsonl').touch()
            arrivals = run_open_loop(
                started=started,
                duration=args.duration,
                rps=args.rps,
                workers=args.workers,
                queue_capacity=args.queue_capacity,
                execute=execute_arrival,
                key_for=lambda index: index % len(groups) if groups else None,
                blocked=lambda key: groups[key]['failed'] if key is not None else False,
                settle=settle_arrival,
                stop=stop,
            )
        else:
            with ThreadPoolExecutor(max_workers=args.workers) as pool:
                list(pool.map(group_worker if args.groups else worker, range(args.workers)))
        if args.max_requests is None:
            stop.wait(max(0, deadline - time.monotonic()))
        if args.open_loop_groups:
            miss_slots(next_slot, offered_slots)
        load_elapsed = time.monotonic() - started
        phase[0] = 'cooldown'
        stop.wait(args.cooldown)
    finally:
        stop.set()
        sampler.join()
    summary = {
        'duration_requested_seconds': args.duration,
        'load_elapsed_seconds': load_elapsed,
        'target_rps': args.rps,
        'workers': args.workers,
        'cooldown_seconds': args.cooldown,
        'requests': len(rows),
        'request_limit': args.max_requests,
        'successful_requests': sum(row['status'] == 'ok' for row in rows),
        'verified_runs': len(verified_ids),
        'runner_requests': sum(row.get('requires_runner', False) for row in rows),
        'verification_enabled': bool(args.ledger_db),
        'planned_requests': args.max_requests if args.max_requests is not None else math.ceil(args.duration * args.rps),
        'delivery_ratio': len(rows)
        / (args.max_requests if args.max_requests is not None else math.ceil(args.duration * args.rps)),
        'drain_seconds': max(0, load_elapsed - args.duration),
        'schedule_lag_p95_seconds': percentile([row['schedule_lag_seconds'] for row in rows], 0.95),
        'load_model': 'bounded workers; serialized groups; dispatch latency excludes verification',
        'status': dict(Counter(row['status'] for row in rows)),
        'cases': {},
    }
    if arrivals is not None:
        arrivals.update(
            successful=sum(row['status'] == 'ok' for row in rows),
            failed=sum(row['status'] == 'failed' for row in rows),
            unknown=sum(row['status'] == 'unknown' for row in rows),
            queue_p95_seconds=percentile([row['queue_seconds'] for row in rows], 0.95),
            arrival_p95_seconds=percentile([row['arrival_seconds'] for row in rows], 0.95),
            latency_population='all dispatched outcomes, including verification',
        )
        arrivals['conserved'] = arrivals['conserved'] and arrivals['dispatched'] == len(rows)
        summary.update(
            planned_requests=arrivals['scheduled'],
            delivery_ratio=len(rows) / arrivals['scheduled'],
            arrival_mode=args.arrival_mode,
            arrivals=arrivals,
            load_model='fixed arrivals; bounded client queue; serialized groups; arrival latency includes verification',
        )
    if args.open_loop_groups:
        admitted = Counter(row['case'] for row in rows)
        summary.update(
            planned_requests=offered_slots,
            delivery_ratio=len(rows) / offered_slots,
            load_model='open-loop scheduled slots; bounded workers; serialized sessions; missed slots not replayed',
            slot_accounting={
                name: {
                    'offered': admitted[name] + missed_by_case[name],
                    'admitted': admitted[name],
                    'not_admitted': missed_by_case[name],
                }
                for name in dict.fromkeys(case['name'] for case in cases)
            },
        )
    if args.ledger_db:
        conversations.update('group_' + group['id'] for group in groups)
        summary['ledger_closeout'] = reconcile_runs(
            args.ledger_db, args.workspace, phase_start_id, conversations, verified_ids
        )
    samples = [json.loads(line) for line in (args.output / 'resources.jsonl').read_text().splitlines()]
    summary['http_concurrency'] = http_concurrency(rows)
    summary['resource_observations'] = resource_observations(samples)
    summary['health_samples'] = len(samples)
    summary['health_failures'] = sum(
        any('error' in target for target in [*sample['targets'].values(), *sample['health'].values()])
        or bool(sample.get('container_error'))
        for sample in samples
    )
    summary['sampling_errors'] = sampling_errors
    if args.groups:
        for index, group in enumerate(groups):
            group_state['groups'][index] = {key: value for key, value in group.items() if key not in {'due', 'busy'}}
        group_state['in_progress'] = False
        temporary = state_path.with_suffix('.tmp')
        temporary.write_text(json.dumps(group_state, indent=2))
        temporary.chmod(0o600)
        temporary.replace(state_path)
        summary['groups'] = {
            'configured': args.groups,
            'members_per_group': args.members_per_group,
            'target_rps_per_group': args.rps / args.groups,
            'sessions': {
                group['id']: {
                    'case': cases[group['case']]['name'],
                    'successful_turns_total': group['turn'] - 1,
                    'failed': group['failed'],
                    'requests_this_phase': sum(row.get('group_id') == group['id'] for row in rows),
                    'members_this_phase': sorted(
                        {row['member_id'] for row in rows if row.get('group_id') == group['id']}
                    ),
                }
                for group in groups
            },
        }
        if args.open_loop_groups:
            for index, group in enumerate(groups):
                summary['groups']['sessions'][group['id']]['group_index'] = index
        summary['group_failures'] = [
            group_id
            for group_id, result in summary['groups']['sessions'].items()
            if result['failed'] or result['successful_turns_total'] < 2 or not result['requests_this_phase']
        ]
    for name in dict.fromkeys(case['name'] for case in cases):
        selected = [row for row in rows if row['case'] == name]
        times = [row['seconds'] for row in selected if row['status'] == 'ok']
        summary['cases'][name] = {
            'requests': len(selected),
            'status': dict(Counter(row['status'] for row in selected)),
            'p50_seconds': percentile(times, 0.5),
            'p95_seconds': percentile(times, 0.95),
            'p99_seconds': percentile(times, 0.99),
        }
        if arrivals is not None:
            summary['cases'][name].update(
                arrival_p95_seconds=percentile([row['arrival_seconds'] for row in selected], 0.95),
                queue_p95_seconds=percentile([row['queue_seconds'] for row in selected], 0.95),
                arrival_latency_count=len(selected),
                arrival_latency_population='all dispatched outcomes, including verification',
            )
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)
    if (
        not rows
        or (
            not args.open_loop_groups
            and args.max_requests is not None
            and (len(rows) != args.max_requests or load_elapsed > args.duration)
        )
        or any(row['status'] != 'ok' for row in rows)
        or summary['health_failures']
        or sampling_errors
        or (
            arrivals is not None
            and (not arrivals['conserved'] or any(arrivals[name] for name in ('dropped', 'expired', 'blocked')))
        )
        or summary.get('group_failures')
        or (args.ledger_db and not summary['ledger_closeout']['matched'])
    ):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
