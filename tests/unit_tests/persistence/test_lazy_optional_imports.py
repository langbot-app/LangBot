"""Keep optional vector and S3 dependencies off the SQLite cold-start path."""

from __future__ import annotations

import subprocess
import sys
import os
from pathlib import Path


def _run_isolated_import_check(script: str) -> None:
    project_root = Path(__file__).resolve().parents[3]
    result = subprocess.run(
        [sys.executable, '-c', script],
        cwd=project_root,
        env={**os.environ, 'PYTHONPATH': str(project_root / 'src')},
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr or result.stdout


def test_sqlite_revision_scan_and_local_content_do_not_import_optional_backends() -> None:
    _run_isolated_import_check(
        """
import asyncio
import sys
from types import SimpleNamespace

from langbot.pkg.persistence.alembic_runner import get_alembic_head
from langbot.pkg.storage.content import ContentStore

assert 'pgvector' not in sys.modules
assert 'numpy' not in sys.modules
assert get_alembic_head()
assert 'pgvector' not in sys.modules
assert 'numpy' not in sys.modules

store = ContentStore(SimpleNamespace(
    instance_config=SimpleNamespace(data={'storage': {'content': {'backends': {}}}}),
    logger=None,
))
try:
    asyncio.run(store._s3('missing'))
except ValueError as exc:
    assert 'not configured' in str(exc)
else:
    raise AssertionError('missing content backend should fail')
assert 'boto3' not in sys.modules
assert 'botocore' not in sys.modules
"""
    )


def test_cached_content_backend_does_not_import_s3_provider() -> None:
    _run_isolated_import_check(
        """
import asyncio
import sys
from types import SimpleNamespace

from langbot.pkg.storage.content import ContentStore

identity = {'endpoint_url': '', 'bucket': 'langbot-storage', 'region': 'us-east-1'}
store = ContentStore(SimpleNamespace(
    instance_config=SimpleNamespace(data={
        'storage': {'content': {'backends': {'archive': {'type': 's3', **identity}}}},
    }),
    logger=None,
))
store._providers['archive'] = (object(), identity)
assert asyncio.run(store._s3('archive', locator=identity))[1] == identity
assert 'boto3' not in sys.modules
assert 'botocore' not in sys.modules
"""
    )
