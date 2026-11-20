"""Journal test-owned resources and verify their cleanup."""

import sys
from uuid import uuid4

from tools.regression.evidence import checked


def journal(suite, row):
    row.setdefault('resource_journal', f'resource-case-{uuid4().hex}.json')
    suite.write(
        row['resource_journal'],
        {
            'workspace_uuid': suite.variables['workspace_uuid'],
            'resources': row.get('owned_resources', []),
            'cleanup_errors': row.get('cleanup_errors', []),
        },
    )


def cleanup(suite, row, assertion, action):
    original = sys.exc_info()[1]
    try:
        checked(row, assertion, action)
    except Exception as exc:
        message = f'{type(exc).__name__}: {exc}'
        for secret in suite.secrets:
            message = message.replace(secret, '[REDACTED]')
        row.setdefault('cleanup_errors', []).append(message)
        if original is None:
            raise
    finally:
        journal(suite, row)


def verify_cleanup(suite, deleted):
    checks = []
    for kind, model_type in dict.fromkeys((item['kind'], item.get('type')) for item in deleted):
        args = [kind, 'list'] + (['--type', model_type] if model_type else [])
        data = suite.call(args)
        key = {
            'provider': 'providers',
            'model': 'models',
            'pipeline': 'pipelines',
            'bot': 'bots',
            'knowledge-base': 'bases',
        }[kind]
        items = data.get(key) if isinstance(data, dict) else None
        if not isinstance(items, list) or any(
            not isinstance(item, dict) or not isinstance(item.get('uuid'), str) for item in items
        ):
            raise ValueError(f'Malformed {kind} list response during cleanup verification')
        visible = {item['uuid'] for item in items}
        expected_absent = {item['uuid'] for item in deleted if item['kind'] == kind and item.get('type') == model_type}
        remaining = sorted(expected_absent & visible)
        checks.append({'kind': kind, 'type': model_type, 'deleted_count': len(expected_absent), 'remaining': remaining})
    suite.write('cleanup-checks.json', checks)
    if any(row['remaining'] for row in checks):
        raise ValueError('Deleted resources remain visible in CLI list readback')
