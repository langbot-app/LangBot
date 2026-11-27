import json

from tools.entrypoints.log_scan import classify, scan
from tools.regression.service_logs import records


OLD = '[11-22 19:29:28.964] (worker) app.py (42) - [WARNING] : '
NEW = '[2026-11-23 13:50:27.954099+08:00] ERROR [CORE.PIPELINE] query (mgr.py:312) [2785][MainThread/job][ws=test][Y-abc] '
HTTP = '[2026-11-22 19:24:39 +0000] [2785] [INFO] 127.0.0.1:35196 GET '


def test_records():
    old, unified, warning = records(
        [
            '\x1b[33m' + OLD + 'retry\x1b[0m',
            NEW + 'TimeoutError: query expired',
            '\tTraceback (most recent call last):',
            '\tTimeoutError: query expired',
            '/venv/api.py:149: InsecureKeyLengthWarning: short key',
            '  return encode()',
        ],
        'runtime',
    )
    assert (old.level, old.file, old.line, old.msg) == ('WARN', 'app.py', 42, 'retry')
    assert (unified.service, unified.module, unified.func, unified.trace, unified.exc_type) == (
        'core',
        'CORE.PIPELINE',
        'query',
        'Y-abc',
        'TimeoutError',
    )
    assert len(unified.continuation) == 2 and classify(unified)[0] == 'traceback'
    assert (warning.exc_type, warning.file, warning.line, warning.continuation) == (
        'InsecureKeyLengthWarning',
        'api.py',
        149,
        ['  return encode()'],
    )


def test_mixed_log(tmp_path):
    path = tmp_path / 'langbot.log.wf'
    path.write_text(
        '\n'.join(
            [
                NEW + 'failed token=hidden Authorization: Bearer hidden2',
                'Traceback (most recent call last):',
                '  File "core.py", line 123',
                '    raise ValueError()',
                'ValueError: bad input',
                HTTP + '/bots/123?api_key=hidden 1.1 500 12 34',
                HTTP + '/bots/456 1.1 502 34 56',
                HTTP + '/other 1.1 403 0 0',
                OLD + 'Terminal monitoring write failed (attempt 1): ',
                'unknown banner',
            ]
        )
    )
    report = scan([(path, 'core')], [], [])
    anomalies = {item['kind']: item for item in report['anomalies']}
    assert set(anomalies) == {'error', 'traceback', 'empty_exception_message', 'http_5xx', 'warn', 'unparsed_ratio'}
    assert anomalies['http_5xx']['count'] == 2
    assert 'ValueError' in anomalies['traceback']['fingerprint']
    assert anomalies['traceback']['first_ts'] == '2026-11-23 13:50:27.954099+08:00'
    assert anomalies['traceback']['sample'].endswith('ValueError: bad input')
    assert report['services']['core'] == {'lines': 10, 'unparsed': 1}
    assert 'hidden' not in json.dumps(report)


def test_baseline_of_allowlisted_warnings(tmp_path):
    path = tmp_path / 'box.log'
    path.write_text((OLD + 'retry 1\n') * 31)
    files = [(path, 'box')]
    rules = [{'pattern': 'box|app.py|||retry #', 'max_count': 31}]
    report = scan(files, rules, [])
    assert not report['anomalies']
    (fingerprint,) = report['warn_counts']
    baselines = [{fingerprint: value} for value in (1, 10, 40)]
    (group,) = scan(files, rules, baselines)['anomalies']
    assert (group['kind'], group['count'], group['baseline_median']) == ('warn_growth', 31, 10)
    path.write_text((OLD + 'retry 2\n') * 30)
    assert not scan(files, rules, baselines)['anomalies']


def test_empty_allowlist(tmp_path, monkeypatch):
    from tools.entrypoints import log_scan

    logs = tmp_path / 'runtime.log'
    logs.write_text(OLD + 'warning')
    rules = tmp_path / 'allow.yaml'
    rules.touch()
    monkeypatch.setattr(
        'sys.argv', ['log_scan', '--input', str(logs), '--allowlist', str(rules), '--output', str(tmp_path)]
    )
    log_scan.main()
    report = json.loads((tmp_path / 'log-anomalies.json').read_text())
    assert report['anomalies'][0]['kind'] == 'warn'
