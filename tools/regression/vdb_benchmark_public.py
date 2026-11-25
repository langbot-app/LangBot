"""Pinned BEIR SciFact inputs and document-level retrieval scoring."""

from collections import defaultdict
import csv
from hashlib import sha256
from io import TextIOWrapper
import json
from math import log2
import random
from zipfile import ZipFile

MODEL = 'all-MiniLM-L6-v2'
REVISION = '1110a243fdf4706b3f48f1d95db1a4f5529b4d41'
MODEL_URL = f'https://huggingface.co/sentence-transformers/{MODEL}/resolve/{REVISION}'
ASSETS = {
    'scifact.zip': (
        'https://public.ukp.informatik.tu-darmstadt.de/thakur/BEIR/datasets/scifact.zip',
        '536e14446a0ba56ed1398ab1055f39fe852686ecad24a6306c80c490fa8e0165',
    ),
    'model.onnx': (MODEL_URL + '/onnx/model.onnx', '6fd5d72fe4589f189f8ebc006442dbb529bb7ce38f8082112682524616046452'),
    'tokenizer.json': (
        MODEL_URL + '/tokenizer.json',
        'be50c3628f2bf5bb5e3a7f17b1f74611b2561a3a27eeab05e5aa30f411572037',
    ),
}
SCHEMA = {
    'documents': (10, 5183),
    'test_queries': (1, 300),
    'seed': (0, 2**32 - 1),
    'workers': (1, 16),
    'warmup_queries': (0, 30),
    'request_timeout_seconds': (1, 300),
    'index_timeout_seconds': (1, 600),
}


def assets_verified(directory, names=ASSETS):
    for name in names:
        fingerprint = sha256()
        with (directory / name).open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                fingerprint.update(block)
        if fingerprint.hexdigest() != ASSETS[name][1]:
            raise ValueError(f'SHA-256 mismatch for {name}')


def read_data(directory):
    with ZipFile(directory / 'scifact.zip') as archive:

        def jsonl(name):
            with archive.open('scifact/' + name) as rows:
                return {row['_id']: row for row in map(json.loads, rows)}

        docs, queries = jsonl('corpus.jsonl'), jsonl('queries.jsonl')
        qrels = defaultdict(dict)
        with TextIOWrapper(archive.open('scifact/qrels/test.tsv'), encoding='utf-8') as rows:
            for row in csv.DictReader(rows, delimiter='\t'):
                score = int(row['score'])
                if score > 0:
                    qrels[row['query-id']][row['corpus-id']] = score
    if (len(docs), len(queries), len(qrels), sum(map(len, qrels.values()))) != (5183, 1109, 300, 339):
        raise ValueError('Unexpected canonical BEIR SciFact counts')
    if not qrels.keys() <= queries.keys() or any(not grades.keys() <= docs.keys() for grades in qrels.values()):
        raise ValueError('Unresolved BEIR SciFact qrels IDs')
    return docs, queries, dict(qrels)


def plan(profile_file, directory, *, verify=True):
    profile = json.loads(profile_file.read_text())
    if not isinstance(profile, dict) or set(profile) != set(SCHEMA):
        raise ValueError('Invalid public RAG profile fields')
    for key, (lo, hi) in SCHEMA.items():
        if type(profile[key]) is not int or not lo <= profile[key] <= hi:
            raise ValueError(f'{key} must be an integer in {lo}..{hi}')
    if verify:
        assets_verified(directory)
    docs, queries, qrels = read_data(directory)
    rng = random.Random(profile['seed'])
    selected = rng.sample(sorted(qrels), profile['test_queries'])
    selected_qrels = {key: qrels[key] for key in selected}
    relevant = set().union(*(set(scores) for scores in selected_qrels.values()))
    if len(relevant) > profile['documents']:
        raise ValueError('Profile too small to contain all selected test qrels positives')
    population = sorted(
        relevant | set(rng.sample(sorted(docs.keys() - relevant), profile['documents'] - len(relevant)))
    )
    rng.shuffle(population)
    warmup_ids = rng.sample(sorted(queries.keys() - qrels.keys()), profile['warmup_queries'])
    manifest = {
        'dataset': 'BEIR SciFact',
        'dataset_card': 'https://huggingface.co/datasets/BeIR/scifact',
        'dataset_license': 'CC-BY-SA-4.0',
        'split': 'test',
        'canonical_documents': len(docs),
        'canonical_test_queries': len(qrels),
        'model': MODEL,
        'model_revision': REVISION,
        'model_license': 'Apache-2.0',
        'asset_sources': {name: {'url': url, 'sha256': checksum} for name, (url, checksum) in ASSETS.items()},
        'population': 'full corpus'
        if len(population) == len(docs)
        else 'qrels-conditioned subset; not a standard BEIR score',
        'selection': 'Sample test qids by seed, include all their positive documents, sample remaining corpus documents by seed',
        'profile': profile,
        'documents': population,
        'warmup_query_ids': warmup_ids,
        'scored_query_ids': selected,
        'qrels': selected_qrels,
    }
    return manifest, docs, queries


def score_chunks(file_ids, engine_ids, qrels, k=10):
    """Map LangRAG's top-k chunks to unique documents in first-seen order."""
    if not qrels or len(file_ids) > k or any(doc not in engine_ids for doc in file_ids):
        raise ValueError('Query has no positive qrels, too many hits, or returned an unowned file')
    ranked = list(dict.fromkeys(engine_ids[doc] for doc in file_ids))
    hits = len(qrels.keys() & set(ranked))
    actual = sum((2 ** qrels.get(doc, 0) - 1) / log2(rank + 2) for rank, doc in enumerate(ranked))
    ideal = sum((2**grade - 1) / log2(rank + 2) for rank, grade in enumerate(sorted(qrels.values(), reverse=True)[:k]))
    return {'returned_document_ids': ranked, 'recall_at_10': hits / len(qrels), 'ndcg_at_10': actual / ideal}
