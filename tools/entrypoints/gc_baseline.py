#!/usr/bin/env python3
"""Measure GC pressure so a performance claim can be re-run instead of trusted.

The GC section of langbot-app/LangBot#2852 was produced with an ad-hoc script
that was never committed, so its numbers cannot be reproduced. This tool is that
method in the repo: it counts GC-tracked objects, measures full-generation scan
cost, and attributes cost to a cause with ``gc.freeze()``.

Every phase keeps only scalars. Holding object references between phases shifts
the very counters being measured, so types are summarized as counts and dropped.
``gc.DEBUG_SAVEALL`` is opt-in and its timings are reported separately, because
it changes what the collector does.

Run from the repository root:

    uv run --no-sync python -m tools.entrypoints.gc_baseline --help
    uv run --no-sync python -m tools.entrypoints.gc_baseline measure --samples 5

``--json`` writes the same data for comparison between runs. A baseline is a
measurement, not a regression gate: compare two outputs rather than gates on one.
"""

import argparse
import gc
import importlib
import json
import platform
import statistics
import sys
import time
from collections import Counter
from pathlib import Path


# Objects survive in surprising volume right after interpreter startup; a
# measurement taken before this floor is mostly boilerplate.
_MIN_SAMPLES = 1


def collect(scopes):
    """Run ``gc.collect(2)`` and report duration plus collected counts."""
    start = time.perf_counter()
    collected = gc.collect(scopes)
    return (time.perf_counter() - start) * 1000.0, collected


def tracked_object_count():
    """Count tracked objects without retaining them."""
    return len(gc.get_objects())


def object_type_histogram(limit=15):
    """Return the most common tracked types as ``{module.qualname: count}``."""
    counter = Counter()
    for obj in gc.get_objects():
        kind = type(obj)
        counter[f'{kind.__module__}.{kind.__qualname__}'] += 1
    return dict(counter.most_common(limit))


def generation_counts():
    return {str(gen): len(gc.get_objects(gen)) for gen in (0, 1, 2)}


def scan_cost(samples):
    """Time repeated full collections on an already-warm heap.

    Collection cost here is dominated by scanning long-lived objects; a run with
    ``collected == 0`` still pays it. That is the point of the measurement.
    """
    durations = []
    collected_total = 0
    for _ in range(samples):
        elapsed, collected = collect(2)
        durations.append(elapsed)
        collected_total += collected
    return {
        'samples': samples,
        'durations_ms': [round(value, 3) for value in durations],
        'median_ms': round(statistics.median(durations), 3),
        'min_ms': round(min(durations), 3),
        'max_ms': round(max(durations), 3),
        'collected_total': collected_total,
    }


def freeze_attribution(samples):
    """Measure scan cost with the existing heap moved out of the scan.

    ``gc.freeze()`` parks current objects in a permanent generation. The delta
    against a normal scan attributes cost to scanning that population. It is a
    diagnostic, not a production configuration: thawing semantics and long-lived
    object lifetimes are not exercised.
    """
    gc.collect(2)
    gc.freeze()
    try:
        return scan_cost(samples)
    finally:
        gc.unfreeze()


def saveall_type_sample():
    """Collect unreachable-object types with ``DEBUG_SAVEALL``.

    ``DEBUG_SAVEALL`` keeps everything in ``gc.garbage`` instead of freeing it,
    so its timings are not comparable to a normal scan and are reported apart.
    The garbage list is cleared before returning to avoid changing later phases.
    """
    previous = gc.get_debug()
    # DEBUG_SAVEALL must be on *before* collecting: an earlier normal collection
    # would already have freed the unreachable objects this phase wants to sample.
    gc.set_debug(gc.DEBUG_SAVEALL)
    start = time.perf_counter()
    try:
        gc.collect(2)
    finally:
        gc.set_debug(previous)
        elapsed = (time.perf_counter() - start) * 1000.0
    try:
        histogram = Counter(f'{type(obj).__module__}.{type(obj).__qualname__}' for obj in gc.garbage)
        return {
            'durations_ms': round(elapsed, 3),
            'collected': len(gc.garbage),
            'top_types': dict(histogram.most_common(15)),
            'note': 'DEBUG_SAVEALL timings are not comparable to normal scans',
        }
    finally:
        gc.garbage.clear()


def preload(modules):
    """Import module names before measuring, returning the ones that loaded.

    ``langbot.pkg.core.app`` alone pulls in the adapter, provider and ORM stack,
    which is where the object population actually comes from. A measurement on a
    bare interpreter only sees interpreter boilerplate.
    """
    loaded, failed = [], []
    for name in modules:
        try:
            importlib.import_module(name)
        except Exception as exc:  # noqa: BLE001 - report, do not abort the run
            failed.append({'module': name, 'error': f'{type(exc).__name__}: {exc}'})
        else:
            loaded.append(name)
    return {'loaded': loaded, 'failed': failed}


def build_report(args):
    """Run every requested phase and return scalars only."""
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'src'))
    report = {
        'preload': preload(args.load),
        'platform': {
            'python': platform.python_version(),
            'implementation': platform.python_implementation(),
            'system': platform.system(),
            'machine': platform.machine(),
        },
        'thresholds': gc.get_threshold(),
        'counts': gc.get_count(),
        'enabled': gc.isenabled(),
    }

    # Sample unreachable objects before the settling collect below, otherwise it
    # has already freed everything this phase wants to name.
    if args.saveall:
        report['saveall'] = saveall_type_sample()

    gc.collect(2)
    report['objects'] = {
        'tracked': tracked_object_count(),
        'by_generation': generation_counts(),
        'top_types': object_type_histogram(),
    }

    report['scan'] = scan_cost(args.samples)
    report['frozen_scan'] = freeze_attribution(args.samples)

    thawed = report['frozen_scan']['median_ms']
    baseline = report['scan']['median_ms']
    report['attribution'] = {
        'scan_median_ms': baseline,
        'frozen_median_ms': thawed,
        'scan_share_pct': (round((baseline - thawed) / baseline * 100.0, 1) if baseline > 0 else None),
        'interpretation': 'share of scan cost attributable to the pre-existing object population',
    }

    return report


def summarize(report):
    """Render the report for a human, with the caveats inline."""
    lines = [
        f'python {report["platform"]["python"]} on {report["platform"]["system"]}/{report["platform"]["machine"]}',
        f'gc enabled: {report["enabled"]}  thresholds: {report["thresholds"]}',
        '',
        f'preloaded: {", ".join(report["preload"]["loaded"]) or "(nothing)"}',
        *[f'  FAILED {item["module"]}: {item["error"]}' for item in report['preload']['failed']],
        '',
        f'tracked objects: {report["objects"]["tracked"]}',
        f'by generation: {report["objects"]["by_generation"]}',
        '',
        f'full scan (n={report["scan"]["samples"]}): median '
        f'{report["scan"]["median_ms"]} ms, collected {report["scan"]["collected_total"]}',
        f'frozen scan (n={report["frozen_scan"]["samples"]}): median {report["frozen_scan"]["median_ms"]} ms',
    ]
    share = report['attribution']['scan_share_pct']
    if share is not None:
        lines.append(f'scan cost attributable to the existing heap: {share}%')
    lines += [
        '',
        'Top tracked types:',
        *[f'  {name}: {count}' for name, count in report['objects']['top_types'].items()],
    ]
    if 'saveall' in report:
        lines += [
            '',
            f'DEBUG_SAVEALL: {report["saveall"]["collected"]} unreachable objects, '
            f'{report["saveall"]["durations_ms"]} ms (timing not comparable)',
        ]
    return '\n'.join(lines)


def positive_int(text):
    value = int(text)
    if value < _MIN_SAMPLES:
        raise argparse.ArgumentTypeError(f'must be >= {_MIN_SAMPLES}')
    return value


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    subparsers = parser.add_subparsers(dest='command', required=True)
    measure = subparsers.add_parser('measure', help='run the measurement phases')
    measure.add_argument('--samples', type=positive_int, default=3, help='collections per scan phase (default: 3)')
    measure.add_argument(
        '--saveall',
        action='store_true',
        help='also sample unreachable-object types (reports 0 on a freshly imported, cycle-free heap)',
    )
    measure.add_argument(
        '--load',
        action='append',
        default=[],
        metavar='MODULE',
        help='import MODULE before measuring (repeatable); see tools/profiles/gc-baseline.json',
    )
    measure.add_argument('--json', action='store_true', help='emit JSON instead of a text summary')
    args = parser.parse_args(argv)

    report = build_report(args)
    print(json.dumps(report, indent=2) if args.json else summarize(report))
    return 0


if __name__ == '__main__':
    sys.exit(main())
