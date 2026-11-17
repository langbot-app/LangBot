"""Repeat explicit Skill Artifact pytest scenarios; never count skips as acceptance."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import subprocess
import sys
import time
import xml.etree.ElementTree as ET


def report_counts(path: Path) -> dict[str, int]:
    """Count leaf cases to avoid summing nested JUnit suite totals twice."""
    root = ET.parse(path).getroot()
    cases = list(root.iter('testcase'))
    return {
        'tests': len(cases),
        'failures': sum(case.find('failure') is not None for case in cases),
        'errors': sum(case.find('error') is not None for case in cases),
        'skipped': sum(case.find('skipped') is not None for case in cases),
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--duration', type=float, default=3600)
    parser.add_argument('--interval', type=float, default=5)
    parser.add_argument('--timeout', type=float, default=900, help='Maximum seconds per pytest round')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('nodes', nargs='+', help='Exact pytest paths or node IDs for the changed boundary')
    args = parser.parse_args(argv)
    if args.duration <= 0 or args.timeout <= 0 or args.interval < 0:
        parser.error('duration and timeout must be positive; interval must be non-negative')
    if args.output.exists() and any(args.output.iterdir()):
        parser.error('output must be a new or empty directory; existing evidence is never overwritten')
    args.output.mkdir(parents=True, exist_ok=True)
    sha = subprocess.check_output(['git', 'rev-parse', 'HEAD'], text=True).strip()
    dirty = bool(subprocess.check_output(['git', 'status', '--porcelain'], text=True).strip())
    started = time.monotonic()
    round_number = 0
    manifest = args.output / 'rounds.ndjson'
    while time.monotonic() - started < args.duration:
        round_number += 1
        junit = args.output / f'round-{round_number:05d}.xml'
        log = args.output / f'round-{round_number:05d}.log'
        command = [sys.executable, '-m', 'pytest', *args.nodes, '-q', '-rs', f'--junitxml={junit}']
        row = {
            'round': round_number,
            'started_at': dt.datetime.now(dt.timezone.utc).isoformat(),
            'candidate_sha': sha,
            'dirty_checkout': dirty,
            'command': command,
            'log': log.name,
            'junit': junit.name,
        }
        round_started = time.monotonic()
        with log.open('w') as output:
            try:
                result = subprocess.run(command, stdout=output, stderr=subprocess.STDOUT, timeout=args.timeout)
                row['exit_code'] = result.returncode
            except subprocess.TimeoutExpired:
                row['exit_code'] = 124
                row['error'] = 'scenario timeout'
        try:
            counts = report_counts(junit)
            row.update(counts)
            passed = (
                row['exit_code'] == 0
                and counts['tests'] > 0
                and not any(counts[key] for key in ('failures', 'errors', 'skipped'))
            )
        except (OSError, ET.ParseError) as exc:
            row['error'] = f'Invalid or missing JUnit report: {type(exc).__name__}'
            passed = False
        row['elapsed_seconds'] = round(time.monotonic() - round_started, 3)
        row['status'] = 'passed' if passed else 'failed'
        with manifest.open('a') as output:
            output.write(json.dumps(row) + '\n')
        print(json.dumps(row), flush=True)
        if not passed:
            return 1
        remaining = args.duration - (time.monotonic() - started)
        if remaining > 0:
            time.sleep(min(args.interval, remaining))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
