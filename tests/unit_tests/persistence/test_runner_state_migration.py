"""Preserve persisted invocation state while normalizing the Runner table name."""

import importlib
from unittest.mock import patch

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

migration = importlib.import_module('langbot.pkg.persistence.alembic.versions.0024_unify_runner_state')


@pytest.mark.parametrize('current_table_exists', [False, True])
def test_upgrade_preserves_state_and_downgrade_restores_name(current_table_exists):
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        conn.execute(sa.text('CREATE TABLE agent_runner_state (id INTEGER PRIMARY KEY, value_json TEXT)'))
        conn.execute(sa.text("INSERT INTO agent_runner_state VALUES (1, 'saved value')"))
        if current_table_exists:
            conn.execute(sa.text('CREATE TABLE runner_state (id INTEGER PRIMARY KEY, value_json TEXT)'))
        with patch.object(migration, 'op', Operations(MigrationContext.configure(conn))):
            migration.upgrade()
            assert 'agent_runner_state' not in sa.inspect(conn).get_table_names()
            assert conn.scalar(sa.text('SELECT value_json FROM runner_state')) == 'saved value'
            migration.downgrade()
            assert 'runner_state' not in sa.inspect(conn).get_table_names()
            assert conn.scalar(sa.text('SELECT value_json FROM agent_runner_state')) == 'saved value'
    engine.dispose()


def test_two_populated_tables_fail_without_discarding_either():
    engine = sa.create_engine('sqlite://')
    with engine.begin() as conn:
        for name in ('agent_runner_state', 'runner_state'):
            conn.execute(sa.text(f'CREATE TABLE {name} (id INTEGER PRIMARY KEY)'))
            conn.execute(sa.text(f'INSERT INTO {name} VALUES (1)'))
        with patch.object(migration, 'op', Operations(MigrationContext.configure(conn))):
            with pytest.raises(RuntimeError, match='Both .* contain state'):
                migration.upgrade()
        assert set(sa.inspect(conn).get_table_names()) == {'agent_runner_state', 'runner_state'}
    engine.dispose()
