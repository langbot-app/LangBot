#!/usr/bin/env python3
"""Compare compatible load runs and check resource recovery without treating missing data as zero."""

import argparse
import hashlib
import json
import math
import os
import platform
from pathlib import Path
import statistics
import re
from urllib.parse import urlsplit


METRICS = {'rss_bytes', 'open_fds', 'threads', 'processes'}


def validate_resource_limits(limits):
    if (
        not isinstance(limits, dict)
        or not {'warmup_seconds', 'window_seconds', 'min_samples', 'targets'} <= set(limits)
        or limits.keys() - {'warmup_seconds', 'window_seconds', 'min_samples', 'targets', 'containers'}
    ):
        raise ValueError('resource_limits requires warmup_seconds, window_seconds, min_samples and targets')
    for key in ('warmup_seconds', 'window_seconds', 'min_samples'):
        value = limits[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value <= 0:
            raise ValueError(f'resource_limits.{key} must be positive and finite')
    if not isinstance(limits['min_samples'], int) or limits['min_samples'] < 3:
        raise ValueError('resource_limits.min_samples must be an integer >= 3')
    if not isinstance(limits['targets'], dict) or not limits['targets']:
        raise ValueError('resource_limits.targets must contain process targets')
    for name, metrics in limits['targets'].items():
        if not name or not isinstance(metrics, dict) or not metrics or metrics.keys() - METRICS:
            raise ValueError('resource limits support rss_bytes, open_fds, threads and processes')
        if any(
            isinstance(v, bool) or not isinstance(v, (float, int)) or not math.isfinite(v) or v < 0
            for v in metrics.values()
        ):
            raise ValueError('resource growth allowances must be finite and nonnegative')

    if 'containers' in limits:
        values = limits['containers']
        if not isinstance(values, dict) or not values or values.keys() - {'memory_bytes', 'pids', 'count'}:
            raise ValueError('container limits support memory_bytes, pids and count')
        if any(
            isinstance(v, bool) or not isinstance(v, (int, float)) or not math.isfinite(v) or v < 0
            for v in values.values()
        ):
            raise ValueError('container growth allowances must be finite and nonnegative')


def container_metrics(row):
    entries = row.get('containers')
    if not isinstance(entries, list) or not entries or row.get('container_error'):
        return {}
    memory = pids = 0
    units = {'B': 1, 'kB': 1000, 'KiB': 1024, 'MB': 1000**2, 'MiB': 1024**2, 'GB': 1000**3, 'GiB': 1024**3}
    for item in entries:
        match = re.fullmatch(r'([0-9.]+)\s*([A-Za-z]+)', item.get('MemUsage', '').split('/')[0].strip())
        try:
            if match is None:
                return {}
            memory += float(match[1]) * units[match[2]]
            pids += int(item['PIDs'])
        except (ValueError, KeyError, TypeError):
            return {}
    return {'memory_bytes': memory, 'pids': pids, 'count': len(entries)}


def resource_verdict(directory, limits):
    validate_resource_limits(limits)
    rows = [json.loads(line) for line in (Path(directory) / 'resources.jsonl').read_text().splitlines()]
    result = {'errors': [], 'targets': {}, 'limits': limits}
    cooldown = [row for row in rows if row['phase'] == 'cooldown']
    if not cooldown:
        result['errors'].append('No cooldown resource samples; recovery is unknown')
        return result
    end = max(row['elapsed'] for row in cooldown)
    baseline = [
        row
        for row in rows
        if row['phase'] == 'load'
        and limits['warmup_seconds'] <= row['elapsed'] < limits['warmup_seconds'] + limits['window_seconds']
    ]
    tail = [row for row in cooldown if row['elapsed'] >= end - limits['window_seconds']]
    if min(len(baseline), len(tail)) < limits['min_samples']:
        result['errors'].append('Insufficient stable/cooldown samples; resource recovery is unknown')
        return result
    targets = dict(limits['targets'])
    if limits.get('containers'):
        targets['docker_containers'] = limits['containers']
    for name, metrics in targets.items():
        target = result['targets'][name] = {}
        for metric, allowance in metrics.items():

            def value(row):
                source = container_metrics(row) if name == 'docker_containers' else row['targets'].get(name, {})
                return source.get(metric)

            before = [value(row) for row in baseline]
            after = [value(row) for row in tail]
            if any(
                not isinstance(v, (int, float))
                or not math.isfinite(v)
                or v < 0
                or (metric in {'rss_bytes', 'memory_bytes'} and v == 0)
                for v in before + after
            ):
                result['errors'].append(f'{name}/{metric}: missing or invalid samples')
                continue
            initial, final = statistics.median(before), statistics.median(after)
            growth = final - initial
            target[metric] = {
                'baseline_median': initial,
                'cooldown_median': final,
                'growth': growth,
                'allowance': allowance,
            }
            if growth > allowance:
                result['errors'].append(f'{name}/{metric}: retained growth {growth:g} exceeds {allowance:g}')
    return result


def workload_contract(profile, profile_path):
    """Fingerprint stimuli and load geometry, excluding target addresses and generated UUIDs."""
    from regression_suite import resolve

    profile_path = Path(profile_path).resolve()
    variables = {
        **profile.get('vars', {}),
        'profile_dir': str(profile_path.parent),
        **{item['id']: '${' + item['id'] + '}' for item in profile.get('resources', []) if 'id' in item},
        'workspace_uuid': '${workspace_uuid}',
        'group_secret': '${group_secret}',
        'run_dir': '${run_dir}',
    }
    resources = resolve(profile.get('resources', []), variables)
    cases = resolve(profile.get('cases', []), variables)
    for resource in resources:
        for document in resource.get('documents', []):
            path = Path(document['file'])
            path = path if path.is_absolute() else profile_path.parent / path
            document['file'] = {'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
        if resource.get('kind') == 'provider':
            body = resource['body']
            if body.get('base_url'):
                url = urlsplit(body['base_url'])
                body['base_url'] = {'scheme': url.scheme, 'path': url.path, 'query': url.query}
            if 'api_keys' in body:
                body['api_keys'] = '<credentials>'
    for case in cases:
        if 'http_group' in case:
            url = urlsplit(case['http_group']['url'])
            case['http_group']['url'] = {'scheme': url.scheme, 'path': url.path, 'query': url.query}
    contract = {key: profile.get(key) for key in ('phases', 'thresholds', 'resource_limits')}
    contract.update(resources=resources, cases=cases)
    contract['observer_host'] = {'name': platform.node(), 'machine': platform.machine(), 'cpus': os.cpu_count()}
    contract['oracle_sha256'] = {
        name: hashlib.sha256(Path(__file__).with_name(name).read_bytes()).hexdigest()
        for name in ('regression_traffic.py', 'regression_smoke.py', 'regression_analysis.py')
    }
    contract['timing_contract'] = 'dispatch-after-ledger-snapshot-v1'
    contract['verified_runs'] = bool(profile.get('verification'))
    contract['mock_scenarios_sha256'] = hashlib.sha256(
        Path(__file__).with_name('mock_llm_scenarios.json').read_bytes()
    ).hexdigest()
    return contract


def compare(baseline, candidate, *, max_p95_ratio=1.2, min_rps_ratio=0.9, min_requests=30):
    roots = [Path(baseline), Path(candidate)]
    summaries = [json.loads((root / 'summary.json').read_text()) for root in roots]
    contracts = [json.loads((root / 'workload.json').read_text()) for root in roots]
    errors, comparisons = [], []
    plugins = []
    for root in roots:
        environment = root / 'environment.json'
        if not environment.exists():
            errors.append('Plugin dependency evidence is missing')
            continue
        records = json.loads(environment.read_text())['plugins']['plugins']
        plugins.append(
            sorted(
                (item['author'], item['name'], item['version'])
                for item in records
                if item.get('enabled') and item.get('status') == 'initialized'
            )
        )
    if any(not value for value in plugins):
        errors.append('Enabled plugin evidence is empty')
    if len(plugins) == 2 and plugins[0] != plugins[1]:
        errors.append('Enabled plugin versions differ; runs are not comparable')
    if contracts[0] != contracts[1]:
        errors.append('Workload/fixtures/oracles differ; runs are not comparable')
    if not all(summary.get('passed') is True for summary in summaries):
        errors.append('Both runs must pass functional, delivery and resource checks')
    if not all(contract.get('verified_runs') for contract in contracts):
        errors.append('Both runs require ledger verification')
    if errors:
        return {'passed': False, 'errors': errors, 'comparisons': comparisons}
    old_phases, new_phases = summaries[0]['phases'], summaries[1]['phases']
    if not old_phases or not new_phases:
        return {'passed': False, 'errors': ['Measured phases are missing'], 'comparisons': []}
    if [phase['name'] for phase in old_phases] != [phase['name'] for phase in new_phases]:
        return {'passed': False, 'errors': ['Phase sets differ'], 'comparisons': []}
    for old, new in zip(old_phases, new_phases):
        if any(
            phase.get('verification_enabled') is not True
            or phase.get('verified_runs') != phase.get('runner_requests')
            or phase.get('ledger_closeout', {}).get('matched') is not True
            for phase in (old, new)
        ):
            errors.append(f'{new["name"]}: runner reconciliation is incomplete')
            continue
        if any(
            not isinstance(phase.get('achieved_rps'), (int, float))
            or not math.isfinite(phase['achieved_rps'])
            or phase['achieved_rps'] <= 0
            for phase in (old, new)
        ):
            errors.append(f'{new["name"]}: successful throughput is invalid')
            continue
        if not old['cases'] or not new['cases'] or old['cases'].keys() != new['cases'].keys():
            errors.append(f'{new["name"]}: case sets differ')
            continue
        if new['achieved_rps'] < old['achieved_rps'] * min_rps_ratio:
            errors.append(f'{new["name"]}: successful throughput regressed')
        for name, current in new['cases'].items():
            previous = old['cases'][name]
            values = [previous.get('p95_seconds'), current.get('p95_seconds')]
            if min(previous['requests'], current['requests']) < min_requests or any(
                not isinstance(v, (int, float)) or not math.isfinite(v) or v <= 0 for v in values
            ):
                errors.append(f'{new["name"]}/{name}: insufficient samples or invalid P95')
                continue
            ratio = current['p95_seconds'] / previous['p95_seconds']
            comparisons.append(
                {
                    'phase': new['name'],
                    'case': name,
                    'p95_ratio': ratio,
                    'baseline_requests': previous['requests'],
                    'candidate_requests': current['requests'],
                }
            )
            if ratio > max_p95_ratio:
                errors.append(f'{new["name"]}/{name}: P95 regressed by {(ratio - 1) * 100:.1f}%')
    return {
        'passed': not errors,
        'errors': errors,
        'comparisons': comparisons,
        'max_p95_ratio': max_p95_ratio,
        'min_rps_ratio': min_rps_ratio,
        'min_requests': min_requests,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--baseline', type=Path, required=True)
    parser.add_argument('--candidate', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--max-p95-ratio', type=float, default=1.2)
    parser.add_argument('--min-rps-ratio', type=float, default=0.9)
    parser.add_argument('--min-requests', type=int, default=30)
    args = parser.parse_args()
    if (
        not math.isfinite(args.max_p95_ratio)
        or args.max_p95_ratio < 1
        or not 0 < args.min_rps_ratio <= 1
        or args.min_requests < 1
    ):
        parser.error('require finite max-p95-ratio >= 1, min-rps-ratio in (0,1], min-requests >= 1')
    result = compare(
        args.baseline,
        args.candidate,
        max_p95_ratio=args.max_p95_ratio,
        min_rps_ratio=args.min_rps_ratio,
        min_requests=args.min_requests,
    )
    args.output.write_text(json.dumps(result, indent=2) + '\n')
    print(json.dumps(result, indent=2))
    raise SystemExit(0 if result['passed'] else 1)


if __name__ == '__main__':
    main()
