"""Prepare pinned LoCoMo histories and a deterministic, gold-separated question plan."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
from pathlib import Path


CATEGORY_NAMES = {1: 'multi_hop', 2: 'temporal', 3: 'open_domain', 4: 'single_hop'}
MANIFEST = Path(__file__).parent / 'datasets' / 'locomo10.manifest.json'


def digest(value: object) -> str:
    encoded = json.dumps(value, sort_keys=True, ensure_ascii=False, separators=(',', ':')).encode('utf-8')
    return hashlib.sha256(encoded).hexdigest()


def prepare(
    dataset: Path,
    *,
    seed: int = 42,
    per_category: int | None = None,
    conversation_limit: int | None = None,
) -> tuple[dict, list[dict]]:
    manifest = json.loads(MANIFEST.read_text(encoding='utf-8'))
    raw = dataset.read_bytes()
    sha = hashlib.sha256(raw).hexdigest()
    if sha != manifest['local_sha256']:
        raise ValueError('Dataset SHA-256 differs from the pinned public dataset')
    if per_category is not None and per_category < 1:
        raise ValueError('per_category must be positive')
    if conversation_limit is not None and conversation_limit < 1:
        raise ValueError('conversation_limit must be positive')
    questions = []
    sources = []
    for sample in json.loads(raw)[:conversation_limit]:
        sample_id = sample['sample_id']
        conversation = sample['conversation']
        sessions = sorted(
            (int(match.group(1)), key) for key in conversation if (match := re.fullmatch(r'session_(\d+)', key))
        )
        for number, key in sessions:
            date = conversation.get(key + '_date_time', '')
            turns = conversation[key]
            sources.append(
                {
                    'sample_id': sample_id,
                    'source_id': f'D{number}',
                    'date_time': date,
                    'speakers': [conversation['speaker_a'], conversation['speaker_b']],
                    'turns': [
                        {
                            'id': turn['dia_id'],
                            'speaker': turn['speaker'],
                            'text': turn['text'],
                        }
                        for turn in turns
                    ],
                    'text': '\n'.join(f'[{date}] {turn["speaker"]}: {turn["text"]}' for turn in turns),
                }
            )
        eligible = [
            {
                'id': f'{sample_id}/q{index}',
                'sample_id': sample_id,
                'question': row['question'],
                'category': row['category'],
                'category_name': CATEGORY_NAMES[row['category']],
                'reference_answer': row['answer'],
                'gold_evidence': row.get('evidence', []),
            }
            for index, row in enumerate(sample['qa'], 1)
            if row.get('category') in CATEGORY_NAMES
        ]
        if per_category is not None:
            rng = random.Random(f'{seed}:{sample_id}')
            chosen = []
            for category in CATEGORY_NAMES:
                candidates = [row for row in eligible if row['category'] == category]
                chosen.extend(rng.sample(candidates, min(per_category, len(candidates))))
            eligible = sorted(chosen, key=lambda row: int(row['id'].rsplit('/q', 1)[1]))
        questions.extend(eligible)
    plan = {
        'schema': 'langbot.public-eval.plan.v1',
        'dataset': manifest,
        'dataset_sha256': sha,
        'question_set_sha256': digest(questions),
        'source_set_sha256': digest(sources),
        'seed': seed,
        'selection': {
            'per_category': per_category,
            'conversation_limit': conversation_limit,
        },
        'history_format': 'timestamped-text-only-v1',
        'planned_question_ids': [row['id'] for row in questions],
        'questions': questions,
    }
    return plan, sources


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--dataset', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--seed', type=int, default=42)
    parser.add_argument('--per-category', type=int)
    parser.add_argument('--conversation-limit', type=int)
    args = parser.parse_args()
    plan, sources = prepare(
        args.dataset,
        seed=args.seed,
        per_category=args.per_category,
        conversation_limit=args.conversation_limit,
    )
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / 'plan.json').write_text(json.dumps(plan, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    (args.output / 'sources.jsonl').write_text(
        ''.join(json.dumps(source, ensure_ascii=False) + '\n' for source in sources),
        encoding='utf-8',
    )
    print(
        json.dumps(
            {
                'questions': len(plan['questions']),
                'sessions': len(sources),
                'question_set_sha256': plan['question_set_sha256'],
            }
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
