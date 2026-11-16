"""Attach exact model inputs from the recording proxy to isolated Pipeline results."""

from __future__ import annotations

import argparse
import json
from datetime import datetime
from pathlib import Path

from .locomo import digest
from .pipeline import save


def text_content(content: object) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts = [part.get('text', '') for part in content if isinstance(part, dict) and part.get('type') == 'text']
        # LocalAgent places event metadata and evidence before the current input.
        return parts[-1] if parts else ''
    return ''


def attach(payload: dict, records: list[dict]) -> dict:
    result = json.loads(json.dumps(payload))
    starts = [record for record in records if record.get('event') == 'request_start']
    ends = {record['request_id']: record for record in records if record.get('event') == 'request_complete'}
    used = set()
    for row in result['results']:
        lower, upper = (
            datetime.fromisoformat(row['started_at']),
            datetime.fromisoformat(row['finished_at']),
        )
        matches = []
        for record in starts:
            when = datetime.fromisoformat(record['timestamp'])
            messages = record.get('request_body', {}).get('messages', [])
            users = [text_content(message.get('content')) for message in messages if message.get('role') == 'user']
            if lower <= when <= upper and users and users[-1] == row['question']:
                matches.append(record)
        row['model_trace_status'] = 'verified' if matches else 'missing'
        row['model_traces'] = []
        for record in matches:
            request_id = record['request_id']
            if request_id in used:
                raise ValueError('One model request matched multiple questions')
            used.add(request_id)
            end = ends.get(request_id)
            if end is None or end.get('outcome') != 'ok':
                row['model_trace_status'] = 'incomplete'
            body = record.get('request_body', {})
            protocol = result.get('protocol', {})
            if protocol:
                row['model_trace_status'] = (
                    'model_mismatch' if body.get('model') != protocol['answer_model'] else row['model_trace_status']
                )
                for setting, field in [('temperature', 'answer_temperature'), ('max_tokens', 'answer_max_tokens')]:
                    if body.get(setting) != protocol.get(field):
                        row['model_trace_status'] = 'generation_settings_mismatch'
                prompt_bytes = len(
                    json.dumps(body.get('messages', []), ensure_ascii=False, separators=(',', ':')).encode('utf-8')
                )
                record = {**record, 'serialized_messages_bytes': prompt_bytes}
                if prompt_bytes > protocol['context_budget_bytes']:
                    row['model_trace_status'] = 'budget_exceeded'
            row['model_traces'].append({'request': record, 'response': end})
        # Candidate retrieval traces must be supplied independently by each adapter.
        row['retrieval_trace_available'] = 'retrieved_hits' in row or 'retrieved_ids' in row
    result['model_trace_coverage'] = sum(row['model_trace_status'] == 'verified' for row in result['results']) / max(
        1, len(result['results'])
    )
    result['untraced_result_sha256'] = digest(payload)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.input.resolve() == args.output.resolve():
        raise ValueError('Keep untraced results unchanged')
    records = [json.loads(line) for line in args.record.read_text(encoding='utf-8').splitlines() if line.strip()]
    result = attach(json.loads(args.input.read_text(encoding='utf-8')), records)
    save(args.output, result)
    print(json.dumps({'model_trace_coverage': result['model_trace_coverage']}))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
