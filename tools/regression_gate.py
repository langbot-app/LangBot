#!/usr/bin/env python3
"""Bound a prepared-environment smoke run and record process resource samples."""

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

from regression_suite import Suite, validate
from regression_traffic import read_process_snapshot


def supervise(command, output, budget, pids, env=None):
    output.mkdir(parents=True, exist_ok=False, mode=0o700)
    started = time.monotonic()
    samples, errors = [], []
    timed_out = False
    with (output / 'suite.log').open('w') as log:
        process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT, env=env, start_new_session=True)
        try:
            while process.poll() is None:
                remaining = budget - (time.monotonic() - started)
                if remaining <= 0:
                    timed_out = True
                    os.killpg(process.pid, signal.SIGKILL)
                    process.wait()
                    break
                sample = {'elapsed_seconds': time.monotonic() - started, 'processes': {}}
                for name, pid in pids.items():
                    try:
                        sample['processes'][name] = read_process_snapshot(pid)
                    except (RuntimeError, OSError) as exc:
                        errors.append(f'{name}: {exc}')
                samples.append(sample)
                remaining = budget - (time.monotonic() - started)
                try:
                    process.wait(timeout=max(0, min(1, remaining)))
                except subprocess.TimeoutExpired:
                    pass
        finally:
            if process.poll() is None:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
    elapsed = time.monotonic() - started
    (output / 'resources.jsonl').write_text(''.join(json.dumps(sample) + '\n' for sample in samples))
    summary_path = output / 'suite' / 'summary.json'
    summary = json.loads(summary_path.read_text()) if summary_path.exists() else {}
    result = {
        'passed': process.returncode == 0
        and summary.get('passed') is True
        and elapsed <= budget
        and not timed_out
        and not errors,
        'budget_seconds': budget,
        'elapsed_seconds': elapsed,
        'timed_out': timed_out,
        'exit_code': process.returncode,
        'resource_errors': errors,
        'requests': summary.get('requests'),
        'status': summary.get('status'),
        'stages': summary.get('stages'),
        'resource_peaks': {
            name: {
                metric: max((s['processes'].get(name, {}).get(metric, 0) for s in samples), default=0)
                for metric in ('rss_bytes', 'threads', 'open_fds')
            }
            for name in pids
        },
    }
    (output / 'gate.json').write_text(json.dumps(result, indent=2) + '\n')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    profile = json.loads(args.profile.read_text())
    validate(profile)
    if 'smoke' not in profile:
        parser.error('a smoke profile is required')
    suite = Suite(profile, args.profile.resolve(), args.output / 'suite')
    pids = dict(profile.get('observe', {}).get('pids', {}))
    for name, path in profile.get('observe', {}).get('pid_files', {}).items():
        pids[name] = int(Path(suite.path(path)).read_text().strip())
    result = supervise(
        [
            sys.executable,
            str(Path(__file__).with_name('regression_suite.py')),
            'run',
            '--profile',
            str(args.profile.resolve()),
            '--output',
            str(args.output.resolve() / 'suite'),
        ],
        args.output,
        60,
        pids,
    )
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
