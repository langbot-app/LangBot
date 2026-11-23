"""Parse service output, keeping multiline records together within each file."""

import re
from dataclasses import dataclass, field
from pathlib import Path


ANSI = re.compile(r'\x1b\[[\d;]*m')
OLD = re.compile(
    r'(?:\([^)]*\) )?\[(?P<ts>\d\d-\d\d [\d:.]+)\] (?:\([^)]*\) )?(?P<file>\S+) \((?P<line>\d+)\) - \[(?P<level>\w+)\] : (?P<msg>.*)'
)
NEW = re.compile(
    r'\[(?P<ts>\d{4}-[\d: .+T-]+)\] (?P<level>\w+) +\[(?P<module>[^\]]+)\] (?P<func>\S+) \((?P<file>.+?):(?P<line>\d+)\) \[\d+\]\[[^\]]*\]\[[^\]]*\]\[(?P<trace>[^\]]*)\] (?P<msg>.*)'
)
HYPER = re.compile(r'\[(?P<ts>\d{4}-[^\]]+)\] \[\d+\] \[(?P<level>\w+)\] (?P<msg>.*)')
ACCESS = re.compile(r'\S+ ([A-Z]+) (\S+) (?:HTTP/)?[\d.]+ (\d{3})(?: |$)')
WARNING = re.compile(r'(?:(?P<file>.+?):(?P<line>\d+): )?(?P<exc_type>\w*Warning):\s*(?P<msg>.*)')
EXCEPTION = re.compile(r'([\w.]+(?:Error|Exception|Interrupt|Exit))(?::\s*(.*)|$)')
TRACE = 'Traceback (most recent call last):'


@dataclass(slots=True)
class Record:
    service: str
    msg: str
    level: str = ''
    ts: str | None = None
    module: str = ''
    func: str = ''
    file: str = ''
    line: int | None = None
    trace: str = ''
    exc_type: str = ''
    continuation: list[str] = field(default_factory=list)
    access: tuple = ()
    sample: str = ''


def parse(text, service):
    if text.startswith(('[', '(')):
        match = OLD.match(text) or NEW.match(text) or HYPER.match(text)
    else:
        match = WARNING.match(text) if 'Warning:' in text else None
    if not match:
        return Record(service, text, 'ERROR' if text == TRACE else '', sample=text)
    fields = {key: value for key, value in match.groupdict().items() if value is not None}
    if 'line' in fields:
        fields['line'] = int(fields['line'])
    if match.re is WARNING:
        fields.update(level='WARN', file=Path(fields.get('file', '')).name)
    record = Record(service, **fields, sample=text)
    if match.re is NEW:
        prefix, _, suffix = record.module.partition('.')
        if prefix in ('CORE', 'RUNTIME', 'BOX', 'PLUGIN'):
            record.service = 'plugin:' + suffix if prefix == 'PLUGIN' else prefix.lower()
    if match.re in (NEW, HYPER) and (access := ACCESS.match(record.msg)):
        method, path, status = access.groups()
        record.access = method, path.partition('?')[0], int(status)
        record.level = 'ERROR' if status.startswith('5') else 'WARN' if status.startswith('4') else 'INFO'
    record.level = {'WARNING': 'WARN', 'CRITICAL': 'FATAL'}.get(record.level, record.level)
    if record.level in ('ERROR', 'FATAL', 'WARN') and (exc := EXCEPTION.match(record.msg)):
        record.exc_type = exc[1]
    return record


def records(lines, service):
    previous = None
    last_timestamp = None
    in_trace = False
    for raw in lines:
        text = raw.rstrip('\r\n')
        if '\x1b' in text:
            text = ANSI.sub('', text)
        if previous and previous.level:
            if (
                text.startswith('\t')
                or (in_trace and text.startswith(' '))
                or (previous.exc_type.endswith('Warning') and text.startswith('  '))
            ):
                previous.continuation.append(text)
                continue
            if in_trace and re.fullmatch(r'[\w.]+(?::.*)?', text):
                previous.continuation.append(text)
                previous.exc_type = text.partition(':')[0]
                previous.sample += '\n' + text
                in_trace = False
                continue
        if previous is not None:
            yield previous
        previous = parse(text, service)
        in_trace = text == TRACE
        if in_trace:
            previous.ts = last_timestamp
        elif previous.ts:
            last_timestamp = previous.ts
    if previous is not None:
        yield previous
