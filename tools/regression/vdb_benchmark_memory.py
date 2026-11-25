"""Read-only Linux process memory evidence for an owned test deployment.

RSS is never presented as unique resident memory. PSS is proportional and
optional, descendant coverage is sampled, and cgroup counters are shared
scope evidence, not a per-process OOM diagnosis.
"""

from collections import defaultdict
from dataclasses import dataclass
from hashlib import sha256
import json
import math
from pathlib import Path, PurePosixPath
import re
from statistics import median
from threading import Event, Lock, Thread
from time import monotonic, monotonic_ns, sleep

from tools.regression.vdb_benchmark_smaps import mapping_summary, read_smaps

ROLE = re.compile(r'[a-z][a-z0-9_-]{0,63}\Z')
PHASE = re.compile(r'[a-z][a-z0-9:_-]{0,127}\Z')
OOM_KEYS = ('oom', 'oom_kill', 'oom_group_kill')
MAX_TREE_PROCESSES = 512


def text_or_none(path):
    try:
        return path.read_text()
    except (OSError, UnicodeError):
        return None


def numeric(raw):
    text = (raw or '').strip()
    return int(text) if text.isascii() and text.isdecimal() else None


def parser_kib(raw, keys):
    values = {key: None for key in keys}
    for line in (raw or '').splitlines():
        key, _, body = line.partition(':')
        if key in values:
            parts = body.split()
            if len(parts) == 2 and parts[1] == 'kB' and (n := numeric(parts[0])) is not None:
                values[key] = n * 1024
    return values


@dataclass(frozen=True)
class ProcessIdentity:
    pid: int
    start_ticks: int


def read_identity(proc, pid):
    raw = text_or_none(proc / str(pid) / 'stat')
    if raw is None:
        return None
    before, marker, after = raw.rpartition(')')
    tail = after.split()
    if not marker or not before.startswith(f'{pid} (') or len(tail) < 20:
        return None
    # Field 22, relative to start of field 3 after process comm.
    ticks = numeric(tail[19])
    return ProcessIdentity(pid, ticks) if ticks is not None and tail[0] not in {'Z', 'X'} else None


def children(proc, pid):
    try:
        threads = tuple((proc / str(pid) / 'task').iterdir())
    except OSError:
        return set(), False
    found = set()
    ok = bool(threads)
    for thread in threads:
        raw = text_or_none(thread / 'children')
        if raw is None:
            ok = False
            continue
        for child in raw.split():
            n = numeric(child)
            if n is None or n <= 0:
                ok = False
            else:
                found.add(n)
    return found, ok


def role_snapshot(proc, root, retained, *, pss_sampled, protected=(), mapping_sampled=False, chroma_dir=None):
    """Track descendants of this owned root, plus still-live observed reparented workers."""
    # Continue reporting previously observed workers after a root exits
    # without declaring its tree complete or adopting a reused root PID.
    pending = [x for x in retained if x != root and read_identity(proc, x.pid) == x]
    if read_identity(proc, root.pid) == root:
        pending.append(root)
    seen = set()
    data = []
    discovery = True
    while pending and len(seen) < MAX_TREE_PROCESSES:
        identity = pending.pop()
        if identity in seen or identity in protected:
            continue
        seen.add(identity)
        if read_identity(proc, identity.pid) != identity:
            discovery = False
            continue
        pid_dir = proc / str(identity.pid)
        fields = parser_kib(text_or_none(pid_dir / 'status'), ('VmRSS', 'VmHWM', 'RssAnon', 'RssFile', 'RssShmem'))
        smaps = read_smaps(pid_dir / 'smaps', chroma_dir, fields['VmRSS']) if mapping_sampled else None
        detailed_pss = (smaps or {}).get('totals', {}).get('pss_bytes')
        if pss_sampled and detailed_pss is None:
            pss = parser_kib(text_or_none(pid_dir / 'smaps_rollup'), ('Pss',))['Pss']
        else:
            pss = detailed_pss if pss_sampled else None
        child_pids, complete = children(proc, identity.pid)
        discovery &= complete
        if read_identity(proc, identity.pid) != identity:
            discovery = False
            continue
        data.append(
            {
                'pid': identity.pid,
                'start_ticks': identity.start_ticks,
                'kind': 'root' if identity == root else 'descendant',
                'rss_bytes': fields['VmRSS'],
                'hwm_bytes': fields['VmHWM'],
                'rss_anon_bytes': fields['RssAnon'],
                'rss_file_bytes': fields['RssFile'],
                'rss_shmem_bytes': fields['RssShmem'],
                'pss_bytes': pss,
                **({'smaps': smaps} if mapping_sampled else {}),
            }
        )
        for pid in child_pids:
            found = read_identity(proc, pid)
            if found is None:
                discovery = False
            elif found not in seen:
                pending.append(found)
    root_alive = read_identity(proc, root.pid) == root
    complete = root_alive and discovery and not pending and bool(data)

    def complete_sum(key):
        if not complete or any(row[key] is None for row in data):
            return None
        return sum(row[key] for row in data)

    return {
        'root_alive': root_alive,
        'discovery_complete': complete,
        **({'mapping_requested': True} if mapping_sampled else {}),
        'rss_tree_sum_bytes': complete_sum('rss_bytes'),
        'pss_tree_bytes': complete_sum('pss_bytes'),
        'processes': sorted(data, key=lambda p: (p['kind'] != 'root', p['pid'])),
    }, {ProcessIdentity(p['pid'], p['start_ticks']) for p in data if p['kind'] == 'descendant'}


def cgroup_v2_path(proc, pid):
    for line in (text_or_none(proc / str(pid) / 'cgroup') or '').splitlines():
        if line.startswith('0::'):
            location = PurePosixPath(line[3:])
            if location.is_absolute() and '..' not in location.parts:
                return location
    return None


def cgroup_mount(proc):
    for line in (text_or_none(proc / 'self/mountinfo') or '').splitlines():
        left, sep, right = line.partition(' - ')
        items = left.split()
        if sep and right.split()[:1] == ['cgroup2'] and len(items) >= 5:
            # Standard mountinfo octal escape convention, needed for spaces.
            def unescape(value):
                return re.sub(r'\\([0-7]{3})', lambda m: chr(int(m[1], 8)), value)

            return PurePosixPath(unescape(items[3])), Path(unescape(items[4]))
    return None


def read_cgroup(directory):
    events = {}
    for line in (text_or_none(directory / 'memory.events') or '').splitlines():
        parts = line.split()
        if len(parts) == 2 and parts[0] in OOM_KEYS and (n := numeric(parts[1])) is not None:
            events[parts[0]] = n
    maximum = text_or_none(directory / 'memory.max')
    return {
        'current_bytes': numeric(text_or_none(directory / 'memory.current')),
        'max_bytes': numeric(maximum),
        'unlimited': True if (maximum or '').strip() == 'max' else False if numeric(maximum) is not None else None,
        'events': {key: events.get(key) for key in OOM_KEYS},
    }


class CgroupTracker:
    def __init__(self, proc):
        self.proc = proc
        self.mount = cgroup_mount(proc)
        self.locations = {}
        self.owners = defaultdict(set)

    def snapshot(self, roles):
        if self.mount is None:
            return []
        mount_root, mount_point = self.mount
        for role, identity in roles.items():
            if read_identity(self.proc, identity.pid) != identity:
                continue
            location = cgroup_v2_path(self.proc, identity.pid)
            if location is None:
                continue
            try:
                relative = location.relative_to(mount_root)
            except ValueError:
                continue
            directory = mount_point / relative
            self.locations[role] = directory
            self.owners[directory].add(role)
        # Keep direct cgroup evidence if a sampled root exits. The shared
        # counters can still advance after that process can no longer be read.
        return [
            {
                'group_id': sha256(str(directory).encode()).hexdigest()[:16],
                'roles': sorted(owners),
                'unchanged_membership': all(self.locations[role] == directory for role in owners),
                **read_cgroup(directory),
            }
            for directory, owners in self.owners.items()
        ]


def end_value(values):
    return values[-1] if values else None


def observed_max(values):
    return max(values) if values else None


def summarize_memory(samples):
    phases = list(dict.fromkeys(row['phase'] for row in samples))
    all_roles = sorted({role for row in samples for role in row['roles']})
    mapped_roles = {role for sample in samples for role, row in sample['roles'].items() if row.get('mapping_requested')}
    by_role = {}
    for name in all_roles:
        phase_stats = {}
        for phase in phases:
            rows = [row['roles'][name] for row in samples if row['phase'] == phase and name in row['roles']]
            root_rows = [p for row in rows if row['root_alive'] for p in row['processes'] if p['kind'] == 'root']

            def values(source, key):
                return [row[key] for row in source if row[key] is not None]

            rss = values(root_rows, 'rss_bytes')
            hwm = values(root_rows, 'hwm_bytes')
            tree_rss = values(rows, 'rss_tree_sum_bytes')
            tree_pss = values(rows, 'pss_tree_bytes')
            direct_pss = values(root_rows, 'pss_bytes')
            child_rss = [
                sum(p['rss_bytes'] for p in row['processes'] if p['kind'] == 'descendant')
                for row in rows
                if row['rss_tree_sum_bytes'] is not None
            ]
            desc = {(p['pid'], p['start_ticks']) for row in rows for p in row['processes'] if p['kind'] == 'descendant'}
            baseline_label = phase.split(':', 1)[0] + ':baseline' if ':' in phase else 'baseline'
            base = (phase_stats.get(baseline_label) or {}).get('root_rss_median_bytes')
            details = mapping_summary(samples, name, phase, baseline_label) if name in mapped_roles else None
            phase_stats[phase] = {
                **({'mapping_attribution': details} if details is not None else {}),
                'samples': len(rows),
                'root_alive_samples': sum(row['root_alive'] for row in rows),
                'root_rss_samples': len(rss),
                'complete_discovery_samples': sum(row['discovery_complete'] for row in rows),
                'complete_tree_rss_samples': len(tree_rss),
                'complete_tree_pss_samples': len(tree_pss),
                'distinct_sampled_descendants': len(desc),
                'root_rss_median_bytes': median(rss) if rss else None,
                'root_rss_peak_sampled_bytes': observed_max(rss),
                'root_rss_anon_peak_sampled_bytes': observed_max(values(root_rows, 'rss_anon_bytes')),
                'root_rss_file_peak_sampled_bytes': observed_max(values(root_rows, 'rss_file_bytes')),
                'root_pss_peak_sampled_bytes': observed_max(direct_pss),
                'observed_descendant_rss_sum_peak_sampled_bytes': observed_max(child_rss),
                'root_last_observed_rss_bytes': end_value(rss),
                'root_lifetime_hwm_end_bytes': end_value(hwm),
                'root_lifetime_hwm_advanced': hwm[-1] > hwm[0] if len(hwm) >= 2 else None,
                'tree_rss_sum_peak_sampled_bytes': observed_max(tree_rss),
                'tree_pss_peak_sampled_bytes': observed_max(tree_pss),
                'root_peak_delta_from_baseline_median_bytes': max(rss) - base if rss and base is not None else None,
                'root_last_delta_from_baseline_median_bytes': rss[-1] - base if rss and base is not None else None,
            }
        by_role[name] = phase_stats

    oom = []
    grouped = defaultdict(list)
    for row in samples:
        for group in row['cgroups']:
            grouped[group['group_id']].append((row['monotonic_ns'], group))
    for group_id, rows in grouped.items():
        first_stamp, first = rows[0]
        last_stamp, last = rows[-1]
        increments = {}
        for key in OOM_KEYS:
            begin, end = first['events'][key], last['events'][key]
            increments[key] = (
                end - begin
                if last_stamp > first_stamp
                and begin is not None
                and end is not None
                and end >= begin
                and all(g['unchanged_membership'] for _, g in rows)
                else None
            )
        oom.append(
            {
                'group_id': group_id,
                'roles': sorted({role for _, snapshot in rows for role in snapshot['roles']}),
                'samples': len(rows),
                'events_delta': increments,
                'memory_current_peak_sampled_bytes': observed_max(
                    [group['current_bytes'] for _, group in rows if group['current_bytes'] is not None]
                ),
                'end_max_bytes': last['max_bytes'],
                'end_unlimited': last['unlimited'],
            }
        )
    known_kill = [group['events_delta']['oom_kill'] for group in oom]
    covered_roles = {role for group in oom if group['events_delta']['oom_kill'] is not None for role in group['roles']}
    return {
        'sampling_notice': (
            'Sampled /proc evidence in launcher namespace. RSS tree totals count shared pages repeatedly. '
            'PSS splits shared pages proportionally; lifetime HWM is not stage-exclusive. '
            'Embedded vector storage is in Core; cgroup OOM counters are shared-scope.'
        ),
        'samples': len(samples),
        'phases': phases,
        'roles': by_role,
        'host_mem_available_min_bytes': min(
            (row['host_mem_available_bytes'] for row in samples if row['host_mem_available_bytes'] is not None),
            default=None,
        ),
        'cgroup_v2': oom,
        'cgroup_oom_kill_observed': (
            True
            if any(n is not None and n > 0 for n in known_kill)
            else False
            if known_kill and all(n is not None for n in known_kill) and covered_roles == set(all_roles)
            else None
        ),
        'core_rss_phase_coverage': {
            phase: bool(phase_stat['root_rss_samples']) for phase, phase_stat in by_role.get('core', {}).items()
        },
    }


def partition_stages(samples, stage_events):
    """Partition background observations by complete external monotonic windows."""
    windows, errors, starts = [], [], {}
    raw = text_or_none(stage_events)
    if raw is None:
        return samples, {}, ['Stage events not readable']
    for line in raw.splitlines():
        try:
            row = json.loads(line)
            stage, event, timestamp = row['stage'], row['event'], row['monotonic_ns']
            if not isinstance(stage, str) or not PHASE.fullmatch(stage) or type(timestamp) is not int or timestamp <= 0:
                raise ValueError
            if event == 'start' and stage not in starts:
                starts[stage] = timestamp
            elif event == 'end' and stage in starts and timestamp > starts[stage]:
                windows.append((stage, starts.pop(stage), timestamp))
            else:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            errors.append('Ignored malformed or unpaired stage event')
    if starts:
        errors.append('Incomplete stage event window')
    observed = defaultdict(int)
    partitioned = []
    for row in samples:
        # A sample with an acquisition straddling a boundary is not claimed
        # for the short phase. Keep it labeled with the launcher phase.
        matches = {
            name for name, start, end in windows if start <= row['monotonic_ns'] and row['finished_monotonic_ns'] <= end
        }
        if len(matches) == 1:
            phase = next(iter(matches))
            observed[phase] += 1
            partitioned.append({**row, 'phase': phase})
        else:
            partitioned.append(row)
    return (
        partitioned,
        {name: observed[name] for name in sorted({name for name, _, _ in windows} | set(starts))},
        errors,
    )


class MemorySampler:
    """Capture same-namespace memory for explicitly owned deployment process roots."""

    def __init__(
        self,
        output,
        *,
        roots,
        interval_seconds=0.25,
        pss_every=4,
        stage_events=None,
        proc_root=Path('/proc'),
        mapping_every=0,
        chroma_dir=None,
        mapping_roles=('core', 'runtime'),
    ):
        if (
            not roots
            or any(
                not isinstance(role, str) or not ROLE.fullmatch(role) or type(pid) is not int or pid <= 0
                for role, pid in roots.items()
            )
            or len(set(roots.values())) != len(roots)
        ):
            raise ValueError('Memory sampling needs unique, named, launcher-owned process roots')
        if not math.isfinite(interval_seconds) or not 0.05 <= interval_seconds <= 60:
            raise ValueError('Memory sampling interval must be in 0.05..60 seconds')
        if type(pss_every) is not int or pss_every < 0:
            raise ValueError('pss_every must be zero (disabled) or a positive interval')
        if type(mapping_every) is not int or not 0 <= mapping_every <= 3600:
            raise ValueError('mapping_every must be zero (disabled) or a sampling interval up to 3600 ticks')
        if not isinstance(mapping_roles, (tuple, list)) or any(
            not isinstance(role, str) or not ROLE.fullmatch(role) for role in mapping_roles
        ):
            raise ValueError('mapping_roles must contain known memory role labels')
        self.mapping_every = mapping_every
        self.chroma_dir = Path(chroma_dir).resolve() if chroma_dir is not None else None
        self.mapping_roles = set(mapping_roles) & set(roots)
        if mapping_every and not self.mapping_roles:
            raise ValueError('No owned process roles were selected for detailed mapping sampling')
        self.output = Path(output)
        self.proc = Path(proc_root)
        self.root_pids = roots.copy()
        self.phase_counts = defaultdict(int)
        self.cgroups = CgroupTracker(self.proc)
        self.roots = {}
        self.retained = {name: set() for name in roots}
        self.interval = interval_seconds
        self.pss_every = pss_every
        self.stage_events = Path(stage_events) if stage_events is not None else None
        self.phase = 'setup'
        self.errors = []
        self.sequence = 0
        self.stop = Event()
        self.lock = Lock()
        self.thread = None

    def mark(self, phase):
        if not isinstance(phase, str) or not PHASE.fullmatch(phase):
            raise ValueError('Invalid memory phase label')
        with self.lock:
            self.phase = phase

    def wait_for_samples(self, phase, *, minimum=3, timeout=5):
        deadline = monotonic() + timeout
        while monotonic() < deadline and not self.stop.is_set():
            with self.lock:
                if self.phase_counts[phase] >= minimum:
                    return True
            sleep(min(self.interval / 2, 0.05))
        return False

    def _snapshot(self):
        with self.lock:
            self.sequence += 1
            began = monotonic_ns()
            sample_pss = bool(self.pss_every and (self.sequence - 1) % self.pss_every == 0)
            mapping_tick = self.mapping_every and (self.sequence - 1) % self.mapping_every == 0
            roles = {}
            for name, root in self.roots.items():
                protected = set(self.roots.values()) - {root}
                roles[name], self.retained[name] = role_snapshot(
                    self.proc,
                    root,
                    self.retained[name],
                    pss_sampled=sample_pss,
                    protected=protected,
                    mapping_sampled=bool(mapping_tick and name in self.mapping_roles),
                    chroma_dir=self.chroma_dir,
                )
            host = parser_kib(text_or_none(self.proc / 'meminfo'), ('MemAvailable',))
            cgroups = self.cgroups.snapshot(self.roots)
            return {
                'sequence': self.sequence,
                'monotonic_ns': began,
                'finished_monotonic_ns': monotonic_ns(),
                'phase': self.phase,
                'pss_requested': sample_pss,
                'roles': roles,
                'host_mem_available_bytes': host['MemAvailable'],
                'cgroups': cgroups,
            }

    def _run(self):
        try:
            with (self.output / 'memory-samples.jsonl').open('x') as sink:
                while not self.stop.is_set():
                    began = monotonic()
                    sample = self._snapshot()
                    sink.write(json.dumps(sample, allow_nan=False, separators=(',', ':')) + '\n')
                    sink.flush()
                    if all(
                        any(p['kind'] == 'root' and p['rss_bytes'] is not None for p in role['processes'])
                        for role in sample['roles'].values()
                    ):
                        with self.lock:
                            self.phase_counts[sample['phase']] += 1
                    self.stop.wait(max(0, self.interval - (monotonic() - began)))
        except (OSError, ValueError, RuntimeError) as exc:
            self.errors.append('Memory sampling failed: ' + type(exc).__name__)

    def __enter__(self):
        self.output.mkdir(mode=0o700, parents=True, exist_ok=False)
        for name, pid in self.root_pids.items():
            identity = read_identity(self.proc, pid)
            if identity is None:
                self.errors.append(f'{name}: owned root process not visible in sampler namespace')
                # Do not adopt a numeric PID later if we couldn't establish its
                # start time at entry: it could already be recycled.
                self.roots[name] = ProcessIdentity(pid, -1)
            else:
                self.roots[name] = identity
        self.thread = Thread(target=self._run, name='langbot-memory-sampler', daemon=True)
        self.thread.start()
        return self

    def __exit__(self, *_args):
        self.stop.set()
        self.thread.join(timeout=max(self.interval * 2, 5))
        samples = []
        stage_sample_counts = None
        if self.thread.is_alive():
            self.errors.append('Sampler did not finish before its join deadline')
        else:
            try:
                with (self.output / 'memory-samples.jsonl').open() as raw:
                    samples = [json.loads(line) for line in raw]
            except (OSError, ValueError) as exc:
                self.errors.append('Raw memory samples unavailable: ' + type(exc).__name__)
        if self.stage_events is not None:
            samples, stage_sample_counts, errors = partition_stages(samples, self.stage_events)
            self.errors.extend(errors)
        summary = summarize_memory(samples)
        if self.mapping_every:
            summary['mapping_observation'] = {
                'every_ticks': self.mapping_every,
                'roles': sorted(self.mapping_roles),
                'chroma_file_scope_configured': self.chroma_dir is not None,
                'notice': (
                    'Disjoint VMA labels describe mapping provenance, not allocating component. '
                    'File mappings can contain anonymous copy-on-write pages; anonymous counters overlap VMA categories. '
                    'Status and smaps are separate observations; signed gaps are not unclassified RSS. '
                    'Anonymous heap/other cannot identify Chroma allocator use; only explicit Chroma-directory file maps are named. '
                    'Sampled-tree RSS retains shared-page double counting; PSS is proportional.'
                ),
            }
        summary.update(
            interval_seconds=self.interval,
            pss_every=self.pss_every,
            coverage_errors=self.errors,
            stage_sample_counts=stage_sample_counts,
            stage_samples_missing=[k for k, v in (stage_sample_counts or {}).items() if not v],
            sampling_complete=bool(samples)
            and not self.errors
            and all(
                row['root_rss_samples'] == row['samples'] > 0
                for rows in summary['roles'].values()
                for row in rows.values()
            ),
        )
        (self.output / 'memory-summary.json').write_text(json.dumps(summary, indent=2, allow_nan=False) + '\n')
