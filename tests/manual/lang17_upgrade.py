"""Verify a copy of this task's synthetic 4.10.10 database after real boot."""

import asyncio
import json
import os
from pathlib import Path
import sqlite3

import httpx


async def main():
    async with httpx.AsyncClient(base_url='http://127.0.0.1:16399', trust_env=False) as client:
        account_path = Path(os.environ['LANG17_UPGRADE_ACCOUNT'])
        if not account_path.is_absolute():
            account_path = Path(__file__).resolve().parents[2] / account_path
        account = json.loads(account_path.read_text())
        response = await client.post('/api/v1/user/auth', json=account)
        response.raise_for_status()
        client.headers['Authorization'] = 'Bearer ' + response.json()['data']['token']
        preview = await client.get('/api/v1/pipelines/_/migration/preview')
        preview.raise_for_status()
        body = preview.json()
        assert body['code'] == 0
        assert body['data']['items'], 'Legacy pipeline must remain available for migration'
        health = (await client.get('/healthz')).json()
    with sqlite3.connect('data/langbot.db') as db:
        revisions = list(db.execute('SELECT version_num FROM alembic_version'))
        assert revisions == [('0039_execution_lease_indexes',)], revisions
        assert db.execute('SELECT count(*) FROM legacy_pipelines').fetchone()[0] >= 1
        assert db.execute('SELECT count(*) FROM bots').fetchone()[0] >= 1
    Path('upgrade-result.json').write_text(
        json.dumps(
            {
                'revision': revisions,
                'legacy_pipeline_count': len(body['data']['items']),
                'health': health,
                'login': 'passed',
                'scope': 'schema upgrade and preserved legacy migration preview; runner conversion tested separately',
            },
            indent=2,
        )
    )


asyncio.run(main())
