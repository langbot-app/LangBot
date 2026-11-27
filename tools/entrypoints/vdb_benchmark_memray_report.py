"""Summarize owned Core native allocations without exporting raw traces."""

import argparse
from collections.abc import Iterable
import json
from pathlib import Path
from typing import Protocol

_SQLITE = 'CPython SQLite'
_SQLITE_OTHER = 'SQLite other/unresolved caller'
_TEMPFILE = 'Temporary file reads on Core bounded executor'
_OTHER = 'Other/unclassified'
_GROUPS = (_SQLITE, _SQLITE_OTHER, _TEMPFILE, _OTHER)


class PeakRecord(Protocol):
    size: int
    n_allocations: int

    def hybrid_stack_trace(self) -> Iterable[tuple[str, str, int]]: ...


def _classify(stack: Iterable[tuple[str, str, int]]) -> str:
    sqlite = cpython = buffered = tempfile = executor = False
    for symbol, filename, _ in stack:
        sqlite |= symbol.startswith('sqlite3')
        cpython |= symbol.startswith(('_pysqlite_query_execute', 'pysqlite_query_execute'))
        buffered |= symbol.startswith('_io__Buffered_read')
        # Paths are used only as classification inputs, never serialized.
        tempfile |= symbol == 'read' and (filename == 'tempfile.py' or filename.endswith('/tempfile.py'))
        executor |= filename.endswith('/langbot/pkg/utils/bounded_executor.py')
    if sqlite:
        return _SQLITE if cpython else _SQLITE_OTHER
    if buffered and tempfile and executor:
        return _TEMPFILE
    return _OTHER


def summarize(records: Iterable[PeakRecord], *, expected_peak_bytes: int) -> dict:
    groups = {label: {'bytes': 0, 'allocations': 0, 'largest_stack_bytes': 0} for label in _GROUPS}
    for record in records:
        group = groups[_classify(record.hybrid_stack_trace())]
        group['bytes'] += record.size
        group['allocations'] += record.n_allocations
        group['largest_stack_bytes'] = max(group['largest_stack_bytes'], record.size)
    total = sum(group['bytes'] for group in groups.values())
    if total != expected_peak_bytes:
        raise ValueError('Memray peak records do not match the recorded allocation high-water mark')
    return {
        'metric': 'tracked_allocation_high_watermark_not_rss',
        'peak_tracked_allocation_bytes': total,
        'groups': groups,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True, help='Owned Memray native trace')
    parser.add_argument('--output', type=Path, required=True, help='New JSON file outside the checkout')
    args = parser.parse_args()
    try:
        from memray import FileReader
    except ImportError:
        parser.error('install the optional QA dependency memray before reading a trace')
    reader = FileReader(str(args.input))
    if not reader.metadata.has_native_traces:
        parser.error('capture the Core trace with Memray --native for stack attribution')
    report = summarize(
        reader.get_high_watermark_allocation_records(),
        expected_peak_bytes=reader.metadata.peak_memory,
    )
    with args.output.open('x', encoding='utf-8') as output:
        json.dump(report, output, indent=2)
        output.write('\n')


if __name__ == '__main__':
    main()
