"""Repeat explicit Skill Artifact pytest scenarios; never count skips as acceptance."""

from __future__ import annotations

import argparse
import datetime as dt
import json
import ctypes
import os
import signal
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


_CLEANUP_GRACE_SECONDS = 2.0


def _descendants():
    """Find direct/adopted children; deeper descendants become direct on parent exit."""
    owned = {}
    for path in Path('/proc').glob('[0-9]*/stat'):
        try:
            fields = path.read_text().rsplit(')', 1)[1].split()
            # This supervisor remains alive, so its PID cannot be reused. Do not
            # infer multi-generation ancestry from a non-atomic /proc snapshot.
            if int(fields[1]) == os.getpid():
                owned[int(path.parent.name)] = fields[19]
        except (OSError, ValueError, IndexError):
            continue
    return owned


def _signal_owned(pids, signum):
    for pid, started in pids.items():
        descriptor = None
        try:
            # A pidfd binds signaling to one kernel process, closing the PID-reuse
            # race between checking /proc identity and sending the signal.
            descriptor = os.pidfd_open(pid)
            current = Path(f'/proc/{pid}/stat').read_text().rsplit(')', 1)[1].split()
            if current[19] == started and int(current[1]) == os.getpid():
                signal.pidfd_send_signal(descriptor, signum)
        except (ProcessLookupError, FileNotFoundError):
            pass
        finally:
            if descriptor is not None:
                os.close(descriptor)


def _reap_children():
    """Reap exited direct/adopted children; ECHILD alone proves none remain."""
    while True:
        try:
            pid, _ = os.waitpid(-1, os.WNOHANG)
            if not pid:
                return False
        except ChildProcessError:
            return True


def _cleanup_descendants():
    """Terminate, then kill/reap only this round's owned process tree."""
    leaked = not _reap_children()
    for signum, duration in ((signal.SIGTERM, _CLEANUP_GRACE_SECONDS), (signal.SIGKILL, 2.0)):
        deadline = time.monotonic() + duration
        while True:
            no_children = _reap_children()
            owned = _descendants()
            # A /proc snapshot can miss reparenting during parent exit. Do not
            # treat an empty snapshot as proof while waitpid sees a child.
            if not owned and no_children:
                return leaked
            _signal_owned(owned, signum)
            if time.monotonic() >= deadline:
                break
            time.sleep(0.05)
    raise RuntimeError('Scenario descendants could not be reaped after SIGKILL')


def _supervise(command):
    """Linux subreaper isolates one round, including Core processes calling setsid()."""
    libc = ctypes.CDLL(None, use_errno=True)
    if libc.prctl(36, 1, 0, 0, 0) != 0:  # PR_SET_CHILD_SUBREAPER, scoped to this child.
        raise OSError(ctypes.get_errno(), 'Cannot establish scenario subreaper')
    interrupted = []
    for signum in (signal.SIGINT, signal.SIGTERM):
        signal.signal(signum, lambda sig, _frame: interrupted.append(sig))
    code = 1
    try:
        process = subprocess.Popen(command)
        while process.poll() is None and not interrupted:
            time.sleep(0.05)
        code = 128 + interrupted[0] if interrupted else process.returncode
    finally:
        leaked = _cleanup_descendants()
        if leaked and code == 0:
            print('Scenario left child processes running; cleaned up and failed the round', flush=True)
            code = 1
    return code


def run_scenario(command, output, timeout):
    """Run a bounded round and clean its entire owned tree before returning evidence."""
    if sys.platform != 'linux':
        raise RuntimeError('Skill Artifact soak requires Linux process-tree supervision')
    descriptor = None
    try:
        descriptor = os.pidfd_open(os.getpid())
        signal.pidfd_send_signal(descriptor, 0)
    except (AttributeError, OSError) as exc:
        raise RuntimeError('Skill Artifact soak requires Linux pidfd process supervision') from exc
    finally:
        if descriptor is not None:
            os.close(descriptor)
    interrupted = []
    previous = {}
    process = None
    try:
        for signum in (signal.SIGINT, signal.SIGTERM):
            previous[signum] = signal.signal(signum, lambda sig, _frame: interrupted.append(sig))
        process = subprocess.Popen(
            [sys.executable, str(Path(__file__).resolve()), '--supervise', *command],
            stdout=output,
            stderr=subprocess.STDOUT,
            start_new_session=True,
        )
        deadline = time.monotonic() + timeout
        while process.poll() is None:
            if interrupted:
                return 128 + interrupted[0], 'scenario interrupted'
            if time.monotonic() >= deadline:
                return 124, 'scenario timeout'
            time.sleep(0.05)
        return process.returncode, None
    finally:
        try:
            if process is not None and process.poll() is None:
                # Signal the supervisor only: it owns and reaps even detached descendants.
                process.send_signal(signal.SIGTERM)
                process.wait(timeout=2 * _CLEANUP_GRACE_SECONDS + 5)
        finally:
            for signum, handler in previous.items():
                signal.signal(signum, handler)


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
                row['exit_code'], error = run_scenario(command, output, args.timeout)
                if error:
                    row['error'] = error
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                row['exit_code'] = 1
                row['error'] = f'Scenario supervision failed: {type(exc).__name__}'
        try:
            counts = report_counts(junit)
            row.update(counts)
            passed = (
                row['exit_code'] == 0
                and counts['tests'] > 0
                and not any(counts[key] for key in ('failures', 'errors', 'skipped'))
            )
        except (OSError, ET.ParseError) as exc:
            row['report_error'] = f'Invalid or missing JUnit report: {type(exc).__name__}'
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
    if len(sys.argv) > 1 and sys.argv[1] == '--supervise':
        raise SystemExit(_supervise(sys.argv[2:]))
    raise SystemExit(main())
