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
    uv run --no-sync python -m tools.entrypoints.gc_baseline measure --profile core --samples 5
    uv run --no-sync python -m tools.entrypoints.gc_baseline compare before.json after.json

``--json`` writes the same data for comparison between runs. A baseline is a
measurement, not a regression gate: compare two outputs rather than gates on one.
This tool measures controlled offline heap scans rather than live request-window
natural GC frequency; ``gc.freeze()`` is a diagnostic, not a production setting.
"""

import argparse
import gc
import importlib
import json
import platform
import statistics
import sys
import time
import types
from collections import Counter
from pathlib import Path


# Objects survive in surprising volume right after interpreter startup; a
# measurement taken before this floor is mostly boilerplate.
_MIN_SAMPLES = 1
_DEFAULT_PROFILES_PATH = Path(__file__).resolve().parents[1] / 'profiles' / 'gc-baseline.json'
_REPO_SRC_PATH = str(Path(__file__).resolve().parents[2] / 'src')


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


def function_module_histogram(limit=15):
    """Return the most common defining modules for tracked Python functions."""
    counter = Counter()
    for obj in gc.get_objects():
        if type(obj) is types.FunctionType:
            counter[getattr(obj, '__module__', None) or '<unknown>'] += 1
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
        result = scan_cost(samples)
        result['frozen_objects'] = gc.get_freeze_count()
        return result
    finally:
        gc.unfreeze()


def saveall_type_sample():
    """Collect unreachable-object types with ``DEBUG_SAVEALL``.

    ``DEBUG_SAVEALL`` keeps everything in ``gc.garbage`` instead of freeing it,
    so its timings are not comparable to a normal scan and are reported apart.
    The garbage list is cleared and collected before returning so sampled cycles
    are actually reclaimed rather than left behind for later phases.
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
            'duration_ms': round(elapsed, 3),
            'collected': len(gc.garbage),
            'top_types': dict(histogram.most_common(15)),
            'note': 'DEBUG_SAVEALL timings are not comparable to normal scans',
        }
    finally:
        gc.garbage.clear()
        if not (previous & gc.DEBUG_SAVEALL):
            gc.collect(2)


def load_profiles(profiles_path=_DEFAULT_PROFILES_PATH):
    """Load named module profiles from ``gc-baseline.json``."""
    data = json.loads(Path(profiles_path).read_text(encoding='utf-8'))
    profiles = data.get('profiles')
    if not isinstance(profiles, dict):
        raise ValueError(f'invalid profiles file: {profiles_path}')
    return profiles


def resolve_preload_modules(profile_name=None, extra_modules=(), profiles_path=_DEFAULT_PROFILES_PATH):
    """Resolve a profile name plus extra ``--load`` modules in deduplicated order."""
    modules = []
    if profile_name is not None:
        profiles = load_profiles(profiles_path)
        if profile_name not in profiles:
            available = ', '.join(sorted(profiles))
            raise ValueError(f'unknown profile {profile_name!r}; available: {available}')
        profile_modules = profiles[profile_name].get('modules', [])
        if not isinstance(profile_modules, list):
            raise ValueError(f'profile {profile_name!r} modules must be a list')
        modules.extend(profile_modules)
    modules.extend(extra_modules)
    return list(dict.fromkeys(modules))


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
    if _REPO_SRC_PATH not in sys.path:
        sys.path.insert(0, _REPO_SRC_PATH)
    profile_name = getattr(args, 'profile', None)
    profiles_path = getattr(args, 'profiles_file', _DEFAULT_PROFILES_PATH)
    modules = resolve_preload_modules(profile_name, args.load, profiles_path)
    preload_result = preload(modules)
    preload_result['profile'] = profile_name
    report = {
        'preload': preload_result,
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
        'top_function_modules': function_module_histogram(),
    }

    report['scan'] = scan_cost(args.samples)
    report['frozen_scan'] = freeze_attribution(args.samples)

    frozen_median = report['frozen_scan']['median_ms']
    baseline = report['scan']['median_ms']
    report['attribution'] = {
        'scan_median_ms': baseline,
        'frozen_median_ms': frozen_median,
        'scan_share_pct': (round((baseline - frozen_median) / baseline * 100.0, 1) if baseline > 0 else None),
        'interpretation': 'share of scan cost attributable to the pre-existing object population',
    }

    return report


def summarize(report):
    """Render the report for a human, with the caveats inline."""
    profile_name = report['preload'].get('profile')
    lines = [
        f'python {report["platform"]["python"]} on {report["platform"]["system"]}/{report["platform"]["machine"]}',
        f'gc enabled: {report["enabled"]}  thresholds: {report["thresholds"]}',
        '',
        f'profile: {profile_name or "(custom/none)"}',
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
    top_fn_modules = report['objects'].get('top_function_modules') or {}
    if top_fn_modules:
        lines += [
            '',
            'Top function modules:',
            *[f'  {name}: {count}' for name, count in top_fn_modules.items()],
        ]
    if 'saveall' in report:
        saveall = report['saveall']
        duration = saveall.get('duration_ms', saveall.get('durations_ms'))
        lines += [
            '',
            f'DEBUG_SAVEALL: {saveall["collected"]} unreachable objects, {duration} ms (timing not comparable)',
            *[f'  {name}: {count}' for name, count in saveall.get('top_types', {}).items()],
        ]
    return '\n'.join(lines)


def _metric_delta(before_value, after_value, digits=3):
    if before_value is None or after_value is None:
        return {'before': before_value, 'after': after_value, 'delta': None, 'delta_pct': None}
    delta = round(after_value - before_value, digits)
    delta_pct = round((after_value - before_value) / before_value * 100.0, 1) if before_value else None
    return {'before': before_value, 'after': after_value, 'delta': delta, 'delta_pct': delta_pct}


def _histogram_deltas(before_map, after_map, limit=10):
    deltas = []
    for name in set(before_map) | set(after_map):
        before_count = before_map.get(name)
        after_count = after_map.get(name)
        if before_count is not None and after_count is not None:
            diff = after_count - before_count
            if diff != 0:
                deltas.append({'name': name, 'before': before_count, 'after': after_count, 'delta': diff})
        else:
            deltas.append({'name': name, 'before': before_count, 'after': after_count, 'delta': None})
    deltas.sort(
        key=lambda item: (
            0 if item['delta'] is not None else 1,
            -abs(item['delta']) if item['delta'] is not None else -max(item['before'] or 0, item['after'] or 0),
            item['name'],
        )
    )
    return deltas[:limit]


def compare_reports(before, after):
    """Compare two ``gc_baseline measure --json`` reports and flag context mismatches."""
    warnings = []
    if before.get('platform') != after.get('platform'):
        warnings.append('platform differs between before and after; timings are not directly comparable')
    before_preload = before.get('preload', {})
    after_preload = after.get('preload', {})
    if before_preload.get('profile') != after_preload.get('profile'):
        warnings.append(
            f'profile differs: before={before_preload.get("profile")!r} after={after_preload.get("profile")!r}'
        )
    if before_preload.get('loaded') != after_preload.get('loaded'):
        warnings.append('preloaded module lists differ between before and after')
    if before_preload.get('failed') or after_preload.get('failed'):
        warnings.append('one or both runs reported preload failures')

    return {
        'before_profile': before_preload.get('profile'),
        'after_profile': after_preload.get('profile'),
        'warnings': warnings,
        'metrics': {
            'tracked_objects': _metric_delta(
                before['objects']['tracked'],
                after['objects']['tracked'],
                digits=0,
            ),
            'scan_median_ms': _metric_delta(before['scan']['median_ms'], after['scan']['median_ms']),
            'frozen_median_ms': _metric_delta(before['frozen_scan']['median_ms'], after['frozen_scan']['median_ms']),
            'scan_share_pct': _metric_delta(
                before['attribution'].get('scan_share_pct'),
                after['attribution'].get('scan_share_pct'),
                digits=1,
            ),
        },
        'top_type_deltas': _histogram_deltas(
            before['objects'].get('top_types', {}),
            after['objects'].get('top_types', {}),
        ),
        'top_function_module_deltas': _histogram_deltas(
            before['objects'].get('top_function_modules', {}),
            after['objects'].get('top_function_modules', {}),
        ),
    }


def summarize_comparison(comparison):
    """Render a comparison of two GC baseline reports."""
    lines = [
        f'profile: before={comparison["before_profile"] or "(custom/none)"}  '
        f'after={comparison["after_profile"] or "(custom/none)"}',
    ]
    for warning in comparison['warnings']:
        lines.append(f'WARNING: {warning}')
    lines.append('')
    for key, label in (
        ('tracked_objects', 'tracked objects'),
        ('scan_median_ms', 'full scan median (ms)'),
        ('frozen_median_ms', 'frozen scan median (ms)'),
        ('scan_share_pct', 'existing-heap share (%)'),
    ):
        item = comparison['metrics'][key]
        pct = f' ({item["delta_pct"]:+.1f}%)' if item['delta_pct'] is not None else ''
        delta = f'{item["delta"]:+}' if item['delta'] is not None else 'n/a'
        lines.append(f'{label}: {item["before"]} -> {item["after"]} (delta {delta}{pct})')
    if comparison['top_type_deltas']:
        lines += [
            '',
            'Top tracked type deltas:',
            *[_format_histogram_delta(entry) for entry in comparison['top_type_deltas']],
        ]
    if comparison['top_function_module_deltas']:
        lines += [
            '',
            'Top function module deltas:',
            *[_format_histogram_delta(entry) for entry in comparison['top_function_module_deltas']],
        ]
    return '\n'.join(lines)


def _format_histogram_delta(entry):
    before = entry['before'] if entry['before'] is not None else 'outside top-N'
    after = entry['after'] if entry['after'] is not None else 'outside top-N'
    if entry['delta'] is None:
        return f'  {entry["name"]}: {before} -> {after}'
    return f'  {entry["name"]}: {before} -> {after} ({entry["delta"]:+d})'


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
        '--profile',
        default=None,
        metavar='NAME',
        help='preload a named module set from tools/profiles/gc-baseline.json',
    )
    measure.add_argument(
        '--profiles-file',
        type=Path,
        default=_DEFAULT_PROFILES_PATH,
        metavar='PATH',
        help='override the profiles JSON path (default: tools/profiles/gc-baseline.json)',
    )
    measure.add_argument(
        '--load',
        action='append',
        default=[],
        metavar='MODULE',
        help='import MODULE before measuring (repeatable); see tools/profiles/gc-baseline.json',
    )
    measure.add_argument('--json', action='store_true', help='emit JSON instead of a text summary')

    compare = subparsers.add_parser('compare', help='compare two measure --json reports')
    compare.add_argument('before', type=Path, help='baseline JSON report path')
    compare.add_argument('after', type=Path, help='candidate JSON report path')
    compare.add_argument('--json', action='store_true', help='emit JSON instead of a text summary')

    args = parser.parse_args(argv)

    if args.command == 'measure':
        try:
            report = build_report(args)
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            parser.error(str(exc))
        print(json.dumps(report, indent=2) if args.json else summarize(report))
        return 0

    try:
        before = json.loads(args.before.read_text(encoding='utf-8'))
        after = json.loads(args.after.read_text(encoding='utf-8'))
        comparison = compare_reports(before, after)
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
        parser.error(str(exc))
    print(json.dumps(comparison, indent=2) if args.json else summarize_comparison(comparison))
    return 0


if __name__ == '__main__':
    sys.exit(main())
