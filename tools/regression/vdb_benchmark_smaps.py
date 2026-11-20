"""Bounded, read-only Linux smaps aggregation; no allocation owner attribution."""

from pathlib import PurePosixPath
import re

MAX_SMAPS_BYTES = 16 * 1024 * 1024
MAX_LINE_BYTES = 65536
METRICS = {'Rss': 'rss_bytes', 'Pss': 'pss_bytes', 'Anonymous': 'anonymous_bytes'}
CATEGORIES = (
    'anonymous_heap',
    'anonymous_stack',
    'anonymous_other',
    'shared_memory',
    'chroma_files',
    'shared_libraries',
    'other_private_file',
    'other_shared_file',
    'kernel_special',
    'unclassified',
)
VMA = re.compile(rb'^[0-9a-f]+-[0-9a-f]+ ([r-][w-][x-][ps]) [0-9a-f]+ [0-9a-f]+:[0-9a-f]+ +[0-9]+ *(.*?)\n?$')
SHARED_OBJECT = re.compile(r'\.so(?:\.[^/]+)?$')


def mapping_category(label, permissions, chroma_root):
    # Linux renders deleted maps with a trailing marker not part of the path.
    label = label.removesuffix(' (deleted)')
    if label == '[heap]':
        return 'anonymous_heap'
    if label == '[stack]' or (label.startswith('[stack:') and label.endswith(']')):
        return 'anonymous_stack'
    if (
        label.startswith(('[anon_shmem:', '/dev/shm/', '/memfd:', '/SYSV', 'memfd:'))
        or (label == '/dev/zero' and permissions.endswith('s'))
        or (not label and permissions.endswith('s'))
    ):
        return 'shared_memory'
    if not label or label.startswith('[anon:'):
        return 'anonymous_other'
    if label in {'[vdso]', '[vvar]', '[vvar_vclock]', '[vsyscall]', '[vectors]'}:
        return 'kernel_special'
    if label.startswith('/'):
        path = PurePosixPath(label)
        if chroma_root is not None and '..' not in path.parts and path.is_relative_to(chroma_root):
            return 'chroma_files'
        if SHARED_OBJECT.search(path.name):
            return 'shared_libraries'
        return 'other_shared_file' if permissions.endswith('s') else 'other_private_file'
    return 'unclassified'


def zero_categories():
    return {kind: {'mappings': 0, **dict.fromkeys(METRICS.values(), 0)} for kind in CATEGORIES}


def add_metrics(destination, source):
    destination['mappings'] += source['mappings']
    for key in METRICS.values():
        value = source[key]
        destination[key] = destination[key] + value if destination[key] is not None and value is not None else None


def totals(categories):
    total = {'mappings': 0, **dict.fromkeys(METRICS.values(), 0)}
    for row in categories.values():
        add_metrics(total, row)
    return total


def parse_smaps(stream, chroma_root=None, *, max_bytes=MAX_SMAPS_BYTES):
    """Each complete VMA contributes only once, to a name/backing category."""
    if chroma_root is not None:
        chroma_root = PurePosixPath(chroma_root)
    categories = zero_categories()
    current = None
    visited = 0

    def finish():
        if current is not None:
            if values['rss_bytes'] is None:
                raise ValueError('VMA RSS missing')
            add_metrics(categories[current], values)

    while line := stream.readline(MAX_LINE_BYTES + 1):
        visited += len(line)
        if visited > max_bytes or len(line) > MAX_LINE_BYTES:
            raise ValueError('smaps exceeds parser budget')
        header = VMA.fullmatch(line)
        if header:
            finish()
            permissions, label = header.groups()
            current = mapping_category(label.decode('utf-8', 'surrogateescape'), permissions.decode(), chroma_root)
            values = {'mappings': 1, **dict.fromkeys(METRICS.values())}
            continue
        name, _, body = line.partition(b':')
        key = METRICS.get(name.decode('ascii', 'ignore'))
        if key is None:
            continue
        parts = body.split()
        if current is None or len(parts) != 2 or not parts[0].isdigit() or parts[1] != b'kB' or values[key] is not None:
            raise ValueError('Malformed smaps metric')
        values[key] = int(parts[0]) * 1024
    finish()
    total = totals(categories)
    if not total['mappings']:
        raise ValueError('No readable memory mappings')
    return {'status': 'observed', 'totals': total, 'categories': categories}


def read_smaps(path, chroma_root, rss_status):
    try:
        with path.open('rb') as stream:
            result = parse_smaps(stream, chroma_root)
    except OSError as exc:
        return {'status': 'unavailable', 'reason': type(exc).__name__}
    except ValueError as exc:
        return {'status': 'incomplete', 'reason': str(exc)}
    return {
        **result,
        'status_rss_bytes': rss_status,
        'smaps_minus_status_rss_bytes': result['totals']['rss_bytes'] - rss_status if rss_status is not None else None,
    }


def aggregate_mappings(processes):
    if not processes or any(row.get('smaps', {}).get('status') != 'observed' for row in processes):
        return None
    categories = zero_categories()
    for row in processes:
        for key, values in row['smaps']['categories'].items():
            add_metrics(categories[key], values)
    return {'status': 'observed', 'totals': totals(categories), 'categories': categories}


def _snapshot_summary(snapshot, baseline):
    if snapshot is None:
        return None
    total = snapshot['totals']['rss_bytes']
    categories = snapshot['categories']
    in_order = sorted(
        [
            {'category': key, **metrics, 'rss_share': metrics['rss_bytes'] / total if total else None}
            for key, metrics in categories.items()
        ],
        key=lambda row: (-row['rss_bytes'], row['category']),
    )
    changes = (
        {key: value['rss_bytes'] - baseline['categories'][key]['rss_bytes'] for key, value in categories.items()}
        if baseline
        else None
    )
    largest_growth = max(changes, key=changes.get) if changes and max(changes.values()) > 0 else None
    return {
        'sample_sequence': snapshot['sample_sequence'],
        'totals': snapshot['totals'],
        'status_rss_bytes': snapshot.get('status_rss_bytes'),
        'smaps_minus_status_rss_bytes': snapshot.get('smaps_minus_status_rss_bytes'),
        'largest_rss_category': in_order[0]['category'] if total else None,
        'categories': in_order,
        'rss_delta_from_baseline_bytes': total - baseline['totals']['rss_bytes'] if baseline else None,
        'category_rss_deltas_bytes': changes,
        'largest_rss_growth_category': largest_growth,
    }


def mapping_summary(samples, role, phase, baseline_phase):
    def collect(wanted):
        planned, roots, trees, root_misses = 0, [], [], {}
        for sample in samples:
            data = sample['roles'].get(role, {})
            if sample['phase'] != wanted or not data.get('mapping_requested'):
                continue
            planned += 1
            processes = data['processes']
            root = next((p for p in processes if p['kind'] == 'root'), {})
            smaps = root.get('smaps', {})
            if data['root_alive'] and smaps.get('status') == 'observed':
                roots.append({**smaps, 'sample_sequence': sample['sequence']})
            else:
                reason = smaps.get('reason', 'owned root unavailable')
                root_misses[reason] = root_misses.get(reason, 0) + 1
            if data['discovery_complete'] and (tree := aggregate_mappings(processes)) is not None:
                trees.append({**tree, 'sample_sequence': sample['sequence']})
        return planned, roots, trees, root_misses

    planned, roots, trees, root_misses = collect(phase)
    if not planned and not any(sample['roles'].get(role, {}).get('mapping_requested') for sample in samples):
        return None
    _, base_roots, base_trees, _ = collect(baseline_phase)

    def points(current, baseline):
        ranks = sorted(baseline, key=lambda row: row['totals']['rss_bytes'])
        # Use one actual tick near baseline median, not a sum of independently
        # selected category medians across times.
        base = ranks[(len(ranks) - 1) // 2] if ranks else None
        peak = max(current, key=lambda row: row['totals']['rss_bytes'], default=None)
        return {
            'baseline_reference': _snapshot_summary(base, None),
            'peak_mapped_snapshot': _snapshot_summary(peak, base),
            'last_mapped_snapshot': _snapshot_summary(current[-1], base) if current else None,
        }

    return {
        'requested_samples': planned,
        'root_observed_samples': len(roots),
        'root_unobserved_reasons': root_misses,
        'complete_observed_tree_samples': len(trees),
        'root': points(roots, base_roots),
        'sampled_tree': points(trees, base_trees),
    }
