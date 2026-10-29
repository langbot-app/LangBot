#!/usr/bin/env python3
"""Report explicitly asserted business contracts, independently of pass rate."""

import argparse
import ast
from collections import Counter
import json
import hashlib
import re
from urllib.parse import urlsplit
from pathlib import Path

CATALOG = Path(__file__).with_name('regression_contracts.json')
STATES = ('passed', 'failed', 'incomplete', 'skipped', 'not_run', 'missing_test')


def checked(row, name, action):
    """Record an evaluated assertion; transport failures leave it unverified."""
    assertions = row.setdefault('assertions', {})
    try:
        result = action()
    except ValueError:
        assertions[name] = 'failed'
        raise
    assertions[name] = 'passed'
    return result


def check_response(data, expected, forbidden=()):
    text = json.dumps(data, ensure_ascii=False)
    if expected not in text:
        raise ValueError('Response does not contain the expected business result')
    if any(value in text for value in forbidden):
        raise ValueError('Response contains forbidden content')


def load_catalog(path=CATALOG):
    catalog = json.loads(Path(path).read_text())
    if catalog.get('version') != 1 or not catalog.get('scope'):
        raise ValueError('Coverage catalog requires version 1 and an explicit scope')
    seen = set()
    for item in catalog['contracts']:
        if item['id'] in seen or item['kind'] not in ('blackbox', 'graybox'):
            raise ValueError('Coverage contract IDs must be unique and kinds explicit')
        seen.add(item['id'])
        if not item['description'] or not item['area'] or item['priority'] not in ('P0', 'P1', 'P2'):
            raise ValueError('Coverage contracts require a description, area and priority')
        for binding in item['bindings']:
            if not binding['profile'] or not binding['case'] or not binding['checks']:
                raise ValueError('Coverage bindings require a profile, case and actual assertions')
    return catalog


def collect(directory):
    directory = Path(directory)
    profile = json.loads((directory / 'profile.json').read_text())
    suite = profile.get('coverage_suite', 'unclassified')
    sources = (
        [directory / 'cases.json']
        if 'smoke' in profile
        else [directory / phase['name'] / 'requests.jsonl' for phase in profile.get('phases', [])]
    )
    rows, errors = [], []
    for path in sources:
        if not path.exists():
            errors.append(f'{path}: missing executed-case evidence')
            continue
        try:
            data = (
                [json.loads(line) for line in path.read_text().splitlines()]
                if path.suffix == '.jsonl'
                else json.loads(path.read_text())
            )
            if not isinstance(data, list) or any(
                not isinstance(row, dict)
                or row.get('status') not in ('passed', 'ok', 'failed', 'unknown', 'skipped')
                or not isinstance(row.get('case'), str)
                or not isinstance(row.get('assertions', {}), dict)
                or any(value not in ('passed', 'failed') for value in row.get('assertions', {}).values())
                or not isinstance(row.get('turn', 0), int)
                for row in data
            ):
                raise ValueError('Malformed executed-case evidence')
            if not data:
                errors.append(f'{path}: empty executed-case evidence')
            rows.extend({**row, 'profile': suite, 'source': str(path)} for row in data)
        except (ValueError, OSError) as exc:
            errors.append(f'{path}: {exc}')
    missing = {case['name'] for case in profile.get('cases', [])} - {row['case'] for row in rows}
    if missing:
        errors.append(f'{directory}: no evidence for planned cases: {sorted(missing)}')
    return rows, errors


def route_inventory(catalog, root=None):
    """Discover RouterGroup HTTP declarations; links express test intent, not endpoint hits."""
    root = Path(root) if root else Path(__file__).resolve().parents[1]
    routes, unresolved = [], []
    for path in sorted((root / 'src/langbot/pkg').rglob('*.py')):
        if 'group_class' not in path.read_text():
            continue
        tree = ast.parse(path.read_text())
        for cls in (node for node in ast.walk(tree) if isinstance(node, ast.ClassDef)):
            groups = [
                d
                for d in cls.decorator_list
                if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr == 'group_class'
            ]
            if not groups:
                continue
            try:
                prefix = ast.literal_eval(groups[0].args[1])
            except (ValueError, IndexError):
                unresolved.append(f'{path.relative_to(root)}:{cls.lineno}')
                continue
            for func in (node for node in ast.walk(cls) if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))):
                for dec in func.decorator_list:
                    if (
                        not isinstance(dec, ast.Call)
                        or not isinstance(dec.func, ast.Attribute)
                        or dec.func.attr != 'route'
                    ):
                        continue
                    location = f'{path.relative_to(root)}:{func.lineno}'
                    try:
                        rule = ast.literal_eval(dec.args[0])
                        methods = next((ast.literal_eval(k.value) for k in dec.keywords if k.arg == 'methods'), ['GET'])
                        if not isinstance(prefix, str) or not isinstance(rule, str) or not isinstance(methods, list):
                            raise ValueError('Dynamic route declaration')
                    except (ValueError, IndexError):
                        unresolved.append(location)
                        continue
                    for method in methods:
                        key = f'{method.upper()} {prefix}{rule}'
                        routes.append(
                            {
                                'route': key,
                                'source': location,
                                'contracts': [c['id'] for c in catalog['contracts'] if key in c.get('routes', [])],
                            }
                        )
    return {
        'scope': 'Static RouterGroup HTTP declarations only; excludes WebSockets, platform-dispatched and dynamic routes. Contract links are intent, not HTTP hit coverage.',
        'routes': routes,
        'unresolved': unresolved,
    }


def http_observations(paths, inventory):
    """Map Hypercorn access records to declared routes without retaining request URLs."""
    patterns, unsupported = [], []
    for route in inventory['routes']:
        method, path = route['route'].split(' ', 1)
        parts = re.split(r'(<[^>]+>)', path)
        if any(part.startswith('<') and ':' in part and not part.startswith(('<int:', '<path:')) for part in parts):
            unsupported.append(route['route'])
            continue
        pattern = ''.join(
            ('.+' if part.startswith('<path:') else r'\d+' if part.startswith('<int:') else '[^/]+')
            if part.startswith('<') and part.endswith('>')
            else re.escape(part)
            for part in parts
        )
        literal_length = sum(len(part) for part in parts if not part.startswith('<'))
        patterns.append((literal_length, method, re.compile(pattern), route['route']))
    patterns.sort(key=lambda item: item[0], reverse=True)
    access = re.compile(r'\b(GET|POST|PUT|PATCH|DELETE|HEAD|OPTIONS) (\S+) (?:HTTP/)?[123]\.[01] (\d{3})\b')
    matched, unclassified, records, errors = {}, Counter(), 0, []
    for path in paths:
        try:
            with Path(path).open() as stream:
                for line_number, line in enumerate(stream, 1):
                    match = access.search(line)
                    if not match:
                        continue
                    method, target, status = match.groups()
                    records += 1
                    try:
                        request_path = urlsplit(target).path
                    except ValueError:
                        errors.append(f'{path}:{line_number}: invalid request target')
                        unclassified[f'{method} {status}'] += 1
                        continue
                    route = next(
                        (
                            name
                            for _, expected_method, pattern, name in patterns
                            if method == expected_method and pattern.fullmatch(request_path)
                        ),
                        None,
                    )
                    if route is None:
                        unclassified[f'{method} {status}'] += 1
                    else:
                        matched.setdefault(route, Counter())[status] += 1
        except (OSError, ValueError) as exc:
            errors.append(f'{path}: {exc}')
    if paths and not records:
        errors.append('No HTTP access records were recognized')
    return {
        'scope': 'Observed HTTP methods and declared route templates; this does not prove behavior assertions or adapter sub-path coverage.',
        'records': records,
        'routes': [{'route': route, 'statuses': dict(statuses)} for route, statuses in sorted(matched.items())],
        'unclassified': dict(unclassified),
        'unsupported_templates': unsupported,
        'evidence_errors': errors,
    }


def counts(items):
    status = Counter(item['status'] for item in items)
    decided = status['passed'] + status['failed']
    return {
        'total': len(items),
        'decided': decided,
        'coverage_percent': round(100 * decided / len(items), 2) if items else None,
        'pass_percent': round(100 * status['passed'] / decided, 2) if decided else None,
        'status': {name: status[name] for name in STATES},
    }


def report(catalog, rows, errors=()):
    items, bound = [], set()
    for contract in catalog['contracts']:
        observations = []
        for binding in contract['bindings']:
            bound.add((binding['profile'], binding['case']))
            for row in rows:
                if (row['profile'], row['case']) != (binding['profile'], binding['case']):
                    continue
                if 'group_index' in binding and row.get('group_index') != binding['group_index']:
                    continue
                if 'turn' in binding and row.get('turn') != binding['turn']:
                    continue
                if row.get('turn', 0) < binding.get('min_turn', 0):
                    continue
                checks = [row.get('assertions', {}).get(name) for name in binding['checks']]
                status = (
                    'failed'
                    if 'failed' in checks
                    else 'skipped'
                    if row['status'] == 'skipped'
                    else 'passed'
                    if all(value == 'passed' for value in checks)
                    else 'incomplete'
                )
                observations.append({'status': status, 'case': row['case'], 'profile': row['profile']})
        statuses = {row['status'] for row in observations}
        status = (
            'missing_test'
            if not contract['bindings']
            else 'not_run'
            if not observations
            else 'failed'
            if 'failed' in statuses
            else 'skipped'
            if statuses == {'skipped'}
            else 'passed'
            if statuses == {'passed'}
            else 'incomplete'
        )
        items.append({**contract, 'status': status, 'observations': dict(Counter(x['status'] for x in observations))})
    return {
        'version': 1,
        'scope': catalog['scope'],
        'catalog_version': catalog['version'],
        'catalog_sha256': hashlib.sha256(json.dumps(catalog, sort_keys=True).encode()).hexdigest(),
        'complete_evidence': not errors,
        'kinds': {kind: counts([x for x in items if x['kind'] == kind]) for kind in ('blackbox', 'graybox')},
        'areas': {
            area: counts([x for x in items if x['kind'] == 'blackbox' and x['area'] == area])
            for area in sorted({x['area'] for x in items if x['kind'] == 'blackbox'})
        },
        'contracts': items,
        'unclassified_cases': [
            {'profile': p, 'case': c} for p, c in sorted({(row['profile'], row['case']) for row in rows} - bound)
        ],
        'evidence_errors': list(errors),
    }


def write_report(directories, output, catalog_path=CATALOG, http_logs=()):
    rows, errors = [], []
    for directory in directories:
        try:
            found, invalid = collect(directory)
            rows.extend(found)
            errors.extend(invalid)
        except (ValueError, OSError, KeyError) as exc:
            errors.append(f'{directory}: {exc}')
    catalog = load_catalog(catalog_path)
    data = report(catalog, rows, errors)
    data['route_inventory'] = route_inventory(catalog)
    if http_logs:
        data['http_observations'] = http_observations(http_logs, data['route_inventory'])
        errors.extend(data['http_observations']['evidence_errors'])
        data['evidence_errors'] = list(errors)
        data['complete_evidence'] = not errors
    output = Path(output)
    output.mkdir(parents=True, exist_ok=True)
    (output / 'coverage.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
    lines = [
        '# Business behavior coverage',
        '',
        data['scope'],
        '',
        'Coverage counts evaluated contracts (pass or fail), not requests or code lines.',
        'Incomplete evidence and skipped/not-run contracts do not count. Gray-box evidence is separate.',
        '',
        '| Evidence | Decided / registered | Coverage | Pass rate |',
        '|---|---:|---:|---:|',
    ]
    for kind, values in data['kinds'].items():
        lines.append(
            f'| {kind} | {values["decided"]}/{values["total"]} | {values["coverage_percent"]}% | {values["pass_percent"]}% |'
        )
    lines += ['', '| Priority | Contract | Area | Evidence | Status |', '|---|---|---|---|---|']
    for item in sorted(data['contracts'], key=lambda x: (x['priority'], x['area'], x['id'])):
        lines.append(
            f'| {item["priority"]} | {item["id"]}: {item["description"]} | {item["area"]} | {item["kind"]} | {item["status"]} |'
        )
    inventory = data['route_inventory']
    unlinked = sum(not r['contracts'] for r in inventory['routes'])
    lines += [
        '',
        f'Route inventory: {len(inventory["routes"])} HTTP declarations; {unlinked} have no linked behavior contract; {len(inventory["unresolved"])} need manual classification.',
        inventory['scope'],
        'Full route list and source locations are in coverage.json.',
    ]
    if http_logs:
        observed = data['http_observations']
        lines += [
            '',
            f'Observed HTTP: {len(observed["routes"])} declared routes, {observed["records"]} access records.',
            observed['scope'],
            '| Route | HTTP statuses and counts |',
            '|---|---|',
        ]
        lines.extend(f'| {row["route"]} | {row["statuses"]} |' for row in observed['routes'])
        lines.append(f'Unclassified method/status counts: {observed["unclassified"]}')
    for item in data['unclassified_cases']:
        lines.append(f'\nUnclassified case: {item["profile"]}/{item["case"]}')
    for error in errors:
        lines.append(f'\nEvidence error: {error}')
    (output / 'coverage.md').write_text('\n'.join(lines) + '\n')
    return data


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--run', type=Path, action='append', required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--http-log', type=Path, action='append', default=[])
    args = parser.parse_args()
    data = write_report(args.run, args.output, http_logs=args.http_log)
    print(json.dumps(data['kinds'], indent=2))
    if data['evidence_errors']:
        raise SystemExit(1)


if __name__ == '__main__':
    main()
