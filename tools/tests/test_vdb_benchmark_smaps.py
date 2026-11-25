"""Linux smaps parsing, scope, and paired snapshot rules (no external files)."""

from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

from tools.regression.vdb_benchmark_memory import MemorySampler
from tools.regression.vdb_benchmark_smaps import (
    aggregate_mappings,
    mapping_summary,
    parse_smaps,
    read_smaps,
)
from tools.tests.test_vdb_benchmark_memory import fake_process


def smap(label, rss, pss=None, anon=None, perms='rw-p', offset=1):
    lines = [f'{offset:08x}-{offset + 4096:08x} {perms} 00000000 00:00 0      {label}', f'Rss: {rss} kB']
    if pss is not None:
        lines.append(f'Pss: {pss} kB')
    if anon is not None:
        lines.append(f'Anonymous: {anon} kB')
    return ('\n'.join(lines) + '\n').encode()


def mapped(name, rss):
    return parse_smaps(BytesIO(smap(name, rss, rss - 1, rss)))


def sample(sequence, phase, role, processes):
    return {
        'sequence': sequence,
        'phase': phase,
        'roles': {
            role: {
                'mapping_requested': True,
                'root_alive': True,
                'discovery_complete': True,
                'processes': processes,
            }
        },
    }


class SmapAttributionTest(unittest.TestCase):
    def test_exclusive_scoped_categories_and_separate_anonymous_page_counter(self):
        read = parse_smaps(
            BytesIO(
                b''.join(
                    [
                        smap('[heap]', 8, 8, 8),
                        smap('[stack:123]', 4, 4, 4, offset=8192),
                        smap('[anon:allocator]', 44, 44, 44, offset=16384),
                        smap('/data/chroma/segment with spaces/data.hnsw (deleted)', 32, 20, 2, offset=24576),
                        smap('/data/chroma-second/control', 12, 7, 0, offset=32768),
                        smap('/venv/plugin.cpython-312.so', 20, 14, 9, offset=40960),
                        smap('/lib/libc.so.6', 18, 12, 0, offset=49152),
                        smap('[anon_shmem:cache]', 10, 4, 0, perms='rw-s', offset=57344),
                        smap('[vvar]', 4, 4, 0, offset=65536),
                        smap('[unknown]', 2, 1, 0, offset=73728),
                    ]
                )
            ),
            '/data/chroma',
        )
        c = read['categories']
        self.assertEqual(
            read['totals'],
            {'mappings': 10, 'rss_bytes': 154 * 1024, 'pss_bytes': 118 * 1024, 'anonymous_bytes': 67 * 1024},
        )
        self.assertEqual(c['chroma_files']['rss_bytes'], 32 * 1024)
        self.assertEqual(c['chroma_files']['anonymous_bytes'], 2 * 1024)
        self.assertEqual(c['shared_libraries']['rss_bytes'], 38 * 1024)
        self.assertEqual(c['other_private_file']['rss_bytes'], 12 * 1024)
        self.assertEqual(c['shared_memory']['rss_bytes'], 10 * 1024)
        self.assertEqual(c['unclassified']['rss_bytes'], 2 * 1024)
        self.assertNotIn('spaces', str(read))

    def test_fail_closed_truncation_and_missing_components(self):
        with self.assertRaisesRegex(ValueError, 'budget'):
            parse_smaps(BytesIO(smap('[heap]', 8)), max_bytes=4)
        with self.assertRaisesRegex(ValueError, 'RSS missing'):
            parse_smaps(BytesIO(b'00000000-00001000 rw-p 00000000 00:00 0 [heap]\n'))
        read = parse_smaps(BytesIO(smap('[heap]', 8)))
        self.assertIsNone(read['totals']['pss_bytes'])
        self.assertIsNone(read['totals']['anonymous_bytes'])
        with tempfile.TemporaryDirectory() as tmp:
            missing = read_smaps(Path(tmp) / 'smaps', None, 123)
            self.assertEqual(missing['status'], 'unavailable')
            self.assertNotIn('categories', missing)

    def test_report_uses_one_baseline_tick_and_keeps_tree_unknown_when_worker_unseen(self):
        def proc(kind, label, rss):
            return {'kind': kind, 'smaps': mapped(label, rss)}

        rows = [
            sample(1, 'case:baseline', 'core', [proc('root', '[heap]', 15)]),
            sample(2, 'case:baseline', 'core', [proc('root', '[heap]', 18)]),
            sample(
                3,
                'case:ingest',
                'core',
                [
                    proc('root', '[anon:allocator]', 32),
                    {'kind': 'descendant', 'smaps': {'status': 'unavailable', 'reason': 'FileNotFoundError'}},
                ],
            ),
            sample(4, 'case:ingest', 'core', [proc('root', '[heap]', 20)]),
        ]
        x = mapping_summary(rows, 'core', 'case:ingest', 'case:baseline')
        self.assertEqual(x['requested_samples'], 2)
        self.assertEqual(x['root_observed_samples'], 2)
        self.assertEqual(x['complete_observed_tree_samples'], 1)
        self.assertEqual(x['root']['baseline_reference']['sample_sequence'], 1)
        peak = x['root']['peak_mapped_snapshot']
        self.assertEqual(peak['sample_sequence'], 3)
        self.assertEqual(peak['largest_rss_category'], 'anonymous_other')
        self.assertEqual(peak['largest_rss_growth_category'], 'anonymous_other')
        self.assertEqual(peak['rss_delta_from_baseline_bytes'], 17 * 1024)
        self.assertEqual(x['root']['last_mapped_snapshot']['sample_sequence'], 4)
        self.assertIsNone(aggregate_mappings(rows[2]['roles']['core']['processes']))

    def test_sampler_opt_in_reads_core_but_default_and_embedder_omit_detailed_maps(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            proc_root = root / 'proc'
            core = fake_process(proc_root, 42, 700, rss=16)
            embedder = fake_process(proc_root, 43, 800, rss=10)
            (core / 'smaps').write_bytes(smap('/owned/chroma/file', 12, 8, 1))
            (embedder / 'smaps').write_bytes(smap('[stack]', 4, 4, 4))
            kwargs = {'roots': {'core': 42, 'embedder': 43}, 'proc_root': proc_root, 'interval_seconds': 0.05}
            with MemorySampler(root / 'normal', **kwargs) as m:
                m.mark('baseline')
                self.assertTrue(m.wait_for_samples('baseline', minimum=1))
            normal = json.loads((root / 'normal/memory-summary.json').read_text())
            self.assertNotIn('mapping_observation', normal)
            self.assertNotIn('mapping_attribution', normal['roles']['core']['baseline'])
            with MemorySampler(root / 'detailed', **kwargs, mapping_every=1, chroma_dir='/owned/chroma') as m:
                m.mark('baseline')
                self.assertTrue(m.wait_for_samples('baseline', minimum=1))
            result = json.loads((root / 'detailed/memory-summary.json').read_text())
            self.assertEqual(result['mapping_observation']['roles'], ['core'])
            self.assertNotIn('mapping_attribution', result['roles']['embedder']['baseline'])
            output = result['roles']['core']['baseline']['mapping_attribution']['root']['peak_mapped_snapshot']
            self.assertEqual(output['largest_rss_category'], 'chroma_files')
            self.assertEqual(output['smaps_minus_status_rss_bytes'], -4 * 1024)
