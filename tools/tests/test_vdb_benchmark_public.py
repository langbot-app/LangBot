from pathlib import Path
import json

import pytest

from tools.entrypoints.vdb_benchmark_public import latency
from tools.regression import vdb_benchmark_public as bench


def test_document_metrics_deduplicate_chunks_without_refilling():
    file_ids = {'x': 'not-relevant', 'y': 'relevant-1', 'z': 'relevant-2'}
    result = bench.score_chunks(['x', 'y', 'y'], file_ids, {'relevant-1': 1, 'relevant-2': 1})
    assert result['returned_document_ids'] == ['not-relevant', 'relevant-1']
    assert result['recall_at_10'] == 0.5
    assert result['ndcg_at_10'] == pytest.approx(0.38685280723454163)
    with pytest.raises(ValueError, match='unowned'):
        bench.score_chunks(['unexpected'], file_ids, {'relevant-1': 1})


def test_subset_keeps_all_selected_qrels_and_is_deterministic(tmp_path, monkeypatch):
    docs = {str(i): {} for i in range(24)}
    queries = {f'q{i}': {} for i in range(12)}
    qrels = {'q9': {'21': 1, '22': 1}, 'q8': {'23': 1}}
    monkeypatch.setattr(bench, 'read_data', lambda _path: (docs, queries, qrels))
    src = Path(__file__).resolve().parents[1] / 'profiles' / 'vdb-public-scifact-smoke.json'
    profile = json.loads(src.read_text())
    profile.update(documents=10, test_queries=2)
    path = tmp_path / 'profile.json'
    path.write_text(json.dumps(profile))
    manifest, *_ = bench.plan(path, tmp_path, verify=False)
    assert 'not a standard BEIR score' in manifest['population']
    assert len(set(manifest['documents'])) == 10
    assert {'21', '22', '23'} <= set(manifest['documents'])
    assert not set(manifest['warmup_query_ids']) & set(manifest['scored_query_ids'])
    assert bench.plan(path, tmp_path, verify=False)[0] == manifest


def test_assets_are_hashed_before_parsing(tmp_path):
    (tmp_path / 'scifact.zip').write_bytes(b'corrupted asset')
    with pytest.raises(ValueError, match='SHA-256 mismatch'):
        bench.assets_verified(tmp_path, ('scifact.zip',))


def test_latency_interpolates_and_records_denominator():
    assert latency([]) is None
    assert latency([5, 1]) == {'samples': 2, 'p50': 3.0, 'p95': 4.8, 'p99': 4.96, 'max': 5}
