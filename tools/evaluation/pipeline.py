"""Run a fixed public question plan through installed LangBot Pipeline operations.

Provision and ingest through the normal LangBot APIs before running. This runner
submits only the question text. It never retries an uncertain pipeline submission.
"""

from __future__ import annotations

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from .locomo import digest


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


PROTOCOL_FIELDS = (
    'protocol_id',
    'embedding_model',
    'answer_model',
    'answer_policy',
    'answer_temperature',
    'answer_max_tokens',
    'judge_model',
    'judge_policy',
    'context_budget_bytes',
    'execution_layer',
)


def operation(base_url: str, key: str, name: str, payload: dict, timeout: float = 320) -> object:
    request = urllib.request.Request(
        base_url.rstrip('/') + '/api/v1/operations/' + name,
        data=json.dumps(payload).encode('utf-8'),
        headers={'X-API-Key': key, 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urllib.request.build_opener(NoRedirect()).open(request, timeout=timeout) as response:
            body = json.load(response)
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f'LangBot operation {name} returned HTTP {exc.code}') from None
    if body.get('code') != 0:
        raise RuntimeError(f'LangBot operation {name} failed with code {body.get("code")}')
    return body['data']


def save(path: Path, value: object) -> None:
    temporary = path.with_suffix(path.suffix + '.tmp')
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    temporary.replace(path)


def safe_snapshot(value: object) -> object:
    if isinstance(value, dict):
        return {
            key: '[redacted]'
            if any(part in key.lower() for part in ('secret', 'password', 'api_key'))
            or key.lower() in {'token', 'access_token', 'refresh_token', 'api_token', 'authorization'}
            else safe_snapshot(item)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [safe_snapshot(item) for item in value]
    return value


def validate_profile(plan: dict, profile: dict) -> dict:
    if plan.get('question_set_sha256') != digest(plan['questions']):
        raise ValueError('Question plan content changed')
    if plan['planned_question_ids'] != [row['id'] for row in plan['questions']]:
        raise ValueError('Question plan IDs differ from its rows')
    if len(set(plan['planned_question_ids'])) != len(plan['planned_question_ids']):
        raise ValueError('Question plan contains duplicate IDs')
    protocol = profile['protocol']
    if any(field not in protocol for field in PROTOCOL_FIELDS):
        raise ValueError('Profile must declare every shared protocol field')
    if protocol['execution_layer'] != 'langbot.pipeline':
        raise ValueError('This runner requires execution_layer=langbot.pipeline')
    if (
        isinstance(protocol['context_budget_bytes'], bool)
        or not isinstance(protocol['context_budget_bytes'], int)
        or protocol['context_budget_bytes'] <= 0
    ):
        raise ValueError('Context budget must be a positive integer')
    if not profile.get('provenance', {}).get('core_sha'):
        raise ValueError('Profile must record the running Core SHA')
    if not profile['provenance'].get('sdk_version') or not profile['provenance'].get('plugins'):
        raise ValueError('Profile must record SDK and installed plugin versions or archive hashes')
    if not profile.get('arms'):
        raise ValueError('Profile must bind at least one arm')
    for name, arm in profile['arms'].items():
        if not name.replace('_', '').replace('-', '').isalnum():
            raise ValueError('Arm names must contain letters, digits, hyphens or underscores')
        if not arm.get('pipelines'):
            raise ValueError(f'Arm {name} must map every sample to an ingested Pipeline UUID')
        for row in plan['questions']:
            if not arm['pipelines'].get(row['sample_id']):
                raise ValueError(f'Arm {name} has no pipeline for {row["sample_id"]}')
    return {
        **protocol,
        'dataset_sha256': plan['dataset_sha256'],
        'question_set_sha256': plan['question_set_sha256'],
    }


def run(plan: dict, profile: dict, output: Path, base_url: str, key: str) -> int:
    protocol = validate_profile(plan, profile)
    parsed = urlsplit(base_url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment or parsed.scheme not in {'http', 'https'}:
        raise ValueError('Base URL must be HTTP(S) without credentials, query or fragment')
    output.mkdir(parents=True, exist_ok=True)
    lock = output / '.lock'
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError:
        raise ValueError('Run is locked. Inspect the owning process before removing a stale .lock') from None
    os.close(descriptor)
    try:
        pipelines = sorted({pid for arm in profile['arms'].values() for pid in arm['pipelines'].values()})
        snapshots = {
            pid: safe_snapshot(operation(base_url, key, 'pipeline.get', {'pipeline_uuid': pid})) for pid in pipelines
        }
        manifest = {
            'schema': 'langbot.public-eval.run.v1',
            'protocol': protocol,
            'profile': profile,
            'pipeline_snapshot_sha256': digest(snapshots),
            'planned_question_ids': plan['planned_question_ids'],
        }
        manifest_path = output / 'run.json'
        if manifest_path.exists() and json.loads(manifest_path.read_text(encoding='utf-8')) != manifest:
            raise ValueError('Run identity or Pipeline configuration changed. Use a new output directory')
        save(manifest_path, manifest)
        save(output / 'pipelines.json', snapshots)
        for arm_name, arm in profile['arms'].items():
            path = output / (arm_name + '.json')
            result = {
                'schema': 'langbot.public-eval.result.v1',
                'arm': arm_name,
                'protocol': protocol,
                'planned_question_ids': plan['planned_question_ids'],
                'complete': False,
                'results': [],
            }
            if path.exists():
                saved = json.loads(path.read_text(encoding='utf-8'))
                for field in ('schema', 'arm', 'protocol', 'planned_question_ids'):
                    if saved.get(field) != result[field]:
                        raise ValueError('Saved arm identity changed. Use a new output directory')
                expected = {row['id']: row for row in plan['questions']}
                saved_ids = set()
                for row in saved['results']:
                    if row['id'] not in expected or row['id'] in saved_ids:
                        raise ValueError('Saved arm has duplicate or unexpected questions')
                    saved_ids.add(row['id'])
                    if any(row.get(field) != value for field, value in expected[row['id']].items()):
                        raise ValueError('Saved question differs from the fixed plan')
                result = saved
                if any(row['status'] == 'unknown' for row in result['results']):
                    raise ValueError('Saved outcome unknown. Reconcile it with monitoring before resuming')
            done = {(row['sample_id'], row['id']) for row in result['results']}
            for question in plan['questions']:
                identity = (question['sample_id'], question['id'])
                if identity in done:
                    continue
                pipeline = arm['pipelines'][question['sample_id']]
                row = {
                    **question,
                    'pipeline_uuid': pipeline,
                    'status': 'unknown',
                    'answer': '',
                }
                row['started_at'] = datetime.now(timezone.utc).isoformat()
                # Persist an uncertain outcome before submission, including interrupted requests.
                result['results'].append(row)
                save(path, result)
                started = time.monotonic()
                try:
                    execution = operation(
                        base_url,
                        key,
                        'pipeline.run',
                        {
                            'pipeline_uuid': pipeline,
                            'text': question['question'],
                            'timeout': profile.get('timeout_seconds', 180),
                        },
                    )
                    row['execution'] = execution
                    row['status'] = execution.get('status', 'unknown')
                    row['answer'] = execution.get('reply', '')
                    if execution.get('message_id'):
                        try:
                            details = operation(
                                base_url,
                                key,
                                'monitoring.message.detail',
                                {'message_id': execution['message_id']},
                                timeout=30,
                            )
                            row['monitoring'] = details
                            row['answer_usage'] = details.get('llm_stats', {})
                        except Exception as exc:
                            row['trace_error'] = type(exc).__name__
                except Exception as exc:
                    row['error'] = type(exc).__name__
                row['duration_seconds'] = time.monotonic() - started
                row['finished_at'] = datetime.now(timezone.utc).isoformat()
                save(path, result)
                print(f'{arm_name} {question["id"]} {row["status"]}', flush=True)
                if row['status'] == 'unknown':
                    raise RuntimeError('Pipeline outcome unknown. Inspect recorded query before continuing')
            result['complete'] = len(result['results']) == len(plan['questions'])
            save(path, result)
    finally:
        lock.unlink()
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--plan', type=Path, required=True)
    parser.add_argument('--profile', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--base-url', default='http://127.0.0.1:5300')
    parser.add_argument('--api-key-env', default='LANGBOT_API_KEY')
    parser.add_argument('--validate-only', action='store_true')
    args = parser.parse_args()
    plan = json.loads(args.plan.read_text(encoding='utf-8'))
    profile = json.loads(args.profile.read_text(encoding='utf-8'))
    validate_profile(plan, profile)
    if args.validate_only:
        print('Profile and question plan validated')
        return 0
    return run(plan, profile, args.output, args.base_url, os.environ[args.api_key_env])


if __name__ == '__main__':
    raise SystemExit(main())
