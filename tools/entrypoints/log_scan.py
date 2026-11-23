"""Build a report-only anomaly summary from regression service logs."""

import argparse
from collections import Counter, defaultdict
import fnmatch
import glob
import json
from pathlib import Path
import re
from statistics import median

import yaml

from tools.regression.service_logs import TRACE, records


SECRET = re.compile(
    r"""(?ix)(\b(?:authorization|(?:[\w-]+[_-])?token|(?:[\w-]+[_-])?key|password|secret)["']?\s*[:=]\s*)(?:"[^"]*"|'[^']*'|(?:bearer\s+|basic\s+)?[^\s,;&}\]]+)|\b(bearer\s+)[^\s,;"']+"""
)
VARIABLE = re.compile(
    r""""[^"]*"|'[^']*'|\b[\da-fA-F]{8}(?:-[\da-fA-F]{4}){3}-[\da-fA-F]{12}\b|\b(?:\d{1,3}\.){3}\d{1,3}(?::\d+)?\b|\b(?:0x[\da-fA-F]+|[\da-fA-F]{8,})\b|\d+"""
)
EMPTY = re.compile(r'(?:\bfailed\b.*|[\w.]+(?:Error|Exception)):\s*$', re.I)


def redact(text):
    return SECRET.sub(lambda match: (match[1] or match[2]) + '<redacted>', text)


def classify(record):
    stack = record.msg == TRACE or any(line.strip() == TRACE for line in record.continuation)
    if not stack and record.level not in ('WARN', 'ERROR', 'FATAL'):
        return None
    message = record.msg
    if record.access:
        method, path, status = record.access
        status_template = '5xx' if status >= 500 else str(status)
        route = '/'.join('#' if VARIABLE.fullmatch(segment) else segment for segment in path.split('/'))
        message = f'{method} {route} {status_template}'
        kind = 'http_5xx' if status >= 500 else 'warn'
    else:
        if stack:
            kind = 'traceback'
            if record.continuation:
                terminal = record.continuation[-1].strip()
                message = terminal if record.msg == TRACE else record.msg
                if not record.exc_type and re.match(r'^[\w.]+:', terminal):
                    record.exc_type = terminal.partition(':')[0]
        elif EMPTY.search(message) or (record.exc_type and not message.strip()):
            kind = 'empty_exception_message'
        else:
            kind = 'warn' if record.level == 'WARN' else 'error'
        message = VARIABLE.sub('#', redact(message)).strip()
    fingerprint = '|'.join(
        [record.service, record.module or record.file, record.func, record.exc_type, redact(message)]
    )
    return kind, fingerprint


def scan(files, allowlist, baselines):
    groups = {}
    totals = defaultdict(Counter)
    unknown = {}
    warn_counts = Counter()
    for path, service in files:
        with path.open(encoding='utf-8', errors='replace') as stream:
            for record in records(stream, service):
                counts = totals[record.service]
                counts['lines'] += 1 + len(record.continuation)
                if not record.level:
                    counts['unparsed'] += 1
                    if record.service not in unknown or not unknown[record.service]:
                        unknown[record.service] = redact(record.sample)[:400]
                    continue
                key = classify(record)
                if not key:
                    continue
                kind, fingerprint = key
                if kind == 'warn':
                    warn_counts[fingerprint] += 1
                if key not in groups:
                    groups[key] = dict(
                        kind=kind,
                        service=record.service,
                        fingerprint=fingerprint,
                        count=0,
                        first_ts=record.ts,
                        last_ts=record.ts,
                        sample=redact(record.sample)[:400],
                    )
                group = groups[key]
                group['count'] += 1
                if record.ts:
                    group['first_ts'] = min(record.ts, group['first_ts'] or record.ts)
                    group['last_ts'] = max(record.ts, group['last_ts'] or record.ts)
    anomalies = []
    for (kind, fingerprint), group in sorted(groups.items()):
        baseline = median([run.get(fingerprint, 0) for run in baselines]) if baselines and kind == 'warn' else None
        group['baseline_median'] = baseline
        count = group['count']
        if baseline is not None and count > max(2 * baseline, baseline + 20):
            group['kind'] = 'warn_growth'
        elif any(
            fnmatch.fnmatchcase(fingerprint, rule['pattern']) and count <= rule.get('max_count', count)
            for rule in allowlist
        ):
            continue
        anomalies.append(group)
    for service, counts in sorted(totals.items()):
        if counts['unparsed'] > 0.05 * counts['lines']:
            anomalies.append(
                dict(
                    kind='unparsed_ratio',
                    service=service,
                    fingerprint=f'{service}|unparsed',
                    count=counts['unparsed'],
                    baseline_median=None,
                    first_ts=None,
                    last_ts=None,
                    sample=unknown[service],
                )
            )
    return dict(
        services={svc: dict(lines=c['lines'], unparsed=c['unparsed']) for svc, c in totals.items()},
        warn_counts=warn_counts,
        anomalies=anomalies,
    )


def markdown(report):
    anomalies = report['anomalies']
    lines = [
        f'## Service logs: anomaly groups ({len(anomalies)})',
        '',
        'Service | Lines | Unparsed',
        '--- | ---: | ---:',
    ]
    for service, counts in sorted(report['services'].items()):
        lines.append(f'{service} | {counts["lines"]} | {counts["unparsed"]}')
    for group in anomalies[:30]:
        lines.extend(
            [
                '',
                f'- {group["service"]}: **{group["kind"]}** × {group["count"]} (baseline: {group["baseline_median"] if group["baseline_median"] is not None else "—"})',
                '',
                f'        {group["fingerprint"]}',
                f'        {group["first_ts"] or "—"} → {group["last_ts"] or "—"}',
                f'        {group["sample"]}',
            ]
        )
    if len(anomalies) > 30:
        lines.append('\nFull list in log-anomalies.json.')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', nargs='+', required=True)
    parser.add_argument('--service-map', default='')
    parser.add_argument('--allowlist', type=Path, required=True)
    parser.add_argument('--baseline', nargs='+', type=Path, default=[])
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    mapping = dict(item.split('=', 1) for item in args.service_map.split(',') if item)
    paths = sorted({Path(path).resolve() for pattern in args.input for path in glob.iglob(pattern, recursive=True)})
    if not paths:
        parser.error('no input logs matched')
    files = [(path, mapping.get(path.name, path.stem)) for path in paths]
    baselines = [
        json.loads((path / 'log-anomalies.json' if path.is_dir() else path).read_text())['warn_counts']
        for path in args.baseline
    ]
    report = scan(files, yaml.safe_load(args.allowlist.read_text()) or [], baselines)
    args.output.mkdir(exist_ok=True, parents=True)
    (args.output / 'log-anomalies.json').write_text(json.dumps(report, ensure_ascii=False, indent=2) + '\n')
    (args.output / 'log-anomalies.md').write_text(markdown(report))


if __name__ == '__main__':
    main()
