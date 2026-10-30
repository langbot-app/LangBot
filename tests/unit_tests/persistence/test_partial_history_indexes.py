"""Partial historical tables must not block unrelated maintenance indexes."""

import importlib

import pytest
import sqlalchemy as sa
from alembic.migration import MigrationContext
from alembic.operations import Operations

MIGRATION = importlib.import_module('langbot.pkg.persistence.alembic.versions.0039_execution_lease_indexes')


@pytest.mark.parametrize('table,index,columns', MIGRATION.INDEXES)
def test_missing_column_preserves_rows_and_defers_only_unavailable_indexes(table, index, columns):
    engine = sa.create_engine('sqlite:///:memory:')
    metadata = sa.MetaData()
    present = set(columns) - {columns[-1]}
    model = sa.Table(table, metadata, *(sa.Column(name, sa.String) for name in sorted(present)))
    try:
        with engine.begin() as connection:
            metadata.create_all(connection)
            connection.execute(model.insert().values(**{name: 'history' for name in present}))
            with Operations.context(MigrationContext.configure(connection)):
                MIGRATION.upgrade()
                MIGRATION.upgrade()
                indexes = {item['name'] for item in sa.inspect(connection).get_indexes(table)}
                assert index not in indexes
                expected = {
                    name for target, name, required in MIGRATION.INDEXES if target == table and set(required) <= present
                }
                assert indexes == expected
                assert connection.scalar(sa.select(sa.func.count()).select_from(model)) == 1
                MIGRATION.downgrade()
                assert not sa.inspect(connection).get_indexes(table)
    finally:
        engine.dispose()
