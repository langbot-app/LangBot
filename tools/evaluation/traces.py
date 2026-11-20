"""Attach exact model inputs from the recording proxy to isolated Pipeline results."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping
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


def validate_model_traces(row: Mapping, protocol: Mapping) -> str:
    """Validate raw delivery receipts independently of a cached status flag."""

    traces = row.get('model_traces')
    if not isinstance(traces, list) or not traces:
        return 'missing'
    try:
        lower = datetime.fromisoformat(row['started_at'])
        upper = datetime.fromisoformat(row['finished_at'])
        if lower.tzinfo is None or upper.tzinfo is None or upper < lower:
            return 'invalid_trace_time'
        request_ids = set()
        for trace in traces:
            request = trace.get('request')
            response = trace.get('response')
            if not isinstance(request, Mapping) or request.get('event') != 'request_start':
                return 'invalid_request_trace'
            request_id = request.get('request_id')
            if not isinstance(request_id, str) or not request_id or request_id in request_ids:
                return 'invalid_request_identity'
            request_ids.add(request_id)
            if (
                not isinstance(response, Mapping)
                or response.get('event') != 'request_complete'
                or response.get('request_id') != request_id
                or response.get('outcome') != 'ok'
                or not isinstance(response.get('upstream_status'), int)
                or not 200 <= response['upstream_status'] < 300
            ):
                return 'incomplete'
            when = datetime.fromisoformat(request['timestamp'])
            finished = datetime.fromisoformat(response['timestamp'])
            if when.tzinfo is None or finished.tzinfo is None or not lower <= when <= finished <= upper:
                return 'invalid_trace_time'
            body = request.get('request_body')
            if not isinstance(body, Mapping):
                return 'invalid_request_trace'
            if 'request_body_utf8' in request and json.loads(request['request_body_utf8']) != body:
                return 'request_body_mismatch'
            messages = body.get('messages')
            if not isinstance(messages, list) or any(not isinstance(message, Mapping) for message in messages):
                return 'invalid_request_trace'
            users = [text_content(message.get('content')) for message in messages if message.get('role') == 'user']
            if not users or users[-1] != row.get('question'):
                return 'question_mismatch'
            if body.get('stream') and (
                response.get('stream_done') is not True or 'data: [DONE]' not in response.get('response_body_utf8', '')
            ):
                return 'incomplete'
            if protocol:
                if body.get('model') != protocol['answer_model']:
                    return 'model_mismatch'
                for setting, field in [('temperature', 'answer_temperature'), ('max_tokens', 'answer_max_tokens')]:
                    if body.get(setting) != protocol.get(field):
                        return 'generation_settings_mismatch'
                prompt_bytes = len(json.dumps(messages, ensure_ascii=False, separators=(',', ':')).encode('utf-8'))
                if prompt_bytes > protocol['context_budget_bytes']:
                    return 'budget_exceeded'
    except (AttributeError, KeyError, TypeError, ValueError):
        return 'invalid_trace'
    return 'verified'


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
        row['model_traces'] = []
        for record in matches:
            request_id = record['request_id']
            if request_id in used:
                raise ValueError('One model request matched multiple questions')
            used.add(request_id)
            end = ends.get(request_id)
            body = record.get('request_body', {})
            prompt_bytes = len(
                json.dumps(body.get('messages', []), ensure_ascii=False, separators=(',', ':')).encode('utf-8')
            )
            record = {**record, 'serialized_messages_bytes': prompt_bytes}
            row['model_traces'].append({'request': record, 'response': end})
        row['model_trace_status'] = validate_model_traces(row, result.get('protocol', {}))
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
