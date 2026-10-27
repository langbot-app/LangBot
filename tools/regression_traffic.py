#!/usr/bin/env python3
"""Drive independent CLI requests or persistent group conversations with Linux resource sampling."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import hashlib
import hmac
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cloud_runtime_soak import read_endpoint_snapshot, read_process_snapshot


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def owned_box_containers(data_root, checked=None):
    """Discover sandboxes mounted below one run's data root, including newly created groups."""
    if checked is None:

        def checked(command):
            return subprocess.check_output(command, text=True, timeout=10)

    candidates = checked(['docker', 'ps', '-a', '--filter', 'label=langbot.box=true', '--format', '{{.ID}}']).split()
    if not candidates:
        return []
    root = Path(data_root).resolve()
    descriptions = checked(['docker', 'inspect', '--format', '{{json .}}', *candidates])
    owned = []
    for line in descriptions.splitlines():
        if not line:
            continue
        entry = json.loads(line)
        if any(
            Path(mount['Source']).resolve().is_relative_to(root) for mount in entry['Mounts'] if mount.get('Source')
        ):
            owned.append(entry['Id'])
    return owned


def group_request(case, group_id, member_id, turn, token, previous, env=None):
    """Send one signed GroupMessage through the existing HTTP Bot adapter."""
    settings = case['http_group']
    secret = (os.environ if env is None else env)[settings['secret_env']]
    marker = f'LB_GROUP={group_id} LB_TURN={turn} LB_TOKEN={token} LB_PREVIOUS={previous}'
    body = json.dumps(
        {
            'session_id': group_id,
            'session_type': 'group',
            'sender': {'id': member_id, 'name': member_id, 'group_name': group_id},
            'message': [{'type': 'Plain', 'text': settings['message'] + ' ' + marker}],
        }
    ).encode()
    stamp = str(int(time.time()))
    signature = hmac.new(secret.encode(), stamp.encode() + b'.' + body, hashlib.sha256).hexdigest()
    request = urllib.request.Request(
        settings['url'],
        data=body,
        headers={
            'Content-Type': 'application/json',
            'X-LB-Timestamp': stamp,
            'X-LB-Signature': 'sha256=' + signature,
            'X-LB-Idempotency-Key': token,
        },
    )
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}))
    with opener.open(request, timeout=90) as response:
        payload = json.load(response)
        if response.status != 200 or not isinstance(payload, dict) or payload.get('code') != 0:
            raise ValueError('group ingress did not return a completed response')
    data = payload.get('data', {})
    if not isinstance(data, dict):
        raise ValueError('group ingress response data must be an object')
    parts = data.get('message')
    if not isinstance(parts, list) or any(not isinstance(part, dict) for part in parts):
        raise ValueError('group reply must contain message components')
    text = ''.join(str(part.get('text', '')) for part in parts if part.get('type') == 'Plain')
    if data.get('session_id') != group_id or not data.get('reply_to'):
        raise ValueError('group reply session or message correlation is missing')
    if case['expect'] not in text or f'GROUP_ACK={token}' not in text:
        raise ValueError('group reply failed its business or conversation-history oracle')
    return payload


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
    parser.add_argument(
        '--groups', type=int, default=0, help='Stable group sessions; zero uses independent CLI requests'
    )
    parser.add_argument('--members-per-group', type=int, default=3)
    parser.add_argument(
        '--group-state', type=Path, help='Carry group histories across load phases; refuses interrupted runs'
    )
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
                not isinstance(settings, dict)
                or set(settings) != {'url', 'secret_env', 'message'}
                or not all(isinstance(value, str) and value for value in settings.values())
                or not settings['url'].startswith(('http://', 'https://'))
                or not os.environ.get(settings['secret_env'])
            ):
                parser.error('group cases need HTTP(S) url, message and a populated secret_env')
    args.output.mkdir(parents=True, exist_ok=False)
    pids = {name: int(pid) for name, pid in (value.split('=', 1) for value in args.pid)}
    endpoints = dict(value.split('=', 1) for value in args.health)
    rows = []
    sampling_errors = []
    lock = threading.Lock()
    group_condition = threading.Condition(lock)
    stop = threading.Event()
    phase = ['load']
    next_case = 0
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

    def sample():
        with (args.output / 'resources.jsonl').open('w') as stream:
            while not stop.is_set():
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
                containers = set(args.container)
                if args.box_data_root:
                    containers.update(owned_box_containers(args.box_data_root))
                if containers:
                    result = subprocess.run(
                        ['docker', 'stats', '--no-stream', '--format', '{{json .}}', *sorted(containers)],
                        capture_output=True,
                        text=True,
                        timeout=10,
                    )
                    row['containers'] = [json.loads(line) for line in result.stdout.splitlines() if line]
                    if result.returncode:
                        row['container_error'] = result.stderr.strip()
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
                stop.wait(3)

    def worker(index):
        nonlocal next_case
        iteration = 0
        due = started + index / args.rps
        while due < deadline:
            if stop.wait(max(0, due - time.monotonic())) or time.monotonic() >= deadline:
                break
            if args.shared_case_sequence:
                with lock:
                    case = cases[next_case % len(cases)]
                    next_case += 1
            else:
                case = cases[(iteration * args.workers + index) % len(cases)]
            before = time.monotonic()
            row = {'case': case['name'], 'time': time.time(), 'elapsed': before - started, 'status': 'failed'}
            try:
                result = subprocess.run(
                    [args.lbctl, '--config', args.config, '-o', 'json', *case['args']],
                    capture_output=True,
                    text=True,
                    timeout=90,
                )
                row['exit_code'] = result.returncode
                row['output'] = json.loads(redact(result.stdout))
                if result.returncode == 0 and case['expect'] in json.dumps(row['output'], ensure_ascii=False):
                    row['status'] = 'ok'
                elif 'result_unknown' in result.stdout:
                    row['status'] = 'unknown'
                else:
                    row['error'] = redact(result.stderr)[:2000] or 'exit code or response oracle failed'
            except subprocess.TimeoutExpired:
                row.update(status='unknown', error='CLI timed out; server outcome unknown; request was not retried')
            except (OSError, ValueError) as exc:
                row['error'] = str(exc)
            row['seconds'] = time.monotonic() - before
            with lock:
                rows.append(row)
                with (args.output / 'requests.jsonl').open('a') as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + '\n')
            iteration += 1
            due = max(due + args.workers / args.rps, time.monotonic())

    def group_worker(_index):
        while not stop.is_set():
            with group_condition:
                while True:
                    now = time.monotonic()
                    if stop.is_set() or now >= deadline:
                        return
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
                    break
            case = cases[group['case']]
            before = time.monotonic()
            token = uuid.uuid4().hex
            member = f'qa-member-{(group["turn"] - 1) % args.members_per_group:03d}'
            row = {
                'case': case['name'],
                'group_id': group['id'],
                'member_id': member,
                'turn': group['turn'],
                'time': time.time(),
                'elapsed': before - started,
                'status': 'failed',
            }
            try:
                row['output'] = group_request(case, group['id'], member, group['turn'], token, group['previous'])
                row['status'] = 'ok'
            except urllib.error.HTTPError as exc:
                row.update(http_status=exc.code, error=redact(exc.read(2000).decode(errors='replace')))
                if exc.code >= 500:
                    row['status'] = 'unknown'
            except (urllib.error.URLError, TimeoutError, OSError) as exc:
                row.update(status='unknown', error=redact(str(exc)) + '; not retried')
            except (ValueError, KeyError) as exc:
                row['error'] = redact(str(exc))
            row['seconds'] = time.monotonic() - before
            with group_condition:
                rows.append(row)
                with (args.output / 'requests.jsonl').open('a') as stream:
                    stream.write(json.dumps(row, ensure_ascii=False) + '\n')
                group.update(busy=False, failed=row['status'] != 'ok')
                if row['status'] == 'ok':
                    group.update(turn=group['turn'] + 1, previous=token)
                group['due'] = max(group['due'] + args.groups / args.rps, time.monotonic())
                group_condition.notify_all()

    def sampling_guard():
        try:
            sample()
        except Exception as exc:
            sampling_errors.append(f'{type(exc).__name__}: {exc}')
            stop.set()

    sampler = threading.Thread(target=sampling_guard)
    sampler.start()
    try:
        with ThreadPoolExecutor(max_workers=args.workers) as pool:
            list(pool.map(group_worker if args.groups else worker, range(args.workers)))
        stop.wait(max(0, deadline - time.monotonic()))
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
        'status': dict(Counter(row['status'] for row in rows)),
        'cases': {},
    }
    samples = [json.loads(line) for line in (args.output / 'resources.jsonl').read_text().splitlines()]
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
    (args.output / 'summary.json').write_text(json.dumps(summary, indent=2))
    print(json.dumps(summary, indent=2), flush=True)
    if (
        not rows
        or any(row['status'] != 'ok' for row in rows)
        or summary['health_failures']
        or sampling_errors
        or summary.get('group_failures')
    ):
        raise SystemExit(1)


if __name__ == '__main__':
    main()
