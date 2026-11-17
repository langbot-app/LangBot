"""Native soak finalization must distinguish due inputs from overdue cleanup."""

from contextlib import closing
import datetime as dt
import sqlite3
from types import SimpleNamespace

import pytest

from tests.e2e.test_artifact_lifecycle_soak import _NATIVE_DRAIN, _native_final_inputs

NOW = dt.datetime(2026, 1, 2, 6)


@pytest.fixture
def db():
    with closing(sqlite3.connect(':memory:')) as conn:
        conn.row_factory = sqlite3.Row
        conn.executescript(
            """
            CREATE TABLE artifacts (
                workspace_uuid TEXT, content_ref TEXT, owner_type TEXT, expires_at TEXT, deleted_at TEXT
            );
            CREATE TABLE artifact_references (id TEXT);
            CREATE TABLE agent_run (status TEXT);
            CREATE TABLE content_objects (workspace_uuid TEXT, ref TEXT, owner_type TEXT);
            """
        )
        yield conn


def read_final(conn):
    observer = SimpleNamespace(query=lambda statement, params: [dict(row) for row in conn.execute(statement, params)])
    return _native_final_inputs(observer, now=NOW)


def add_input(conn, *, age_seconds, owner='run', tombstone=False):
    expiration = NOW - dt.timedelta(seconds=age_seconds) if age_seconds is not None else None
    conn.execute('INSERT INTO content_objects VALUES (?, ?, ?)', ('workspace', owner, 'artifact'))
    conn.execute(
        'INSERT INTO artifacts VALUES (?, ?, ?, ?, ?)',
        ('workspace', owner, owner, expiration, NOW if tombstone else None),
    )


@pytest.mark.parametrize('age_seconds, tombstone', [(-1, False), (1, False), (1, True), (_NATIVE_DRAIN, False)])
def test_native_finish_allows_unexpired_or_recently_expired_run_input(db, age_seconds, tombstone):
    add_input(db, age_seconds=age_seconds, tombstone=tombstone)
    result = read_final(db)
    assert result['remaining'] == 1
    assert result['due'] == int(age_seconds >= 0)


@pytest.mark.parametrize(
    'age_seconds, owner, tombstone',
    [
        (_NATIVE_DRAIN + 1, 'run', False),
        (1, 'run_output', False),
        (None, 'run', False),
        (-1, 'run', True),
    ],
)
def test_native_finish_rejects_overdue_or_unexpected_artifacts(db, age_seconds, owner, tombstone):
    add_input(db, age_seconds=age_seconds, owner=owner, tombstone=tombstone)
    with pytest.raises(AssertionError, match='invalid=1'):
        read_final(db)


@pytest.mark.parametrize(
    'statement, key',
    [
        ("INSERT INTO artifact_references VALUES ('unreleased')", 'refs'),
        ("INSERT INTO agent_run VALUES ('running')", 'live_runs'),
        ("INSERT INTO content_objects VALUES ('workspace', 'orphan', 'artifact')", 'orphans'),
    ],
)
def test_native_finish_does_not_relax_cleanup_and_lifecycle_checks(db, statement, key):
    add_input(db, age_seconds=1)
    db.execute(statement)
    with pytest.raises(AssertionError, match=f'{key}=1'):
        read_final(db)
