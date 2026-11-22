"""Prepare exact-size, disjoint replay files from the pinned public WikiText shard."""

import argparse
from hashlib import file_digest
import json
from pathlib import Path

from tools.entrypoints.vdb_benchmark_upload import load_profile

REVISION = 'b08601e04326c79dfdd32d625aee71d232d685c3'
SHARD = 'wikitext-103-raw-v1/train-00000-of-00002.parquet'
URL = f'https://huggingface.co/datasets/Salesforce/wikitext/resolve/{REVISION}/{SHARD}'
CARD = 'https://huggingface.co/datasets/Salesforce/wikitext'
WIKITEXT_SHA256 = '74da360f23826045b3e6ac6375411fdb15f003030aa74f2596ed08b857cb9212'
LICENSE = 'WikiText dataset card: CC BY-SA; historical source notices also list CC BY-SA-3.0 and GFDL'


def prepare(path, profile, output):
    with path.open('rb') as raw:
        seen = file_digest(raw, 'sha256').hexdigest()
    if seen != WIKITEXT_SHA256:
        raise ValueError('Public shard SHA-256 does not match the expected release checksum')

    import pyarrow.parquet as parquet

    def paragraphs():
        for batch in parquet.ParquetFile(path).iter_batches(batch_size=256, columns=['text']):
            for row in batch.column(0).to_pylist():
                if row:
                    yield row.encode('utf-8')

    output.mkdir(mode=0o700, parents=True, exist_ok=False)
    stream = iter(paragraphs())
    records = {}
    for case in profile['cases']:
        files = []
        for index in range(case['files']):
            size = case['file_bytes']
            pending = bytearray()
            while len(pending) < size:
                try:
                    pending.extend(next(stream))
                except StopIteration as exc:
                    raise ValueError('Pinned corpus shard did not have sufficient bytes for the profile') from exc
            # Drop at most one row at the end of each file and end on a complete
            # UTF-8 codepoint. Up to three newline bytes make sizing exact.
            clean = bytes(pending[:size]).decode('utf-8', 'ignore').encode('utf-8')
            name = f'{case["id"]}-{index:02}.txt'
            file = output / name
            file.write_bytes(clean + b'\n' * (size - len(clean)))
            with file.open('rb') as stored:
                checksum = file_digest(stored, 'sha256').hexdigest()
            files.append({'path': name, 'bytes': size, 'sha256': checksum})
        records[case['id']] = files
    result = {
        'version': 1,
        'dataset': 'Salesforce/wikitext',
        'variant': 'wikitext-103-raw-v1',
        'split': 'train',
        'source': URL,
        'dataset_card': CARD,
        'revision': REVISION,
        'source_sha256': seen,
        'license_notice': LICENSE,
        'transformation': 'sequential disjoint UTF-8 text windows; clipped at byte target, at most three newline bytes',
        'cases': records,
    }
    (output / 'manifest.json').write_text(json.dumps(result, indent=2) + '\n')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--parquet', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        prepare(args.parquet, load_profile(args.profile), args.output)
    except (ImportError, OSError, ValueError) as exc:
        parser.exit(1, f'Prepare public corpus: {exc}\n')


if __name__ == '__main__':
    main()
