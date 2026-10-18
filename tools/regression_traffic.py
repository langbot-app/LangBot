#!/usr/bin/env python3
"""Drive normal lbctl traffic and retain business checks, health and Linux resources."""

import argparse
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import threading
import time

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'scripts'))
from cloud_runtime_soak import read_endpoint_snapshot, read_process_snapshot


def percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--lbctl', required=True)
    parser.add_argument('--config', required=True)
    parser.add_argument('--cases', type=Path, required=True, help='JSON array of {name, args, expect}')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--duration', type=float, default=600)
    parser.add_argument('--rps', type=float, default=2)
    parser.add_argument('--workers', type=int, default=4)
    parser.add_argument('--cooldown', type=float, default=30)
    parser.add_argument('--pid', action='append', default=[], metavar='NAME=PID')
    parser.add_argument('--health', action='append', default=[], metavar='NAME=URL')
    parser.add_argument('--container', action='append', default=[])
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
    cases = json.loads(args.cases.read_text())
    if (
        not isinstance(cases, list)
        or not cases
        or any(
            not isinstance(case, dict)
            or not isinstance(case.get('name'), str)
            or not isinstance(case.get('args'), list)
            or not all(isinstance(item, str) for item in case['args'])
            or not isinstance(case.get('expect'), str)
            or not case['expect']
            for case in cases
        )
    ):
        parser.error('cases must contain name, string args, and expected response text')
    args.output.mkdir(parents=True, exist_ok=False)
    pids = {name: int(pid) for name, pid in (value.split('=', 1) for value in args.pid)}
    endpoints = dict(value.split('=', 1) for value in args.health)
    rows = []
    sampling_errors = []
    lock = threading.Lock()
    stop = threading.Event()
    phase = ['load']
    next_case = 0
    started = time.monotonic()
    deadline = started + args.duration
    redactions = [value for name, value in os.environ.items() if 'API_KEY' in name and value]

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
                if args.container:
                    result = subprocess.run(
                        ['docker', 'stats', '--no-stream', '--format', '{{json .}}', *args.container],
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
            list(pool.map(worker, range(args.workers)))
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
    if not rows or any(row['status'] != 'ok' for row in rows) or summary['health_failures'] or sampling_errors:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
